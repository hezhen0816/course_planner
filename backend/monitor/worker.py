import sys
import os
import time
import random
import logging
import threading
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any


from supabase import create_client, Client
from dotenv import load_dotenv

# backend.config reads the environment at import time, so load the repo-root .env
# before importing anything that depends on it (credentials, school_sessions).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_REPO_ROOT, '.env'))
load_dotenv()

from .monitor import CourseMonitor, _enroll_thread_local
from .config import MonitorConfig, CourseConfig
from .email_sender import EmailSender
from .enrollment import EnrollmentClient
from .api_client import NTUSTCourseAPI
from .semester import get_default_semester
from .utils import setup_logging
from .crypto import CryptoManager


def _parse_ts(value: Any) -> Optional[float]:
    """ISO 8601 字串（PostgREST 輸出）轉 epoch 秒；空值或格式錯誤回 None。"""
    if not value:
        return None
    try:
        text = str(value).replace('Z', '+00:00')
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None
from ..credentials import get_school_credentials_secret, CredentialStoreError
from ..school_sessions import save_school_session_state, session_state_from_requests_session

# Setup logging
# Ensure console logging is enabled even if setup_logging was called by imports
logger = logging.getLogger('ntust_monitor')
has_console = False
for h in logger.handlers:
    # FileHandler inherits from StreamHandler, so we must explicitly check it's NOT a FileHandler
    if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
        has_console = True
        break

if not has_console:
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - [%(name)s] - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
logger.setLevel(logging.INFO)


