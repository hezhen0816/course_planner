"""
課程監控核心邏輯
定期查詢課程選課人數並比較變化
"""

import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo

# Thread-local storage：讓加選執行緒在呼叫通知方法時，
# 傳遞正確的 user_id，避免被主迴圈覆蓋造成 Race Condition。
_enroll_thread_local = threading.local()

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .api_client import NTUSTCourseAPI
from .config import ConfigManager, CourseConfig, MonitorConfig
from .enrollment import EnrollmentClient
from .utils import setup_logging

# 設置日誌
logger = setup_logging()

console = Console()


class CourseMonitor:
    """課程監控器"""
    
    def __init__(self, config: MonitorConfig, config_manager: Optional[ConfigManager] = None):
        self.config = config
        self.config_manager = config_manager  # 用於熱重載配置
        # 使用配置中的 verify_ssl 設定，如果沒有則使用預設值（None，會自動判斷）
        # 代理配置會從環境變數自動讀取
        self.api = NTUSTCourseAPI(verify_ssl=config.verify_ssl)
        self.enrollment_client = EnrollmentClient(verify_ssl=config.verify_ssl)
        self.course_states: Dict[str, Dict] = {}  # 儲存每個課程的狀態
        self.notifications: list = []  # 儲存名額通知列表
        self.system_notifications: list = []  # 儲存系統通知列表
        # 從配置中讀取通知數量限制
        self.max_notifications = config.max_notifications if hasattr(config, 'max_notifications') else 6
        self.max_system_notifications = config.max_system_notifications if hasattr(config, 'max_system_notifications') else 20
        self.enrollment_attempts: Dict[str, int] = {}  # 記錄每個課程的加選嘗試次數
        
        # 記錄上次檢查配置文件的時間
        self.last_config_check_time = 0
        # 從配置中讀取配置文件檢查間隔
        self.config_check_interval = config.config_check_interval if hasattr(config, 'config_check_interval') else 5
        
        # Session 保活相關
        self.last_session_check = 0  # 上次檢查 session 的時間
        self.session_check_interval = 180  # 每 3 分鐘檢查一次 session（秒）- 更頻繁檢查
        self.last_session_keepalive = 0  # 上次保持 session 活躍的時間
        self.session_keepalive_interval = 120  # 每 2 分鐘保持一次 session 活躍（秒）- 更頻繁保活
        
        # 加選線程鎖（per-user，確保同一使用者的加選過程線程安全，不阻塞其他使用者）
        self._enroll_locks: Dict[str, threading.Lock] = {}
        self._enroll_locks_guard = threading.Lock()  # 保護 _enroll_locks dict 本身
        # 狀態線程鎖（保護共享狀態：course_states, notifications, system_notifications, enrollment_attempts）
        self.state_lock = threading.Lock()
        
        # 執行緒池與任務追蹤
        self._enroll_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="EnrollWorker")
        self._active_enroll_tasks = set()
        self._active_tasks_lock = threading.Lock()
        # 記錄最近「終態」時間（成功或已在選課清單），避免同步延遲造成重複送單
        self._recent_enroll_terminal: Dict[tuple, float] = {}
        self._limit_notified_at: Dict[tuple, float] = {}
        # 查詢失敗節流：連續失敗只在第一次與每 QUERY_FAIL_LOG_INTERVAL 秒寫一次即時日誌
        self._query_fail_since: Dict[str, float] = {}
        self._query_fail_last: Dict[str, float] = {}
        self._query_fail_last_logged: Dict[str, float] = {}
    
    QUERY_FAIL_LOG_INTERVAL = 300   # seconds between repeated failure log lines
    QUERY_FAIL_STREAK_GAP = 120     # a failure within this many seconds of the last one is the same streak

    def _should_log_query_failure(self, identifier: str) -> bool:
        """Return True if this failure should reach the live log.

        Failures for a course form a streak as long as they are at most
        QUERY_FAIL_STREAK_GAP seconds apart (intermittent timeouts during school
        congestion count as one streak). Log the first failure of a streak, then
        at most once per QUERY_FAIL_LOG_INTERVAL.
        """
        now = time.time()
        with self.state_lock:
            last_fail = self._query_fail_last.get(identifier)
            in_streak = last_fail is not None and (now - last_fail) <= self.QUERY_FAIL_STREAK_GAP
            self._query_fail_last[identifier] = now
            if not in_streak:
                self._query_fail_since[identifier] = now
                self._query_fail_last_logged[identifier] = now
                return True
            if now - self._query_fail_last_logged.get(identifier, 0) >= self.QUERY_FAIL_LOG_INTERVAL:
                self._query_fail_last_logged[identifier] = now
                return True
            return False

    def _note_query_success(self, identifier: str) -> Optional[float]:
        """Called on a successful query. If a streak has been quiet for
        QUERY_FAIL_STREAK_GAP seconds it is over: clear it and return its duration."""
        now = time.time()
        with self.state_lock:
            last_fail = self._query_fail_last.get(identifier)
            if last_fail is None:
                return None
            if now - last_fail < self.QUERY_FAIL_STREAK_GAP:
                return None  # still inside the streak window; wait for more successes
            since = self._query_fail_since.pop(identifier, last_fail)
            self._query_fail_last.pop(identifier, None)
            self._query_fail_last_logged.pop(identifier, None)
        return max(0.0, last_fail - since)

    def _get_course_identifier(self, course: CourseConfig) -> str:
        """取得課程唯一識別碼"""
        return course.course_no or course.course_name or course.alias
    
    def _pre_login_if_needed(self) -> bool:
        """
        如果需要，預先登入以保持 session 活躍
        
        Returns:
            bool: 是否成功登入或已經登入
        """
        if not self.config.student_id or not self.config.student_password:
            return False
        
        if not self.enrollment_client.is_logged_in:
            uid_tag = (getattr(self, "user_id", None) or "")[:8]
            logger.info(f"[{uid_tag}] 預先登入以保持 session 活躍...")
            success, msg = self.enrollment_client.login(
                self.config.student_id,
                self.config.student_password
            )
            if success:
                logger.info(f"[{uid_tag}] 預先登入成功，session 已準備就緒")
                self.last_session_check = time.time()
                self.last_session_keepalive = time.time()
            else:
                logger.warning(f"[{uid_tag}] 預先登入失敗: {msg}")
            return success
        return True
    
    def _keep_session_alive(self) -> None:
        """
        保持 session 活躍，定期檢查並刷新 session

        與加選執行緒共用同一個 requests.Session；取得該使用者的加選鎖後才動 session，
        避免 keepalive 的重新登入與加選中的登入互相覆蓋 cookie。鎖被佔用時本輪略過。
        """
        lock_key = getattr(self, 'user_id', None) or '__default__'
        with self._enroll_locks_guard:
            if lock_key not in self._enroll_locks:
                self._enroll_locks[lock_key] = threading.Lock()
            enroll_lock = self._enroll_locks[lock_key]
        if not enroll_lock.acquire(blocking=False):
            logger.debug("加選進行中，略過本輪 session 保活")
            return
        try:
            self._keep_session_alive_locked()
        finally:
            enroll_lock.release()

    def _keep_session_alive_locked(self) -> None:
        current_time = time.time()
        
        # 每隔一定時間檢查一次 session
        if current_time - self.last_session_check > self.session_check_interval:
            if not self.enrollment_client.is_logged_in:
                # Session 已失效，嘗試重新登入
                self._pre_login_if_needed()
            else:
                # 快速檢查 session 是否還有效
                if not self.enrollment_client._check_session_quick():
                    # Session 已失效，重新登入
                    logger.warning("Session 已失效，正在重新登入...")
                    self._pre_login_if_needed()
            self.last_session_check = current_time
        
        # 每隔一定時間保持 session 活躍（輕量級訪問）
        if current_time - self.last_session_keepalive > self.session_keepalive_interval:
            if self.enrollment_client.is_logged_in:
                if not self.enrollment_client._keep_session_alive():
                    # 保持活躍失敗，立即嘗試重新登入
                    logger.warning("保持 session 活躍失敗，立即嘗試重新登入...")
                    self.enrollment_client.is_logged_in = False
                    # 立即嘗試重新登入
                    if self.config.student_id and self.config.student_password:
                        self._pre_login_if_needed()
            else:
                # 如果未登入，嘗試登入
                if self.config.student_id and self.config.student_password:
                    self._pre_login_if_needed()
            self.last_session_keepalive = current_time
    
    def _query_course(self, course: CourseConfig) -> Optional[Dict]:
        """查詢單一課程資訊"""
        identifier = self._get_course_identifier(course)
        # 檢查之前是否成功查詢過這個課程（用於判斷是否是網路問題）
        previous_state = self.course_states.get(identifier)
        had_previous_success = previous_state is not None and previous_state.get("course_info") is not None
        
        try:
            if course.course_no:
                # 使用課程代碼查詢
                # 確保傳入有效的顯示名稱
                display_name = course.course_name or course.alias or 'N/A'
                # logger.debug(f"Querying course: no={course.course_no}, name={course.course_name}, alias={course.alias}, display={display_name}")
                
                course_info = self.api.get_course_by_code(
                    course.course_no,
                    course.semester,
                    course_name=display_name
                )
            elif course.course_name:
                # 使用課程名稱查詢（可能有多個結果）
                courses = self.api.get_courses_by_name(
                    course.course_name,
                    course.semester
                )
                if courses:
                    # 如果有多個，返回第一個
                    course_info = courses[0]
                else:
                    course_info = None
            else:
                return None
            
            # 如果之前成功查詢過，但現在返回 None，很可能是網路問題
            # 需要主動檢測網路狀態
            if course_info is None and had_previous_success:
                # 嘗試檢測是否是網路問題
                # 由於 search_courses 可能返回空列表而不是拋出異常，
                # 我們需要主動檢測網路狀態
                is_network_down = False
                try:
                    import socket
                    # 嘗試連接一個已知的 IP 來檢測網路
                    socket.create_connection(("8.8.8.8", 53), timeout=2)
                except (socket.error, OSError, Exception) as net_err:
                    # 網路確實中斷了
                    is_network_down = True
                    error_msg = f"查詢課程 {course.alias} 失敗：當前網路已中斷，請檢查網路連接"
                    logger.error(f"查詢課程 {course.alias} 失敗：當前網路已中斷 - {net_err}")
                    self._add_system_notification(error_msg, level="error")
                    return {"_network_error": True}
                
                # 如果網路連接正常，但查詢返回 None，可能是其他問題
                # 但為了保險起見，我們也檢查一下是否能連接到目標服務器
                if not is_network_down:
                    try:
                        import socket
                        # 嘗試解析目標域名
                        socket.gethostbyname("api.ntust.edu.tw")
                    except (socket.error, OSError, Exception) as dns_err:
                        # DNS 解析失敗，可能是網路問題
                        error_msg = f"查詢課程 {course.alias} 失敗：當前網路已中斷，請檢查網路連接"
                        logger.error(f"查詢課程 {course.alias} 失敗：DNS 解析失敗，網路可能已中斷 - {dns_err}")
                        self._add_system_notification(error_msg, level="error")
                        return {"_network_error": True}
            
            return course_info
        except Exception as e:
            from .utils import _is_network_disconnected
            # 檢查是否是網路中斷錯誤
            error_str = str(e)
            is_disconnected = _is_network_disconnected(e)
            if is_disconnected:
                error_msg = f"查詢課程 {course.alias} 失敗：當前網路已中斷，請檢查網路連接"
                logger.error(f"查詢課程 {course.alias} 時發生錯誤：當前網路已中斷 - {e}")
                # 直接添加系統通知，確保訊息能顯示
                self._add_system_notification(error_msg, level="error")
                # 返回特殊標記，表示是網路錯誤，避免 check_course 再添加警告
                return {"_network_error": True}
            elif 'gaierror' in error_str.lower():
                error_msg = f"查詢課程 {course.alias} 時發生網路錯誤（可能是代理配置問題）: {e}"
                logger.error(f"查詢課程 {course.alias} 時發生錯誤: {e}")
                logger.debug(f"錯誤類型: {type(e)}, 錯誤詳情: {error_str}")
                self._add_system_notification(error_msg, level="error")
                return {"_network_error": True}
            else:
                error_msg = f"查詢課程 {course.alias} 時發生錯誤: {e}"
                logger.error(f"查詢課程 {course.alias} 時發生錯誤: {e}")
                if self._should_log_query_failure(identifier):
                    self._add_system_notification(error_msg, level="error")
            return None
    
    def check_course(self, course: CourseConfig) -> bool:
        """
        檢查單一課程的選課人數
        
        此方法會：
        1. 查詢課程當前選課人數
        2. 與上次記錄比較，判斷是否有變化
        3. 如果有名額變化，發送通知
        4. 如果啟用自動加選且有名額，嘗試加選
        
        Args:
            course: 課程配置對象，包含課程代碼、名稱、學年期等信息
        
        Returns:
            bool: 是否成功查詢到課程資訊
                - True: 成功查詢並更新狀態
                - False: 查詢失敗（課程不存在、網絡錯誤等）
        
        Note:
            - 如果課程資訊查詢失敗，會添加系統通知
            - 自動加選邏輯會在此方法中觸發（如果滿足條件）
            - 課程狀態會更新到 course_states 字典中
        """
        identifier = self._get_course_identifier(course)
        course_info = self._query_course(course)
        
        # 檢查是否是網路錯誤標記（_query_course 返回 {"_network_error": True}）
        if isinstance(course_info, dict) and course_info.get("_network_error"):
            # 網路錯誤已由 _query_course 處理並添加通知，直接返回
            return False
        
        if not course_info:
            # 查詢失敗但不是網路錯誤（含逾時）；連續失敗只節流寫入即時日誌
            if self._should_log_query_failure(identifier):
                self._add_system_notification(f"無法取得課程資訊: {course.alias}", level="warning")
            return False
            
        # 如果課程名稱為空，嘗試從查詢結果中更新
        if not course.course_name and course_info.get('CourseName'):
            course.course_name = course_info.get('CourseName')
            # 如果別名就是課程代碼，也更新別名
            if course.alias == course.course_no:
                course.alias = course.course_name
        
        current_count = course_info.get("ChooseStudent", 0)
        # 防護：API 可能回傳 null，dict.get() 會回傳 None（key 存在但值為 null）
        if current_count is None:
            current_count = 0
        try:
            current_count = int(current_count)
        except (ValueError, TypeError):
            current_count = 0
        current_time = datetime.now()
        
        # 使用鎖保護共享狀態的讀取和更新
        with self.state_lock:
            # 取得上次記錄的狀態（複製需要的值）
            previous_state = self.course_states.get(identifier)
            previous_count = previous_state.get("count") if previous_state else None
            
            # 讀取自動加選嘗試次數
            attempts = self.enrollment_attempts.get(identifier, 0)
            
            # 更新狀態
            self.course_states[identifier] = {
                "course": course,
                "count": current_count,
                "last_check": current_time,
                "course_info": course_info,
                "previous_count": previous_count
            }
        
        # 在鎖外計算通知和加選邏輯（避免長時間持有鎖）
        # 檢查剩餘名額變化，只在變化時發送通知
        restrict1 = course_info.get('Restrict1', '')
        should_notify = False
        can_try_auto_enroll = False
        previous_remaining = None
        
        # Restrict1 為空或 9999 代表無人數上限：不做名額通知，但仍允許自動加選
        is_unlimited = not restrict1 or str(restrict1).strip() in ('', '9999')
        if is_unlimited:
            remaining = 1  # 恆視為有名額
        else:
            try:
                restrict1_int = int(restrict1)
            except (ValueError, TypeError):
                logger.warning(f"課程 {course.alias} 的 Restrict1 值無法解析為數字: {restrict1!r}")
                return True
            remaining = restrict1_int - current_count
            
            # 取得上次的剩餘名額
            if previous_count is not None:
                previous_remaining = restrict1_int - previous_count
            
            # 只在名額發生變化時發送通知
            # 1. 第一次檢查（previous_remaining 為 None）
            # 2. 剩餘名額從 0 變為 > 0（從額滿變為有名額）
            # 3. 剩餘名額數量變化（且 > 0）
            if previous_remaining is None:
                # 第一次檢查，如果有剩餘名額就通知
                if remaining > 0:
                    should_notify = True
            elif previous_remaining != remaining:
                # 名額發生變化
                if remaining > 0:
                    # 只有當剩餘名額 > 0 時才通知
                    should_notify = True
                elif previous_remaining > 0 and remaining == 0:
                    # 從有名額變為額滿，也通知
                    should_notify = True
            
            # 發送通知
            if should_notify:
                self._add_notification(course, current_count, course_info, previous_remaining)
            
        # 自動加選邏輯：簡化觸發條件，確保一有空位就立即加選
        if course.auto_enroll and remaining > 0:
            reached_limit = attempts >= course.max_enroll_attempts
            can_try_auto_enroll = not reached_limit
            # 終態冷卻：若剛完成成功/已在選課清單，短時間內不重複送單
            user_id_for_key = getattr(self, 'user_id', None) or ''
            term_key = (user_id_for_key, identifier)
            with self.state_lock:
                terminal_at = self._recent_enroll_terminal.get(term_key, 0)
            in_terminal_cooldown = bool(terminal_at and (time.time() - terminal_at) < 20)
            if in_terminal_cooldown:
                can_try_auto_enroll = False
                logger.debug(f"課程 {course.alias} 處於終態冷卻期，略過重複加選")
            # 達到最大嘗試次數時顯示提示（節流：每 5 分鐘最多一次）
            if reached_limit:
                user_id = getattr(self, 'user_id', None) or ''
                limit_key = (user_id, identifier)
                limit_notified = getattr(self, '_limit_notified_at', {})
                now_ts = time.time()
                if limit_key not in limit_notified or (now_ts - limit_notified.get(limit_key, 0)) > 300:
                    self._add_system_notification(
                        f"已達最大嘗試次數：{course_info.get('CourseName', course.alias)} ({course_info.get('CourseNo', course.course_no)}) - {attempts}/{course.max_enroll_attempts}",
                        level="warning"
                    )
                    if not hasattr(self, '_limit_notified_at'):
                        self._limit_notified_at = {}
                    self._limit_notified_at[limit_key] = now_ts
            # 檢查自訂選課開放時間（台灣時間，含日期）：若已設定，僅在該時段內才送出加選請求
            if can_try_auto_enroll:
                start_str = getattr(self, 'enrollment_open_start', None)
                end_str = getattr(self, 'enrollment_open_end', None)
                if start_str and end_str:
                    try:
                        # 解析 datetime-local 格式：YYYY-MM-DDTHH:mm 或 YYYY-MM-DD HH:mm
                        def _parse_dt(s: str):
                            s = s.strip().replace(' ', 'T')
                            if 'T' not in s and len(s) >= 10:
                                s = s[:10] + 'T' + (s[10:].strip() if len(s) > 10 else '00:00')
                            dt = datetime.fromisoformat(s)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=ZoneInfo('Asia/Taipei'))
                            return dt
                        start_dt = _parse_dt(start_str)
                        end_dt = _parse_dt(end_str)
                        now_tw = datetime.now(ZoneInfo('Asia/Taipei'))
                        within = start_dt <= now_tw <= end_dt
                        if not within:
                            can_try_auto_enroll = False
                            logger.debug(f"非選課開放時段（台灣時間 {start_str}–{end_str}），跳過加選")
                    except (ValueError, IndexError) as e:
                        logger.debug(f"解析選課開放時間失敗: {e}")
            if can_try_auto_enroll:
                # 快照以下所有值，避免主迴圈切換使用者後被覆蓋（Race Condition）：
                # - student_id / student_password / enroll_client：帳密與 session
                # - user_id：通知要寫入的 Supabase 使用者 ID
                # - enrollment_attempts：此使用者的加選嘗試次數字典（傳參照，非 self.enrollment_attempts）
                # - use_add_drop：依設定選課時段（A06 / B01）決定
                use_add_drop = (getattr(self, 'enrollment_period', 'A06') == 'B01')
                self._try_auto_enroll_async(
                    course, course_info, identifier,
                    student_id=self.config.student_id,
                    student_password=self.config.student_password,
                    enroll_client=self.enrollment_client,
                    user_id=getattr(self, 'user_id', None),
                    enrollment_attempts=self.enrollment_attempts,
                    use_add_drop=use_add_drop,
                )
    
        return True
    
    def _try_auto_enroll_async(
        self,
        course: CourseConfig,
        course_info: Dict,
        identifier: str,
        student_id: str,
        student_password: str,
        enroll_client,
        user_id: Optional[str] = None,
        enrollment_attempts: Optional[Dict] = None,
        use_add_drop: bool = False,
    ) -> None:
        """
        異步執行加選（不阻塞監控循環）

        所有可能被主迴圈覆蓋的 instance 變數都必須在呼叫時傳入快照：
        - student_id / student_password / enroll_client：帳密與 session
        - user_id：用於將通知寫入正確使用者的 system_logs
        - enrollment_attempts：此使用者的加選嘗試次數字典（傳參照）
        - use_add_drop：True 使用加退選 (B01)，False 使用電腦抽選後選課 (A06)
        """
        # enrollment_attempts 若未傳入，退回 self.enrollment_attempts（單使用者相容）
        ea = enrollment_attempts if enrollment_attempts is not None else self.enrollment_attempts
        
        task_key = (user_id, identifier)
        with self._active_tasks_lock:
            if task_key in self._active_enroll_tasks:
                logger.debug(f"加選任務已在執行中，略過重複提交: {course.alias} ({identifier})")
                return
            self._active_enroll_tasks.add(task_key)
            
        self._enroll_executor.submit(
            self._try_auto_enroll,
            course, course_info, identifier, student_id, student_password, enroll_client, user_id, ea, use_add_drop
        )
        logger.info(f"已提交異步加選任務: {course.alias} ({identifier})")
    
    def _try_auto_enroll(
        self,
        course: CourseConfig,
        course_info: Dict,
        identifier: str,
        student_id: str,
        student_password: str,
        enroll_client,
        user_id: Optional[str] = None,
        enrollment_attempts: Optional[Dict] = None,
        use_add_drop: bool = False,
    ) -> None:
        """
        嘗試自動加選課程（在獨立執行緒中執行）

        重要提醒：請遵守學校選課公平原則，系統已內建速率限制

        所有值均來自呼叫時的快照，不讀取 self.config / self.enrollment_attempts / self.user_id，
        以防止多使用者環境下的 Race Condition。
        """
        # 將 user_id 存入 thread-local，讓 _add_system_notification 的 override 能取得正確的使用者
        if user_id is not None:
            _enroll_thread_local.user_id = user_id

        # 使用傳入的 enrollment_attempts 字典（同一物件，非 self.enrollment_attempts）
        ea = enrollment_attempts if enrollment_attempts is not None else self.enrollment_attempts
        
        def _emit_enroll_log(msg: str, notify_level: str, log_level: str) -> None:
            """Best-effort: notify first; fallback to direct log write only on failure."""
            try:
                self._add_system_notification(msg, level=notify_level)
            except Exception as e:
                logger.error(f"寫入加選通知失敗: {e}")
                write_log = getattr(self, '_write_log', None)
                if callable(write_log):
                    try:
                        write_log(msg, level=log_level, user_id=user_id)
                    except Exception as e2:
                        logger.error(f"寫入加選保底日誌失敗: {e2}")

        try:
            # 檢查課程是否啟用自動加選
            if not course.auto_enroll:
                return

            # 檢查是否已超過最大嘗試次數
            with self.state_lock:
                attempts = ea.get(identifier, 0)
            if attempts >= course.max_enroll_attempts:
                self._add_system_notification(
                    f"已達最大嘗試次數：{course_info.get('CourseName', course.course_name)} ({course_info.get('CourseNo', course.course_no)}) - {attempts}/{course.max_enroll_attempts}",
                    level="warning"
                )
                return

            # 檢查學號和密碼（使用快照值，非 self.config）
            if not student_id:
                self._add_system_notification(
                    f"無法加選：{course_info.get('CourseName', course.course_name)} ({course_info.get('CourseNo', course.course_no)}) - 未設定學號",
                    level="error"
                )
                return

            if not student_password:
                self._add_system_notification(
                    f"無法加選：{course_info.get('CourseName', course.course_name)} ({course_info.get('CourseNo', course.course_no)}) - 未設定密碼（請設定環境變數 NTUST_STUDENT_PASSWORD）",
                    level="error"
                )
                return

            # 取得此使用者專屬的加選鎖（避免跨使用者互相阻塞）
            lock_key = user_id or '__default__'
            with self._enroll_locks_guard:
                if lock_key not in self._enroll_locks:
                    self._enroll_locks[lock_key] = threading.Lock()
                enroll_lock = self._enroll_locks[lock_key]

            # 確保 session 有效並執行加選（全部在 enroll_lock 內以避免並行 login 的 race condition）
            with enroll_lock:
                # 取得鎖後再次確認：前一個執行緒可能已加選成功或達到上限
                # （防止短間隔下多個加選執行緒排隊後重複送出）
                with self.state_lock:
                    current_attempts = ea.get(identifier, 0)

                if not course.auto_enroll:
                    logger.info(f"加選已被禁用（前一執行緒已成功），略過：{course.alias}")
                    return

                if current_attempts >= course.max_enroll_attempts:
                    logger.info(f"已達嘗試上限（前一執行緒已更新），略過：{course.alias} ({current_attempts}/{course.max_enroll_attempts})")
                    return

                # 在鎖內執行 login，避免多執行緒並行登入的 race condition
                if not enroll_client.is_logged_in:
                    logger.warning("加選前 session 無效，立即重新登入...")
                    login_success, login_msg = enroll_client.login(student_id, student_password)
                    if not login_success:
                        self._add_system_notification(
                            f"無法加選：{course_info.get('CourseName', course.course_name)} ({course_info.get('CourseNo', course.course_no)}) - 登入失敗: {login_msg}",
                            level="error"
                        )
                        return
                else:
                    # 即使 is_logged_in 為 True，也快速驗證一次（網站可能已自動登出）
                    if not enroll_client._check_session_quick():
                        logger.warning("加選前 session 檢查失敗，立即重新登入...")
                        login_success, login_msg = enroll_client.login(student_id, student_password)
                        if not login_success:
                            self._add_system_notification(
                                f"無法加選：{course_info.get('CourseName', course.course_name)} ({course_info.get('CourseNo', course.course_no)}) - 登入失敗: {login_msg}",
                                level="error"
                            )
                            return

                success, message = enroll_client.enroll_course(
                    course=course,
                    course_info=course_info,
                    student_id=student_id,
                    password=student_password,
                    use_add_drop=use_add_drop,
                )
                # 只在實際送出加選請求時才計入嘗試次數（速率限制導致的失敗不計入）
                is_rate_limited = not success and ('限制' in message or '間隔' in message)
                # 選課系統尚未開放時的失敗也不計入，否則開放前就會把 max_attempts 用光
                is_not_open = not success and any(
                    k in message for k in ('非電腦抽選後選課', '選課開放時間', '非選課開放時間')
                )
                if not is_rate_limited and not is_not_open:
                    with self.state_lock:
                        ea[identifier] = current_attempts + 1

                # 通知中的次數使用實際送出時的次數
            attempts = current_attempts

            # 若系統回覆「已在選課表/重複選課」，視為終態成功，避免繼續重試
            already_in_schedule_indicators = (
                '已經在您的選課表', '請勿重複選課', '重複選課'
            )
            already_completed_indicators = ('已經修過',)
            is_already_in_schedule = (not success) and any(k in message for k in already_in_schedule_indicators)
            is_already_completed = (not success) and any(k in message for k in already_completed_indicators)
            if is_already_in_schedule or is_already_completed:
                self._handle_duplicate_or_ineligible(course)
                with self.state_lock:
                    self._recent_enroll_terminal[(user_id or '', identifier)] = time.time()
                if is_already_in_schedule:
                    notify_msg = (
                        f"加選已完成：{course_info.get('CourseName', course.course_name)} "
                        f"({course_info.get('CourseNo', course.course_no)}) - 第 {attempts + 1} 次嘗試"
                        "（系統確認已在選課清單，已自動禁用該課程的自動加選）"
                    )
                    _emit_enroll_log(notify_msg, notify_level="success", log_level="success")
                else:
                    notify_msg = (
                        f"停止加選：{course_info.get('CourseName', course.course_name)} "
                        f"({course_info.get('CourseNo', course.course_no)}) - 第 {attempts + 1} 次嘗試 - "
                        "已修過該課，已自動禁用自動加選"
                    )
                    _emit_enroll_log(notify_msg, notify_level="warning", log_level="warn")
                return

            # 添加加選結果到系統通知
            if success:
                self._handle_enroll_success(course)
                with self.state_lock:
                    self._recent_enroll_terminal[(user_id or '', identifier)] = time.time()
                notify_msg = (
                    f"加選成功：{course_info.get('CourseName', course.course_name)} "
                    f"({course_info.get('CourseNo', course.course_no)}) - 第 {attempts + 1} 次嘗試，"
                    "已自動禁用該課程的自動加選"
                )
                _emit_enroll_log(notify_msg, notify_level="success", log_level="success")
            else:
                # 速率限制導致失敗時，不計入嘗試次數，通知顯示「等待重試」
                if is_rate_limited:
                    notify_msg = (
                        f"加選延遲：{course_info.get('CourseName', course.course_name)} "
                        f"({course_info.get('CourseNo', course.course_no)}) - 等待速率限制解除 - {message}"
                    )
                    _emit_enroll_log(notify_msg, notify_level="warning", log_level="warn")
                elif is_not_open:
                    notify_msg = (
                        f"尚未開放：{course_info.get('CourseName', course.course_name)} "
                        f"({course_info.get('CourseNo', course.course_no)}) - 選課系統未開放，不計入嘗試次數 - {message}"
                    )
                    _emit_enroll_log(notify_msg, notify_level="warning", log_level="warn")
                    # 借用終態冷卻，避免每個檢查週期都對學校送一次無效加選
                    with self.state_lock:
                        self._recent_enroll_terminal[(user_id or '', identifier)] = time.time()
                else:
                    notify_msg = (
                        f"加選失敗：{course_info.get('CourseName', course.course_name)} "
                        f"({course_info.get('CourseNo', course.course_no)}) - 第 {attempts + 1} 次嘗試 - {message}"
                    )
                    _emit_enroll_log(notify_msg, notify_level="error", log_level="error")

            # 如果因為速率限制失敗，添加額外延遲以避免過快重試
            if not success and ('限制' in message or '間隔' in message):
                time.sleep(5)
        except Exception as e:
            logger.error(f"加選執行緒發生未處理錯誤 ({course.alias}/{identifier}): {e}", exc_info=True)

        finally:
            # 清除 thread-local，避免記憶體洩漏
            if user_id is not None and hasattr(_enroll_thread_local, 'user_id'):
                del _enroll_thread_local.user_id
            
            # 從活躍任務集合中移除
            task_key = (user_id, identifier)
            with self._active_tasks_lock:
                if task_key in self._active_enroll_tasks:
                    self._active_enroll_tasks.remove(task_key)

    def _handle_enroll_success(self, course: CourseConfig) -> None:
        """處理加選成功後的邏輯（如禁用自動加選、更新配置）"""
        self._set_course_auto_enroll_disabled(course)
    
    def _handle_duplicate_or_ineligible(self, course: CourseConfig) -> None:
        """處理重複選課／已修過等終態（停用自動加選，但不標記為 enrolled）。"""
        self._set_course_auto_enroll_disabled(course)

    def _set_course_auto_enroll_disabled(self, course: CourseConfig) -> None:
        """停用課程自動加選並同步到配置。"""
        course.auto_enroll = False
        
        # 更新配置文件
        if self.config_manager:
            try:
                config = self.config_manager.load_config()
                # 找到對應的課程並更新
                for c in config.courses:
                    if (c.course_no == course.course_no and c.course_no) or \
                       (c.course_name == course.course_name and course.course_name and not c.course_no):
                        c.auto_enroll = False
                        break
                self.config_manager.save_config(config)
                # 更新當前配置
                self.config = config
            except Exception as e:
                logger.warning(f"無法更新配置文件以禁用自動加選: {e}")
    
    def check_all_courses(self, silent: bool = False) -> None:
        """檢查所有配置的課程（並行執行）"""
        if not self.config.courses:
            if not silent:
                console.print("[yellow]沒有配置任何監控課程[/yellow]")
            return
        
        # 保持 session 活躍（在檢查課程之前）
        self._keep_session_alive()
        
        if not silent:
            console.print(f"\n[dim][{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 開始並行檢查 {len(self.config.courses)} 個課程...[/dim]")
        
        # 使用線程池並行檢查所有課程
        with ThreadPoolExecutor(max_workers=min(len(self.config.courses), 10)) as executor:
            # 提交所有檢查任務
            future_to_course = {executor.submit(self.check_course, course): course for course in self.config.courses}
            
            # 等待所有任務完成
            for future in as_completed(future_to_course):
                course = future_to_course[future]
                try:
                    future.result()  # 獲取結果，如果有異常會在這裡拋出
                except Exception as e:
                    logger.error(f"檢查課程 {course.alias} 時發生異常: {e}")
                    self._add_system_notification(f"檢查課程 {course.alias} 時發生異常: {e}", level="error")
    
    def get_course_state(self, identifier: str) -> Optional[Dict]:
        """取得指定課程的狀態"""
        with self.state_lock:
            return self.course_states.get(identifier)
    
    def get_all_states(self) -> Dict[str, Dict]:
        """取得所有課程的狀態"""
        with self.state_lock:
            return self.course_states.copy()
    
    def _create_status_table(self) -> Table:
        """建立狀態表格"""
        # 取得當前時間
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 計算監控課程數（使用配置中的課程數，而不是已查詢到的狀態數）
        total_courses = len(self.config.courses)
        
        table = Table(
            title=f"課程選課人數監控 - {current_time} | 監控課程數: {total_courses}",
            show_header=True,
            header_style="bold magenta",
            box=None,
            border_style="blue",
            title_style="bold cyan"
        )
        
        table.add_column("課程名稱", style="cyan", width=25, no_wrap=False)
        table.add_column("課程代碼", style="green", width=12)
        table.add_column("教師", style="yellow", width=12)
        table.add_column("人數限制", justify="right", style="bright_cyan", width=10)
        table.add_column("已選人數", justify="right", style="bright_cyan", width=10)
        table.add_column("剩餘名額", justify="right", width=12)
        table.add_column("自動加選", style="yellow", width=14)
        table.add_column("檢查時間", style="dim", width=20)
        
        # 使用鎖保護讀取共享狀態
        with self.state_lock:
            course_states_copy = self.course_states.copy()
            enrollment_attempts_copy = self.enrollment_attempts.copy()
        
        for identifier, state in course_states_copy.items():
            course = state["course"]
            course_info = state.get("course_info", {})
            count = state["count"]
            last_check = state["last_check"].strftime("%Y-%m-%d %H:%M:%S")
            
            # 取得詳細資訊
            course_no = course_info.get('CourseNo', course.course_no or '')
            teacher = course_info.get('CourseTeacher', 'N/A')
            restrict1 = course_info.get('Restrict1', '')
            
            # 取得課程名稱（優先使用 course.course_name，如果沒有則使用 API 回應的 CourseName）
            course_name = course.course_name or course_info.get('CourseName', course.alias or course_no)
            
            # 取得自動加選狀態（使用複製的字典）
            attempts = enrollment_attempts_copy.get(identifier, 0)
            max_attempts = course.max_enroll_attempts
            if course.auto_enroll:
                if attempts >= max_attempts:
                    enroll_status = f"已達上限({attempts}/{max_attempts})"
                    enroll_style = "red"
                else:
                    enroll_status = f"啟用({attempts}/{max_attempts})"
                    enroll_style = "green"
            else:
                enroll_status = "未啟用"
                enroll_style = "dim"
            
            # 計算人數限制、已選人數、剩餘名額
            if restrict1 and restrict1 != '9999':
                try:
                    restrict1_int = int(restrict1)
                except (ValueError, TypeError):
                    limit_str = "N/A"
                    enrolled_str = str(count)
                    remaining_str = "N/A"
                    remaining_style = "dim"
                    table.add_row(
                        course_name,
                        course_no,
                        teacher,
                        limit_str,
                        enrolled_str,
                        Text(remaining_str, style=remaining_style),
                        Text(enroll_status, style=enroll_style),
                        last_check
                    )
                    continue
                remaining = restrict1_int - count
                
                # 人數限制顯示
                limit_str = str(restrict1_int)
                
                # 已選人數顯示
                enrolled_str = str(count)
                
                # 剩餘名額顯示
                if remaining > 0:
                    remaining_str = str(remaining)
                    remaining_style = "green"
                elif remaining == 0:
                    remaining_str = "額滿"
                    remaining_style = "red"
                else:
                    remaining_str = f"超額{abs(remaining)}"
                    remaining_style = "red"
            else:
                # 無限制
                limit_str = "無限制"
                enrolled_str = str(count)
                remaining_str = "N/A"
                remaining_style = "dim"
            
            table.add_row(
                course_name,  # 課程名稱（API 回應的課程名稱）
                course_no,
                teacher,
                limit_str,
                enrolled_str,
                Text(remaining_str, style=remaining_style),
                Text(enroll_status, style=enroll_style),  # 自動加選狀態
                last_check
            )
        
        return table
    
    def _create_notifications_panel(self) -> Panel:
        """建立通知面板"""
        # 使用鎖保護讀取共享狀態
        with self.state_lock:
            notifications_copy = self.notifications.copy()
        
        if not notifications_copy:
            content = Text("尚無通知", style="dim", justify="center")
        else:
            # 只顯示最近的通知（倒序顯示，最新的在上面）
            recent_notifications = list(reversed(notifications_copy[-self.max_notifications:]))
            
            # 建立通知內容，使用 Text.from_markup 來正確解析 Rich 標記
            content_parts = []
            for i, notif in enumerate(recent_notifications):
                timestamp = notif.get("timestamp", "")
                course_name = notif.get("course_name", "")  # 使用 API 回應的課程名稱
                course_alias = notif.get("course_alias", "")  # 別名（僅在使用者自訂時顯示）
                course_no = notif.get("course_no", "")
                
                # 建立通知項目（使用分隔線區分）
                if i > 0:
                    content_parts.append("[dim]─[/dim]")
                
                # 判斷通知類型
                notif_type = notif.get("type", "availability")  # 預設為名額通知
                
                if notif_type == "enrollment":
                    # 加選結果通知
                    success = notif.get("success", False)
                    message = notif.get("message", "")
                    attempt = notif.get("attempt", 0)
                    status = notif.get("status", "")
                    
                    # 時間和課程名稱
                    content_parts.append(f"[dim]{timestamp}[/dim] [bold cyan]{course_name}[/bold cyan]")
                    content_parts.append(f"  [dim]代碼: {course_no}[/dim]")
                    # 加選結果
                    content_parts.append(f"  {status} (第 {attempt} 次嘗試)")
                    content_parts.append(f"  [dim]{message}[/dim]")
                elif notif_type == "system":
                    # 系統通知
                    message = notif.get("message", "")
                    content_parts.append(f"[dim]{timestamp}[/dim] [bold yellow]系統[/bold yellow]")
                    content_parts.append(f"  [dim]{message}[/dim]")
                else:
                    # 名額通知
                    limit = notif.get("limit", 0)
                    enrolled = notif.get("enrolled", 0)
                    remaining = notif.get("remaining", 0)
                    
                    # 計算佔用率
                    fill_rate = (enrolled / limit * 100) if limit > 0 else 0
                    
                    # 時間和課程名稱（使用 API 回應的課程名稱）
                    content_parts.append(f"[dim]{timestamp}[/dim] [bold cyan]{course_name}[/bold cyan]")
                    # 課程代碼
                    content_parts.append(f"  [dim]代碼: {course_no}[/dim]")
                    # 別名（僅在使用者自訂時顯示，即 course_alias 不等於 course_name 且不等於 course_no）
                    if course_alias and course_alias != course_name and course_alias != course_no:
                        content_parts.append(f"  [dim]別名: {course_alias}[/dim]")
                    # 人數資訊
                    content_parts.append(f"  限制: [yellow]{limit}[/yellow] | 已選: [cyan]{enrolled}[/cyan] ([dim]{fill_rate:.1f}%[/dim])")
                    # 剩餘名額（突出顯示）
                    content_parts.append(f"  剩餘: [bold green]{remaining} 人[/bold green]")
            
            # 使用 Text.from_markup 來正確解析 Rich 標記語法
            content = Text.from_markup("\n".join(content_parts))
        
        return Panel(
            content,
            title=f"[bold green]即時通知 ({len(self.notifications)})[/bold green]",
            border_style="green"
        )
    
    def _add_notification(self, course: CourseConfig, current_count: int, course_info: Dict, previous_remaining: Optional[int] = None) -> None:
        """添加名額通知到列表（只在名額變化時調用）"""
        restrict1 = course_info.get('Restrict1', '')
        if restrict1 and restrict1 != '9999':
            try:
                restrict1_int = int(restrict1)
            except (ValueError, TypeError):
                logger.warning(f"課程 {course.alias} 的 Restrict1 值無法解析為數字: {restrict1!r}")
                return
            remaining = restrict1_int - current_count
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            course_no = course_info.get('CourseNo', course.course_no or 'N/A')
            course_name = course_info.get('CourseName', course.course_name or 'N/A')
            
            # 計算佔用率
            fill_rate = (current_count / restrict1_int * 100) if restrict1_int > 0 else 0
            
            # 判斷變化類型
            change_type = "new"  # 新通知
            if previous_remaining is not None:
                if previous_remaining == 0 and remaining > 0:
                    change_type = "available"  # 從額滿變為有名額
                elif previous_remaining > 0 and remaining == 0:
                    change_type = "full"  # 從有名額變為額滿
                elif remaining > previous_remaining:
                    change_type = "increased"  # 剩餘名額增加
                elif remaining < previous_remaining:
                    change_type = "decreased"  # 剩餘名額減少
            
            notification = {
                "timestamp": timestamp,
                "course_alias": course.alias,
                "course_no": course_no,
                "course_name": course_name,
                "remaining": remaining,
                "previous_remaining": previous_remaining,
                "limit": restrict1_int,
                "enrolled": current_count,
                "fill_rate": fill_rate,
                "change_type": change_type,
                "type": "availability",
                "datetime": datetime.now()
            }
            
            # 添加到通知列表（使用鎖保護）
            with self.state_lock:
                self.notifications.append(notification)
                # 只保留最近的通知（最多6筆）
                if len(self.notifications) > self.max_notifications:
                    self.notifications = self.notifications[-self.max_notifications:]
    
    def _create_control_panel(self) -> Panel:
        """建立控制面板"""
        content_parts = []
        
        # 使用鎖保護讀取共享狀態
        with self.state_lock:
            enrollment_attempts_copy = self.enrollment_attempts.copy()
        
        # 統計資訊
        total_enrolls = sum(enrollment_attempts_copy.values())
        active_courses = sum(1 for c in self.config.courses if c.auto_enroll)
        content_parts.append(f"[bold]自動加選課程:[/bold] [cyan]{active_courses}[/cyan]")
        content_parts.append(f"[bold]總嘗試次數:[/bold] [yellow]{total_enrolls}[/yellow]")
        
        # 控制方式說明
        content_parts.append("[dim]─[/dim]")
        content_parts.append("[bold]控制方式:[/bold]")
        content_parts.append("[dim]  可在 Web 界面或配置文件中為每個課程單獨設置[/dim]")
        content_parts.append("[dim]─[/dim]")
        content_parts.append("[dim]按 Ctrl+C 退出[/dim]")
        
        return Panel(
            Text.from_markup("\n".join(content_parts)),
            title="[bold cyan]控制面板[/bold cyan]",
            border_style="cyan"
        )
    
    def _add_system_notification(self, message: str, level: str = "info") -> None:
        """
        添加系統通知
        
        Args:
            message: 通知訊息
            level: 通知級別 (info, success, warning, error)
        """
        notification = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "type": "system",
            "message": message,
            "level": level,
            "datetime": datetime.now()
        }
        # 使用鎖保護系統通知列表
        with self.state_lock:
            self.system_notifications.append(notification)
            if len(self.system_notifications) > self.max_system_notifications:
                self.system_notifications = self.system_notifications[-self.max_system_notifications:]
    
    def _create_layout(self) -> Layout:
        """建立佈局（三欄：表格、通知、控制）"""
        layout = Layout()
        
        # 左右分欄：左側表格，右側面板
        layout.split_row(
            Layout(name="table", size=None),
            Layout(name="right_panel", size=40)
        )
        
        # 右側面板分為上下：通知和控制
        layout["right_panel"].split_column(
            Layout(name="notifications", size=None),
            Layout(name="control", size=10)
        )
        
        layout["table"].update(self._create_status_table())
        layout["notifications"].update(self._create_notifications_panel())
        layout["control"].update(self._create_control_panel())
        
        return layout
    
    def _reload_config_if_changed(self) -> bool:
        """
        檢查配置文件是否變更，如果變更則重新載入
        
        Returns:
            如果配置文件已變更並重新載入則返回 True
        """
        if not self.config_manager:
            return False
        
        current_time = time.time()
        if current_time - self.last_config_check_time < self.config_check_interval:
            return False
        
        self.last_config_check_time = current_time
        
        try:
            # 檢查配置文件修改時間
            config_file = self.config_manager.config_file
            if os.path.exists(config_file):
                # 重新載入配置
                new_config = self.config_manager.load_config()
                
                # 檢查是否有變化
                old_interval_type = getattr(self.config, 'check_interval_type', 'fixed')
                new_interval_type = getattr(new_config, 'check_interval_type', 'fixed')
                old_interval_min = getattr(self.config, 'check_interval_min', None)
                new_interval_min = getattr(new_config, 'check_interval_min', None)
                old_interval_max = getattr(self.config, 'check_interval_max', None)
                new_interval_max = getattr(new_config, 'check_interval_max', None)
                
                if len(new_config.courses) != len(self.config.courses) or \
                   new_config.check_interval != self.config.check_interval or \
                   new_interval_type != old_interval_type or \
                   new_interval_min != old_interval_min or \
                   new_interval_max != old_interval_max:
                    # 配置已更改，更新
                    old_course_count = len(self.config.courses)
                    self.config = new_config
                    new_course_count = len(self.config.courses)
                    
                    if new_course_count != old_course_count:
                        self._add_system_notification(f"配置已更新：課程數量 {old_course_count} → {new_course_count}")
                    else:
                        self._add_system_notification("配置已重新載入")
                    
                    return True
        except Exception as e:
            # 載入失敗，不影響運行，但需可觀測
            logger.warning(f"重新載入配置失敗（將沿用舊配置）: {e}")
        
        return False
    
    def _get_next_check_interval(self) -> float:
        """
        獲取下一個檢查間隔（支持固定時間或隨機範圍）
        
        Returns:
            float: 下一個檢查間隔（秒）
        """
        # 確保有 check_interval_type 屬性（兼容舊配置）
        interval_type = getattr(self.config, 'check_interval_type', 'fixed')
        if interval_type == "random":
            # 隨機範圍模式
            min_interval = self.config.check_interval_min or 1
            max_interval = self.config.check_interval_max or self.config.check_interval
            # 確保最小值不大於最大值
            if min_interval > max_interval:
                min_interval, max_interval = max_interval, min_interval
            # 生成隨機間隔
            return random.uniform(min_interval, max_interval)
        else:
            # 固定時間模式（默認）
            return float(self.config.check_interval)
    
    def start_monitoring(self) -> None:
        """開始持續監控（使用 Rich Live 更新）"""
        if not self.config.courses:
            console.print("[bold red]錯誤: 沒有配置任何監控課程[/bold red]")
            return
        
        # 預先登入以保持 session 活躍
        if self.config.student_id and self.config.student_password:
            logger.info("監控開始前預先登入...")
            self._pre_login_if_needed()
        
        console.print(f"[bold green]開始監控 {len(self.config.courses)} 個課程[/bold green]")
        interval_type = getattr(self.config, 'check_interval_type', 'fixed')
        if interval_type == "random":
            min_interval = self.config.check_interval_min or 1
            max_interval = self.config.check_interval_max or self.config.check_interval
            console.print(f"[cyan]檢查間隔: 隨機範圍 {min_interval}-{max_interval} 秒[/cyan]")
        else:
            console.print(f"[cyan]檢查間隔: 固定 {self.config.check_interval} 秒[/cyan]")
        console.print("[dim]按 Ctrl+C 停止監控[/dim]")
        console.print("[dim]控制方式：在 Web 界面或配置文件中為每個課程單獨設置自動加選[/dim]")
        console.print("[dim]  可在 Web 界面或配置文件中設置全局自動加選[/dim]\n")
        
        # 清空之前的狀態，確保第一次檢查時會通知
        self.course_states = {}
        self.notifications = []
        self.system_notifications = []
        self.enrollment_attempts = {}
        
        try:
            # 計算更新頻率：根據 check_interval 調整，但至少每秒更新一次（確保時間顯示流暢）
            # 使用預設間隔計算（如果是隨機模式，使用最大值）
            base_interval = self.config.check_interval
            interval_type = getattr(self.config, 'check_interval_type', 'fixed')
            if interval_type == "random":
                base_interval = self.config.check_interval_max or self.config.check_interval
            
            if base_interval < 1:
                refresh_rate = 10
                update_interval = 0.1
            elif base_interval <= 5:
                refresh_rate = 2
                update_interval = 0.5
            else:
                refresh_rate = 1
                update_interval = 1.0
            
            with Live(self._create_layout(), refresh_per_second=refresh_rate, screen=True) as live:
                last_check_time = 0
                next_check_interval = self._get_next_check_interval()  # 獲取第一個檢查間隔
                last_update_time = 0
                notification_count_before_check = len(self.notifications)  # 記錄檢查前的通知數量
                
                while True:
                    current_time_sec = time.time()
                    needs_update = False
                    
                    # 檢查配置文件是否有變化（熱重載）
                    if self._reload_config_if_changed():
                        needs_update = True
                    
                    # 檢查全局自動加選狀態變化（配置參數會在熱重載時自動更新）
                    # 不需要單獨檢查，因為配置重載時會自動更新
                    
                    # 檢查是否到了檢查時間（使用動態間隔）
                    if current_time_sec - last_check_time >= next_check_interval:
                        # 並行執行檢查（不顯示檢查訊息，避免干擾 Live 顯示）
                        with ThreadPoolExecutor(max_workers=min(len(self.config.courses), 10)) as executor:
                            # 提交所有檢查任務
                            future_to_course = {executor.submit(self.check_course, course): course for course in self.config.courses}
                            
                            # 等待所有任務完成
                            for future in as_completed(future_to_course):
                                course = future_to_course[future]
                                try:
                                    future.result()  # 獲取結果，如果有異常會在這裡拋出
                                except Exception as e:
                                    logger.error(f"檢查課程 {course.alias} 時發生異常: {e}")
                                    self._add_system_notification(f"檢查課程 {course.alias} 時發生異常: {e}", level="error")
                        
                        last_check_time = current_time_sec
                        # 獲取下一個檢查間隔（隨機模式時會生成新的隨機值）
                        next_check_interval = self._get_next_check_interval()
                        
                        # 如果有新通知，更新顯示（通知面板）
                        if len(self.notifications) > notification_count_before_check:
                            needs_update = True
                            notification_count_before_check = len(self.notifications)
                    
                    # 根據 update_interval 更新顯示（確保時間顯示流暢，但不更新通知面板）
                    if current_time_sec - last_update_time >= update_interval:
                        # 只更新時間，不更新通知面板（通知面板只在有新通知時更新）
                        needs_update = True
                        last_update_time = current_time_sec
                    
                    # 如果有需要，更新顯示
                    if needs_update:
                        live.update(self._create_layout())
                    
                    # 短暫睡眠，避免 CPU 使用過高
                    time.sleep(0.05)  # 減少睡眠時間以更快響應鍵盤輸入
                    
        except KeyboardInterrupt:
            console.print("\n[bold yellow]監控已停止[/bold yellow]")
        except Exception as e:
            logger.error(f"監控流程發生未預期錯誤: {e}", exc_info=True)
            console.print(f"\n[bold red]監控流程中斷: {e}[/bold red]")
    
    def display_current_status(self) -> None:
        """顯示當前所有課程的狀態（單次顯示，不使用 Live）"""
        layout = self._create_layout()
        console.print(layout)