class SupabaseMonitor(CourseMonitor):
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
        # Initialize with empty config, will be updated in loop
        initial_config = MonitorConfig(courses=[])
        super().__init__(initial_config)
        
        self.user_settings_id = None
        self.user_id = None
        self.is_active = True  # Master switch status
        self.users_data: List[Dict] = []  # All users' settings + courses
        self.enrollment_attempts_per_user: Dict[str, Dict] = {}  # Per-user enrollment attempts
        self.course_states_per_user: Dict[str, Dict] = {}  # Per-user course states (prevent cross-user contamination)
        self.enrollment_clients_per_user: Dict[str, EnrollmentClient] = {}  # Per-user enrollment clients (preserve session & rate limits)

        # Email notification
        self.email_sender = EmailSender()
        self.user_email_map: Dict[str, str] = {}
        self.user_email_notify_map: Dict[str, bool] = {}
        self.user_smtp_map: Dict[str, Dict] = {}
        self.user_resend_map: Dict[str, str] = {}  # user_id -> Resend API Key（每位使用者自有 Key）
        self._system_log_lock = threading.Lock()
        self._user_workers: Dict[str, Dict[str, Any]] = {}
        
        self.crypto = CryptoManager()

    def _on_login_success(self, user_id, student_id, enroll_client) -> None:
        """Publish the worker's SSO session so the official-selection API can reuse it
        instead of logging in again (the worker is the single session holder)."""
        if not user_id or not student_id:
            return
        try:
            state = session_state_from_requests_session(enroll_client.session, is_logged_in=True)
            save_school_session_state(user_id, student_id, state)
            logger.info(f"[{user_id[:8]}] 已將選課系統 session 寫入 school_sessions")
        except Exception as e:
            logger.warning(f"[{user_id[:8]}] 寫入 school_sessions 失敗：{e}")

    def _resolve_log_user_id(self, user_id: Optional[str] = None) -> Optional[str]:
        """Resolve target user_id for system_logs writes with thread-local priority."""
        return user_id or getattr(_enroll_thread_local, 'user_id', None) or self.user_id

    def _normalize_log_level(self, level: str) -> str:
        """Normalize log type before writing to DB for consistent frontend rendering."""
        normalized = (level or 'info').lower()
        if normalized == 'warning':
            return 'warn'
        if normalized in {'info', 'success', 'warn', 'error', 'heartbeat'}:
            return normalized
        return 'info'

    def _db_update_with_retry(self, table: str, data: Dict, match_col: str, match_val: Any, attempts: int = 3) -> None:
        """Run a Supabase update, retrying on transient transport errors.

        The HTTP/2 connection to Supabase is sometimes closed server-side
        (ConnectionTerminated / Server disconnected); the pooled client does not
        transparently reconnect, so the next call after a short pause succeeds.
        """
        last_err: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                self.supabase.table(table).update(data).eq(match_col, match_val).execute()
                return
            except Exception as e:
                last_err = e
                if attempt < attempts - 1:
                    time.sleep(0.3 * (attempt + 1))
        assert last_err is not None
        raise last_err

    def _insert_system_log(self, user_id: str, level: str, message: str) -> bool:
        """Insert into system_logs with a small retry to tolerate transient failures."""
        log_level = self._normalize_log_level(level)
        for attempt in range(2):
            try:
                with self._system_log_lock:
                    self.supabase.table('system_logs').insert({
                        'user_id': user_id,
                        'type': log_level,
                        'message': message,
                        'created_at': datetime.now(timezone.utc).isoformat()
                    }).execute()
                return True
            except Exception as e:
                if attempt == 1:
                    logger.error(f"寫入 Supabase 日誌失敗（uid={user_id[:8]}）：{e}")
                else:
                    time.sleep(0.15)
        return False

    def _add_system_notification(self, message: str, level: str = "info") -> None:
        """Override to write to Supabase system_logs.

        當由加選執行緒呼叫時，優先使用 thread-local 中儲存的 user_id（快照），
        避免 self.user_id 被主迴圈切換到其他使用者後寫入錯誤帳號的日誌。
        """
        super()._add_system_notification(message, level)

        # 加選執行緒呼叫時，使用 thread-local 儲存的 user_id；主迴圈呼叫時，使用 self.user_id
        user_id = self._resolve_log_user_id()

        if not user_id:
            logger.warning(f"無法寫入日誌：未設定使用者 ID（訊息：{message}）")
            return

        if self._insert_system_log(user_id, level, message):
            logger.info(f"[通知] {message}")

        # Email notification for important events
        should_email = (
            level == 'success' or
            (level == 'error' and '加選' in message)
        )
        if should_email and self.user_email_notify_map.get(user_id):
            to_email = self.user_email_map.get(user_id)
            if to_email:
                try:
                    smtp = self.user_smtp_map.get(user_id)
                    kw = dict(
                        smtp_host=smtp.get('host'),
                        smtp_port=smtp.get('port'),
                        smtp_username=smtp.get('username'),
                        smtp_password=smtp.get('password'),
                    ) if smtp else {}
                    resend_key = self.user_resend_map.get(user_id)
                    if resend_key:
                        kw['resend_api_key'] = resend_key
                    prefix = {'success': '✅', 'error': '❌'}.get(level, '')
                    subject = f"{prefix} NTUST Monitor — {message[:60]}"
                    self.email_sender.send_async(to_email, subject, message, level, **kw)
                except Exception as e:
                    logger.warning(f"發送通知 Email 失敗（uid={user_id[:8]}）: {e}")

    def _add_notification(self, course: CourseConfig, current_count: int, course_info: Dict, previous_remaining: Optional[int] = None) -> None:
        """Override to write availability changes to Supabase system_logs"""
        super()._add_notification(course, current_count, course_info, previous_remaining)

        restrict1 = course_info.get('Restrict1', '')
        if restrict1 and restrict1 != '9999':
            try:
                restrict1_int = int(restrict1)
            except (ValueError, TypeError):
                return
            remaining = restrict1_int - current_count

            # Skip notification on initial check (previous_remaining is None = no actual change)
            if previous_remaining is None:
                return

            msg = f"名額變動: {course.alias} ({course.course_no}) - 剩餘: {remaining} (限制: {restrict1_int}, 已選: {current_count})"
            self._add_system_notification(msg, level="success" if remaining > 0 else "warn")

    def fetch_config(self) -> bool:
        """Fetch ALL users' settings and their own courses from Supabase"""
        try:
            settings_response = self.supabase.table('user_settings').select('*').execute()
            if not settings_response.data:
                logger.warning("Supabase 中尚無使用者設定。")
                return False

            self.users_data = []
            self.user_email_map = {}
            self.user_email_notify_map = {}
            self.user_smtp_map = {}
            self.user_resend_map = {}

            for settings in settings_response.data:
                try:
                    user_id = settings.get('user_id')
                    is_encrypted = settings.get('is_encrypted', False)

                    # user_settings 只剩通知用的密鑰（smtp_password / resend_api_key）需要加解密；
                    # 校務密碼一律在 app_private.school_credentials，不再讀 user_settings.student_password。
                    raw_smtp_password = settings.get('smtp_password') or ''
                    raw_resend_api_key = settings.get('resend_api_key') or ''
                    smtp_password = raw_smtp_password
                    resend_api_key = raw_resend_api_key

                    if not is_encrypted and (raw_smtp_password or raw_resend_api_key):
                        # 前端寫入明文並把 is_encrypted 設 false；這裡加密後寫回
                        if self.crypto.fernet is None:
                            logger.error(f"使用者 {user_id[:8]} 有敏感資料但未設定加密金鑰，略過自動加密")
                        else:
                            # 前端只改其中一個密碼時會把整列標成未加密，其他欄位仍是密文；
                            # 已能解密的欄位視為已加密，不可再加密一次（否則永遠解不開）。
                            def _ensure_encrypted(raw: str) -> str:
                                if self.crypto.is_ciphertext(raw):
                                    return raw
                                return self.crypto.encrypt(raw)

                            update_data = {'is_encrypted': True}
                            if raw_smtp_password:
                                update_data['smtp_password'] = _ensure_encrypted(raw_smtp_password)
                                smtp_password = self.crypto.decrypt(update_data['smtp_password'])
                            if raw_resend_api_key:
                                update_data['resend_api_key'] = _ensure_encrypted(raw_resend_api_key)
                                resend_api_key = self.crypto.decrypt(update_data['resend_api_key'])

                            try:
                                self.supabase.table('user_settings').update(update_data).eq('user_id', user_id).execute()
                                logger.info(f"已將使用者 {user_id[:8]} 的通知密鑰加密並寫回資料庫")
                            except Exception as e:
                                logger.error(f"加密寫回資料庫失敗: {e}")
                    elif is_encrypted:
                        if self.crypto.fernet is None:
                            logger.error(f"使用者 {user_id[:8]} 的設定標記為已加密，但加密金鑰不可用，將跳過通知密鑰")
                            smtp_password = ''
                            resend_api_key = ''
                        else:
                            if smtp_password:
                                smtp_password = self.crypto.decrypt(smtp_password)
                            if resend_api_key:
                                resend_api_key = self.crypto.decrypt(resend_api_key)

                    # Read email notification preference
                    email_notify = settings.get('email_notify', False)
                    self.user_email_notify_map[user_id] = email_notify

                    # Resend API Key per-user（每位使用者自有 Key，需至 Resend 註冊取得）
                    resend_key = resend_api_key.strip()
                    if resend_key:
                        self.user_resend_map[user_id] = resend_key

                    # SMTP per-user (frontend config，進階／本機用)
                    smtp_user = (settings.get('smtp_username') or '').strip()
                    smtp_pass = smtp_password
                    if smtp_user and smtp_pass:
                        self.user_smtp_map[user_id] = {
                            'host': (settings.get('smtp_host') or 'smtp.gmail.com').strip(),
                            'port': int(settings.get('smtp_port') or 587),
                            'username': smtp_user,
                            'password': smtp_pass,
                        }

                    # Get user email from Supabase Auth (only if email_notify is on)
                    if email_notify and (self.email_sender.configured or user_id in self.user_smtp_map or user_id in self.user_resend_map):
                        try:
                            auth_resp = self.supabase.auth.admin.get_user_by_id(user_id)
                            if auth_resp and auth_resp.user and auth_resp.user.email:
                                self.user_email_map[user_id] = auth_resp.user.email
                        except Exception as e:
                            logger.debug(f"取得使用者 Email 失敗（{user_id[:8]}）：{e}")

                    # Fetch courses belonging to THIS user only
                    courses_response = self.supabase.table('monitored_courses').select('*').eq('user_id', user_id).execute()

                    user_courses = []
                    for c_data in courses_response.data:
                        if c_data.get('status') in ('paused', 'enrolled'):
                            continue
                        course = CourseConfig(
                            course_no=c_data.get('course_code', ''),
                            course_name=c_data.get('course_name', ''),
                            semester=c_data.get('semester') or get_default_semester(verify_ssl=settings.get('verify_ssl', True)),
                            alias=c_data.get('course_name', ''),
                            auto_enroll=c_data.get('auto_enroll', False),
                            max_enroll_attempts=int(c_data.get('max_attempts') or 3),
                            attempt_count=int(c_data.get('attempt_count') or 0),
                        )
                        course.db_id = c_data.get('id')
                        self._sync_attempt_count_from_db(user_id, course)
                        user_courses.append(course)

                    # 校務帳密唯一來源：app_private.school_credentials（Compass 與 worker 共用）。
                    # 沒有就只查名額，不能自動加選。
                    student_id = settings.get('student_id')
                    student_password = ''
                    try:
                        secret = get_school_credentials_secret(user_id)
                        if secret.get('hasPassword') and secret.get('username'):
                            student_id = secret['username']
                            student_password = secret['password']
                    except (CredentialStoreError, Exception) as e:
                        logger.warning(f"讀取 app_private 校務帳密失敗（uid={user_id[:8]}），此使用者無法自動加選：{e}")

                    check_interval_ms = settings.get('check_interval') or 30000
                    self.users_data.append({
                        'user_id': user_id,
                        'student_id': student_id,
                        'student_password': student_password,
                        'check_interval': check_interval_ms / 1000.0,
                        'random_interval': settings.get('random_interval', 5),
                        'is_active': settings.get('is_active', True),
                        'verify_ssl': settings.get('verify_ssl', True),
                        'courses': user_courses,
                        'enrollment_open_start': (settings.get('enrollment_open_start') or '').strip() or None,
                        'enrollment_open_end': (settings.get('enrollment_open_end') or '').strip() or None,
                        'enrollment_period': (settings.get('enrollment_period') or 'A06').strip() or 'A06',  # A06=電腦抽選後選課, B01=加退選課
                        'login_paused_until': settings.get('login_paused_until'),
                        # Proxy settings
                        'proxy_enabled': settings.get('proxy_enabled', False),
                        'proxy_type': str(settings.get('proxy_type') or 'socks5'),
                        'proxy_host': str(settings.get('proxy_host') or ''),
                        'proxy_port': str(settings.get('proxy_port') or ''),
                        'proxy_username': str(settings.get('proxy_username') or ''),
                        'proxy_password': str(settings.get('proxy_password') or ''),
                    })

                except Exception as e:
                    # 一筆壞掉的設定不應讓所有使用者都讀取失敗
                    uid = str(settings.get('user_id') or '?')[:8]
                    logger.error(f"使用者 {uid} 的設定解析失敗，已略過：{e}", exc_info=True)
                    continue

            return True

        except Exception as e:
            logger.error(f"讀取設定失敗：{e}")
            return False

    def _lookup_auth_email(self, user_id: Optional[str]) -> str:
        """由 Supabase Auth 取得帳號信箱（快取於 user_email_map）。"""
        if not user_id:
            return ''
        cached = self.user_email_map.get(user_id)
        if cached:
            return cached
        try:
            auth_resp = self.supabase.auth.admin.get_user_by_id(user_id)
            email = (getattr(getattr(auth_resp, 'user', None), 'email', None) or '').strip()
        except Exception as e:
            logger.warning(f"取得使用者 Email 失敗（{user_id[:8]}）：{e}")
            return ''
        if email:
            self.user_email_map[user_id] = email
        return email

    def _process_test_email_requests(self) -> None:
        """處理待發送的測試信請求（email_test_requests 表）。"""
        try:
            resp = self.supabase.table('email_test_requests').select('id, user_id, email').is_('sent_at', 'null').order('created_at').limit(20).execute()
            if not resp.data:
                return
            for row in resp.data:
                req_id = row['id']
                user_id = row.get('user_id')
                # 收件人一律以 Auth 帳號信箱為準；前端寫入的 email 欄位不可信（可被改成任意地址）
                to_email = self._lookup_auth_email(user_id)
                if not to_email:
                    self.supabase.table('email_test_requests').update({
                        'sent_at': datetime.now(timezone.utc).isoformat(),
                        'error': '無法取得帳號信箱，請重新登入後再試'
                    }).eq('id', req_id).execute()
                    continue
                smtp = self.user_smtp_map.get(user_id) if user_id else None
                kw = dict(
                    smtp_host=smtp.get('host') if smtp else None,
                    smtp_port=smtp.get('port') if smtp else None,
                    smtp_username=smtp.get('username') if smtp else None,
                    smtp_password=smtp.get('password') if smtp else None,
                ) if smtp else {}
                resend_key = self.user_resend_map.get(user_id) if user_id else None
                if resend_key:
                    kw['resend_api_key'] = resend_key
                if not self.email_sender._is_configured(
                    kw.get('smtp_host'), kw.get('smtp_port'),
                    kw.get('smtp_username'), kw.get('smtp_password'),
                    kw.get('resend_api_key'),
                ):
                    self.supabase.table('email_test_requests').update({
                        'sent_at': datetime.now(timezone.utc).isoformat(),
                        'error': '尚未設定 Email 發送方式（請於設定頁填寫 Resend API Key 或 SMTP）'
                    }).eq('id', req_id).execute()
                    continue
                subject = "NTUST Monitor — 測試信"
                message = "這是一封測試信。若您收到此信，表示 Email 通知已正常運作。"
                try:
                    self.email_sender.send_sync(to_email, subject, message, 'info', **kw)
                    self.supabase.table('email_test_requests').update({
                        'sent_at': datetime.now(timezone.utc).isoformat()
                    }).eq('id', req_id).execute()
                    logger.info(f"測試信已發送至 {to_email}")
                except Exception as e:
                    err_msg = str(e)[:500]
                    self.supabase.table('email_test_requests').update({
                        'sent_at': datetime.now(timezone.utc).isoformat(),
                        'error': err_msg
                    }).eq('id', req_id).execute()
                    logger.warning(f"測試信發送失敗（{to_email}）：{e}")
        except Exception as e:
            logger.debug(f"處理測試信請求時發生錯誤：{e}")

    def check_course(self, course: CourseConfig) -> bool:
        """Override to update Supabase with course status"""
        success = super().check_course(course)
        
        if hasattr(course, 'db_id'):
            try:
                identifier = self._get_course_identifier(course)
                state = self.get_course_state(identifier)
                
                if state:
                    course_info = state.get('course_info', {})
                    current_count = state.get('count', 0)
                    restrict1 = course_info.get('Restrict1', '?')
                    enrolled_str = f"{current_count}/{restrict1}"
                    course_semester = (course_info.get('Semester') or course.semester or '').strip()
                    update_data = {
                        'course_name': course_info.get('CourseName', course.course_name),
                        'current_enrolled': enrolled_str,
                        'last_check_time': datetime.now(timezone.utc).isoformat(),
                    }
                    # 只接受更新的學期，避免舊學期資料回寫覆蓋
                    if course_semester and (not course.semester or course_semester > course.semester):
                        course.semester = course_semester
                        update_data['semester'] = course_semester
                    # 若課程已加選成功，不覆寫 status（避免蓋掉 'enrolled'）
                    try:
                        db_row = self.supabase.table('monitored_courses').select('status').eq('id', course.db_id).execute()
                        db_status = db_row.data[0].get('status') if db_row.data else None
                    except Exception:
                        db_status = None
                    if db_status != 'enrolled':
                        update_data['status'] = 'monitoring'
                    logger.info(f"  ✓ {course.alias}（{course.course_no}）→ {enrolled_str}")
                    outage = self._note_query_success(identifier)
                    if outage is not None:
                        self._write_log(
                            f"✓ {course.alias}（{course.course_no}）查詢已恢復（不穩定持續約 {int(outage // 60)} 分 {int(outage % 60)} 秒）",
                            level="info",
                        )
                    previous_count = state.get('previous_count')
                    if previous_count is not None and previous_count != current_count:
                        self._write_log(
                            f"名額變動：{course.alias}（{course.course_no}）→ {enrolled_str}",
                            level="info",
                        )
                else:
                    update_data = {
                        'last_check_time': datetime.now(timezone.utc).isoformat(),
                        'status': 'error',
                        'current_enrolled': 'Error'
                    }
                    logger.warning(f"  ✗ {course.alias}（{course.course_no}）→ 查詢失敗")
                    # 節流：只有 check_course 這一輪允許寫入時才同步寫這行，避免尖峰刷屏
                    if self._query_fail_last_logged.get(identifier, 0) >= time.time() - 2:
                        self._write_log(f"✗ {course.alias}（{course.course_no}）→ 查詢失敗", level="error")
                
                self._db_update_with_retry('monitored_courses', update_data, 'id', course.db_id)
                    
            except Exception as e:
                logger.error(f"更新課程資料失敗 {course.alias}：{e}")
                
        return success

    def _set_login_pause(self, user_id: str, until_ts: Optional[float], reason: str) -> None:
        """把自動登入冷卻狀態寫進 user_settings，並留一筆日誌讓儀表板顯示。"""
        if until_ts:
            until_iso = datetime.fromtimestamp(until_ts, tz=timezone.utc).isoformat()
            data = {'login_paused_until': until_iso, 'login_pause_reason': (reason or '')[:500]}
            minutes = max(1, int((until_ts - time.time()) // 60))
            self._write_log(
                f"⚠ 連續登入失敗 {EnrollmentClient.LOGIN_FAILURE_COOLDOWN_AFTER} 次，已暫停自動登入 {minutes} 分鐘以保護帳號不被鎖定。"
                f"請先用瀏覽器登入選課系統確認帳密與 SSO 狀態。最後錯誤：{reason}",
                level='warn', user_id=user_id,
            )
        else:
            data = {'login_paused_until': None, 'login_pause_reason': None}
            self._write_log("自動登入已恢復（登入成功，冷卻解除）", level='info', user_id=user_id)
        try:
            self._db_update_with_retry('user_settings', data, 'user_id', user_id)
        except Exception as e:
            logger.error(f"寫入登入暫停狀態失敗（uid={user_id[:8]}）：{e}")

    def _sync_attempt_count_from_db(self, user_id: str, course: CourseConfig) -> None:
        """以資料庫的 attempt_count 校正記憶體中的嘗試次數。

        規則：資料庫為 0（前端重設）時直接採用並清掉「已達上限」通知節流；
        否則取兩者較大值，避免加選執行緒剛寫入、這裡又讀到舊值而多試一次。
        """
        identifier = self._get_course_identifier(course)
        db_count = int(course.attempt_count or 0)
        with self.state_lock:
            ea = self.enrollment_attempts_per_user.setdefault(user_id, {})
            mem_count = ea.get(identifier, 0)
            if db_count == 0:
                if mem_count > 0:
                    logger.info(f"[{user_id[:8]}] 已重設課程 {course.alias} 的加選次數（原 {mem_count}）")
                    self._limit_notified_at.pop((user_id, identifier), None)
                ea[identifier] = 0
            else:
                ea[identifier] = max(mem_count, db_count)
            course.attempt_count = ea[identifier]

    def _persist_attempt_count(self, course: CourseConfig, attempts: int) -> None:
        """Override: 把嘗試次數寫回 monitored_courses.attempt_count，worker 重啟不歸零。"""
        course.attempt_count = attempts
        if not getattr(course, 'db_id', None):
            return
        try:
            self._db_update_with_retry('monitored_courses', {'attempt_count': attempts}, 'id', course.db_id)
        except Exception as e:
            logger.error(f"寫入加選次數失敗 {course.alias}：{e}")

    def _handle_enroll_success(self, course: CourseConfig) -> None:
        """Override to update Supabase when enrollment succeeds"""
        course.auto_enroll = False
        
        if hasattr(course, 'db_id'):
            try:
                logger.info(f"🎉 加選成功：{course.alias}，已關閉自動加選")
                self._db_update_with_retry('monitored_courses', {
                    'auto_enroll': False,
                    'status': 'enrolled'
                }, 'id', course.db_id)
            except Exception as e:
                logger.error(f"更新加選狀態失敗 {course.alias}：{e}")
    
    def _handle_duplicate_or_ineligible(self, course: CourseConfig) -> None:
        """
        Override: duplicate/ineligible terminal state.
        僅停用自動加選，不將課程標記為 enrolled。
        """
        course.auto_enroll = False
        if hasattr(course, 'db_id'):
            try:
                self._db_update_with_retry('monitored_courses', {
                    'auto_enroll': False
                }, 'id', course.db_id)
            except Exception as e:
                logger.error(f"更新終態停用失敗 {course.alias}：{e}")

    def _build_proxies(self, user_data: Dict) -> Optional[Dict]:
        """Build a requests-compatible proxies dict from user proxy settings."""
        if not user_data.get('proxy_enabled'):
            return None
        proxy_type = user_data.get('proxy_type', 'socks5').lower()
        host = user_data.get('proxy_host', '').strip()
        port = user_data.get('proxy_port', '').strip()
        if not host or not port:
            return None
        username = user_data.get('proxy_username', '').strip()
        password = user_data.get('proxy_password', '').strip()
        if username and password:
            auth = f"{username}:{password}@"
        else:
            auth = ''
        proxy_url = f"{proxy_type}://{auth}{host}:{port}"
        return {'http': proxy_url, 'https': proxy_url}

    def _write_log(self, message: str, level: str = "info", user_id: Optional[str] = None) -> None:
        """Write a message directly to system_logs for the Live Console."""
        target_user_id = self._resolve_log_user_id(user_id)
        if not target_user_id:
            return
        if not self._insert_system_log(target_user_id, level, message):
            logger.warning(f"寫入即時日誌失敗（uid={target_user_id[:8]}）")

    def _send_heartbeat(self):
        """Send a heartbeat log to indicate worker is alive"""
        try:
            target_user_id = self._resolve_log_user_id()
            if target_user_id:
                self._insert_system_log(target_user_id, 'heartbeat', 'ping')
        except Exception:
            pass # Ignore heartbeat errors

    def resolve_pending_courses(self) -> int:
        """Query NTUST API for any pending courses and fill in course name/enrollment."""
        try:
            pending_resp = self.supabase.table('monitored_courses').select('*').eq('status', 'pending').execute()
            if not pending_resp.data:
                return 0

            logger.info(f"發現 {len(pending_resp.data)} 門待處理課程，正在查詢資訊...")

            # 依各使用者的 verify_ssl 設定建立查詢 client（不再寫死關閉 TLS 驗證）
            verify_ssl_by_user = {
                u.get('user_id'): bool(u.get('verify_ssl', True)) for u in self.users_data if u.get('user_id')
            }
            api_by_verify: Dict[bool, NTUSTCourseAPI] = {}

            for course_data in pending_resp.data:
                course_code = course_data.get('course_code', '').strip()
                if not course_code:
                    continue
                try:
                    verify_ssl = verify_ssl_by_user.get(course_data.get('user_id'), True)
                    api = api_by_verify.get(verify_ssl)
                    if api is None:
                        api = api_by_verify[verify_ssl] = NTUSTCourseAPI(verify_ssl=verify_ssl)
                    c = api.get_course_by_code(course_code, semester=course_data.get('semester') or '', course_name=course_data.get('course_name') or '')
                    if c:
                        restrict1 = c.get('Restrict1', '')
                        chosen = c.get('ChooseStudent', 0)
                        enrolled_str = (
                            f"{chosen}/{restrict1}"
                            if restrict1 and restrict1 != '9999'
                            else str(chosen if chosen is not None else '---')
                        )
                        update_data = {
                            'course_name': c.get('CourseName', course_code),
                            'current_enrolled': enrolled_str,
                            'status': 'monitoring',
                            'last_check_time': datetime.now(timezone.utc).isoformat()
                        }
                        c_semester = (c.get('Semester') or '').strip()
                        if c_semester:
                            update_data['semester'] = c_semester
                        self._db_update_with_retry('monitored_courses', update_data, 'id', course_data['id'])
                        logger.info(f"  解析完成：{course_code} → {c.get('CourseName', course_code)}（{enrolled_str}）")
                    else:
                        logger.warning(f"  找不到課程：{course_code}")
                except Exception as e:
                    logger.error(f"  解析課程失敗 {course_code}：{e}")
            return len(pending_resp.data)
        except Exception as e:
            logger.error(f"待處理課程查詢失敗：{e}")
        return 0

    def _log_separator(self, label: str = "") -> None:
        line = "─" * 60
        if label:
            msg = f"┤ {label} ├"
            pad = (60 - len(msg)) // 2
            line = "─" * pad + msg + "─" * (60 - pad - len(msg))
        logger.info(line)

    def _start_user_worker(self, user_id: str) -> None:
        if user_id in self._user_workers:
            return
        stop_event = threading.Event()
        t = threading.Thread(
            target=self._run_user_loop,
            args=(user_id, stop_event),
            daemon=True,
            name=f"UserWorker-{user_id[:8]}",
        )
        self._user_workers[user_id] = {"thread": t, "stop_event": stop_event}
        t.start()
        logger.info(f"[manager] 已啟動使用者執行緒: {user_id[:8]}")

    def _stop_user_worker(self, user_id: str) -> None:
        worker = self._user_workers.get(user_id)
        if not worker:
            return
        worker["stop_event"].set()
        worker["thread"].join(timeout=5)
        self._user_workers.pop(user_id, None)
        logger.info(f"[manager] 已停止使用者執行緒: {user_id[:8]}")

    def _run_user_loop(self, user_id: str, stop_event: threading.Event) -> None:
        """Per-user dedicated loop; isolated monitor instance to prevent cross-user interference."""
        user_monitor = SupabaseMonitor(self.supabase_url, self.supabase_key)
        uid_short = user_id[:8]
        HEARTBEAT_INTERVAL = 60
        CONFIG_REFRESH_INTERVAL = 10
        next_check_at = 0.0
        last_heartbeat_at = 0.0
        last_config_fetch_at = 0.0
        cached_user_data: Optional[Dict[str, Any]] = None

        def _wait(seconds: float) -> bool:
            """Wait and return True if stop requested."""
            return stop_event.wait(timeout=max(0.1, seconds))

        try:
            while not stop_event.is_set():
                now = time.time()

                if (now - last_config_fetch_at) >= CONFIG_REFRESH_INTERVAL or cached_user_data is None:
                    if not user_monitor.fetch_config():
                        logger.warning(f"[{uid_short}] 讀取設定失敗，3 秒後重試")
                        if _wait(3):
                            break
                        continue
                    cached_user_data = next((u for u in user_monitor.users_data if u.get('user_id') == user_id), None)
                    last_config_fetch_at = now

                if cached_user_data is None:
                    if _wait(2):
                        break
                    continue

                if now - last_heartbeat_at >= HEARTBEAT_INTERVAL:
                    try:
                        # Piggyback the latest school-API latency on the heartbeat so the
                        # dashboard can show it without a separate (noisy) log row.
                        api_latency_ms = getattr(user_monitor.api, 'last_request_latency_ms', None)
                        hb_msg = 'ping'
                        if api_latency_ms is not None:
                            hb_msg = f"ping 延遲指標：學校系統 {api_latency_ms:.0f}ms"
                        user_monitor._insert_system_log(user_id, 'heartbeat', hb_msg)
                    except Exception:
                        pass
                    last_heartbeat_at = now

                if not cached_user_data.get('is_active') or not cached_user_data.get('courses'):
                    next_check_at = 0.0
                    if _wait(1.5):
                        break
                    continue

                if now < next_check_at:
                    heartbeat_wait = HEARTBEAT_INTERVAL - (now - last_heartbeat_at)
                    wait_s = min(next_check_at - now, max(0.5, heartbeat_wait))
                    if _wait(wait_s):
                        break
                    continue

                user_monitor.user_id = user_id
                user_monitor.config.student_id = cached_user_data.get('student_id')
                user_monitor.config.student_password = cached_user_data.get('student_password')
                user_monitor.config.courses = cached_user_data.get('courses', [])
                user_monitor.config.check_interval = cached_user_data.get('check_interval', 30.0)
                user_monitor.enrollment_open_start = cached_user_data.get('enrollment_open_start')
                user_monitor.enrollment_open_end = cached_user_data.get('enrollment_open_end')
                user_monitor.enrollment_period = cached_user_data.get('enrollment_period', 'A06')

                verify_ssl = cached_user_data.get('verify_ssl', True)
                user_monitor.api.verify_ssl = verify_ssl

                proxies = user_monitor._build_proxies(cached_user_data)
                user_monitor.api.session.proxies = proxies or {}
                n_courses = len(user_monitor.config.courses)
                if proxies:
                    proxy_url = list(proxies.values())[0]
                    pw = cached_user_data.get('proxy_password', '')
                    display_url = proxy_url.replace(pw, '***') if pw else proxy_url
                    start_msg = f"使用代理 {display_url}，開始檢查 {n_courses} 門課程..."
                else:
                    start_msg = f"直接連線，開始檢查 {n_courses} 門課程..."
                logger.info(f"[{uid_short}] {start_msg}")

                if user_id in user_monitor.enrollment_clients_per_user:
                    user_monitor.enrollment_client = user_monitor.enrollment_clients_per_user[user_id]
                    user_monitor.enrollment_client.verify_ssl = verify_ssl
                    user_monitor.enrollment_client.session.proxies = proxies or {}
                else:
                    user_monitor.enrollment_client = EnrollmentClient(verify_ssl=verify_ssl)
                    if proxies:
                        user_monitor.enrollment_client.session.proxies = proxies
                    user_monitor.enrollment_client.on_login_pause = (
                        lambda until, reason, _uid=user_id: user_monitor._set_login_pause(_uid, until, reason)
                    )
                    user_monitor.enrollment_client.seed_login_cooldown(
                        _parse_ts(cached_user_data.get('login_paused_until'))
                    )
                    user_monitor.enrollment_clients_per_user[user_id] = user_monitor.enrollment_client

                user_monitor.enrollment_attempts = user_monitor.enrollment_attempts_per_user.get(user_id, {})
                user_monitor.course_states = user_monitor.course_states_per_user.get(user_id, {})

                loop_start = time.time()
                user_monitor.check_all_courses(silent=True)
                user_monitor.enrollment_attempts_per_user[user_id] = user_monitor.enrollment_attempts
                user_monitor.course_states_per_user[user_id] = user_monitor.course_states

                elapsed = time.time() - loop_start
                base_interval = float(cached_user_data.get('check_interval', 30.0))
                rand_range = float(cached_user_data.get('random_interval', 0) or 0)
                jitter = random.uniform(-rand_range, rand_range) if rand_range > 0 else 0
                interval = max(1.0, base_interval + jitter)
                next_check_at = loop_start + interval
                next_time_str = datetime.fromtimestamp(next_check_at).strftime('%H:%M:%S')
                jitter_str = f"（基礎{base_interval:.0f}s ± 隨機{rand_range:.0f}s）" if rand_range > 0 else ""
                summary_msg = f"耗時 {elapsed:.1f}s／間隔 {interval:.0f}s{jitter_str}／下次 {next_time_str}"
                logger.info(f"[{uid_short}] {summary_msg}")

                if _wait(0.2):
                    break
        except Exception as e:
            logger.error(f"[{uid_short}] 使用者執行緒異常: {e}", exc_info=True)
        finally:
            logger.info(f"[{uid_short}] 使用者執行緒結束")

    def run_loop(self):
        """Manager loop: maintain one dedicated worker thread per user."""
        self._log_separator("NTUST 課程監控 Worker 啟動（每位使用者獨立執行緒）")
        MANAGER_INTERVAL = 8
        should_exit = False

        while not should_exit:
            try:
                self.resolve_pending_courses()

                if not self.fetch_config():
                    logger.warning("[manager] 讀取設定失敗，10 秒後重試...")
                    try:
                        self._process_test_email_requests()
                    except Exception:
                        pass
                    time.sleep(10)
                    continue

                self._process_test_email_requests()

                configured_user_ids = {u.get('user_id') for u in self.users_data if u.get('user_id')}

                # 執行緒若因未捕捉例外結束，移出登記表讓下方邏輯重新啟動
                for uid, worker in list(self._user_workers.items()):
                    if not worker["thread"].is_alive():
                        logger.warning(f"[manager] 使用者 {uid[:8]} 的執行緒已停止，將重新啟動")
                        self._user_workers.pop(uid, None)

                running_user_ids = set(self._user_workers.keys())

                for uid in configured_user_ids - running_user_ids:
                    self._start_user_worker(uid)
                for uid in running_user_ids - configured_user_ids:
                    self._stop_user_worker(uid)

                active_monitoring_users = sum(1 for u in self.users_data if u.get('is_active') and u.get('courses'))
                total_courses = sum(len(u.get('courses') or []) for u in self.users_data)
                logger.info(
                    f"[manager] 使用者 {len(self.users_data)} 位，監控中 {active_monitoring_users} 位，"
                    f"課程 {total_courses} 門，執行緒 {len(self._user_workers)} 條"
                )
                time.sleep(MANAGER_INTERVAL)

            except KeyboardInterrupt:
                logger.info("使用者中止，正在停止所有使用者執行緒...")
                should_exit = True
            except Exception as e:
                logger.error(f"[manager] 主循環發生錯誤：{e}", exc_info=True)
                time.sleep(10)

        for uid in list(self._user_workers.keys()):
            self._stop_user_worker(uid)

if __name__ == "__main__":
    # Supabase 設定以 backend/config.py 為單一來源（worker 已在 import 前 load_dotenv）。
    # 缺 service role key 直接失敗：退回 anon key 會讓 app_private 讀取與 session 寫入靜默失敗。
    from ..config import SUPABASE_URL as CFG_SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY as CFG_SERVICE_KEY
    from ..credentials import _is_placeholder

    SUPABASE_URL = CFG_SUPABASE_URL or (os.getenv("VITE_SUPABASE_URL") or "").rstrip("/")
    if not SUPABASE_URL:
        logger.error("缺少 SUPABASE_URL（或 VITE_SUPABASE_URL），請在 .env 設定")
        sys.exit(1)
    if _is_placeholder(CFG_SERVICE_KEY):
        logger.error("缺少 SUPABASE_SERVICE_ROLE_KEY：worker 需要服務金鑰才能讀 app_private 與寫入 session，不再退回匿名金鑰")
        sys.exit(1)

    logger.info("使用服務金鑰（管理員權限）")
    monitor = SupabaseMonitor(SUPABASE_URL, CFG_SERVICE_KEY)
    monitor.run_loop()
