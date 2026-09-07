"""
自動加選模組
處理課程自動加選邏輯

重要提醒：請遵守學校選課公平原則，不要過度使用自動化功能
系統會監控登入和加選頻率，請合理使用
"""

import os
import re
import time
import threading
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup

from .config import CourseConfig
from .env_manager import EnvManager
from .utils import setup_logging, is_proxy_configured, get_proxy_info_for_logging

# 禁用 SSL 警告（如果禁用驗證）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設置日誌
logger = setup_logging()


class EnrollmentClient:
    """加選客戶端（含速率限制）"""
    
    BASE_URL = "https://courseselection.ntust.edu.tw"
    LOGIN_URL = f"{BASE_URL}/"
    
    # 學校規定的速率限制（安全範圍，低於官方限制）
    MAX_LOGINS_PER_MINUTE = 5  # 官方限制：10次/分鐘，我們設為5次
    MAX_LOGINS_PER_HOUR = 150  # 官方限制：300次/小時，我們設為150次
    MAX_LOGINS_PER_DAY = 300   # 官方限制：600次/天，我們設為300次
    
    MAX_ENROLLS_PER_HOUR = 300  # 官方限制：600次/小時，我們設為300次
    MAX_ENROLLS_PER_DAY = 600   # 官方限制：1200次/天，我們設為600次
    
    # 最小間隔時間（秒）
    MIN_LOGIN_INTERVAL = 12  # 每分鐘最多5次 = 每12秒一次
    MIN_ENROLL_INTERVAL = 12  # 每小時最多300次 = 每12秒一次

    # 登入／加選請求超時（秒）— 選課系統與 SSO 回應常較慢，10 秒易超時
    REQUEST_TIMEOUT = 25  # (connect, read) 或單一數值
    LOG_CLEANUP_INTERVAL_SECONDS = 3600  # 每小時最多清理一次
    
    def __init__(self, verify_ssl: Optional[bool] = None, proxies: Optional[Dict] = None):
        """
        初始化加選客戶端
        
        Args:
            verify_ssl: 是否驗證 SSL 證書
            proxies: 代理配置字典，如果為 None 則從環境變數讀取
        """
        # 初始化環境變數管理器
        self.env_manager = EnvManager()
        
        if verify_ssl is None:
            env_verify = self.env_manager.get('NTUST_VERIFY_SSL', 'true').lower()
            verify_ssl = env_verify in ('true', '1', 'yes')
        
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.is_logged_in = False
        
        # 設置代理
        if proxies:
            self.session.proxies.update(proxies)
        else:
            self._setup_proxy()
        
        # 速率限制追蹤
        self.login_times = deque()  # 記錄登入時間
        self.enroll_times = deque()  # 記錄加選時間
        self.last_login_time = None
        self.last_enroll_time = None
        self._rate_limit_lock = threading.Lock()
        # repo root (backend/monitor/enrollment.py -> three levels up)
        _repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self._response_log_dir = os.path.join(_repo_root, 'logs', 'enrollment_responses')
        retention_days_raw = self.env_manager.get('NTUST_ENROLLMENT_LOG_RETENTION_DAYS', '7')
        try:
            self._response_log_retention_days = max(0, int(retention_days_raw))
        except (ValueError, TypeError):
            self._response_log_retention_days = 7
        self._last_log_cleanup_at = 0.0
    
    def _setup_proxy(self):
        """從環境變數設置代理"""
        proxy_type = self.env_manager.get('NTUST_PROXY_TYPE', '').lower()
        proxy_host = self.env_manager.get('NTUST_PROXY_HOST')
        proxy_port = self.env_manager.get('NTUST_PROXY_PORT')
        proxy_username = self.env_manager.get('NTUST_PROXY_USERNAME')
        proxy_password = self.env_manager.get('NTUST_PROXY_PASSWORD')
        
        if not proxy_type or not proxy_host or not proxy_port:
            return
        
        # 構建代理 URL
        if proxy_username and proxy_password:
            proxy_url = f"{proxy_type}://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}"
        else:
            proxy_url = f"{proxy_type}://{proxy_host}:{proxy_port}"
        
        # 設置代理
        if proxy_type in ['http', 'https']:
            self.session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
        elif proxy_type == 'socks5':
            # 使用 requests session scoped SOCKS5，避免全域 socket 汙染
            socks_proxy_url = proxy_url.replace('socks5://', 'socks5h://', 1)
            self.session.proxies = {
                'http': socks_proxy_url,
                'https': socks_proxy_url
            }
            logger.info(f"已設置 SOCKS5 代理: {proxy_host}:{proxy_port}（session scoped）")
        else:
            logger.warning(f"不支援的代理類型: {proxy_type}")
    
    def _is_proxy_configured(self):
        """檢查是否配置了代理（包括 SOCKS5）"""
        return is_proxy_configured(self.session.proxies, self.env_manager)
    
    def _get_proxy_info_for_logging(self):
        """獲取代理信息用於日誌記錄"""
        return get_proxy_info_for_logging(self.session.proxies, self.env_manager)

    def _extract_sso_failure_reason(self, html: str, final_url: str) -> str:
        """Best-effort extraction for current SSO failure states."""
        if not html:
            return f"登入狀態不明，最終 URL: {final_url}"

        soup = BeautifulSoup(html, 'html.parser')

        error_msg = soup.find('div', class_=re.compile('error|alert|warning|danger', re.I))
        if error_msg:
            error_text = error_msg.get_text(strip=True)
            if error_text:
                return f"登入失敗: {error_text}"

        validation_errors = soup.find_all('span', {'class': lambda x: x and 'field-validation-error' in str(x)})
        error_texts = [err.get_text(strip=True) for err in validation_errors if err.get_text(strip=True)]
        if error_texts:
            return f"登入失敗: {', '.join(error_texts)}"

        page_text = soup.get_text(" ", strip=True)
        if '帳號或密碼輸入錯誤' in page_text:
            return "登入失敗: 帳號或密碼錯誤"
        if '變更密碼' in page_text and '180天' in page_text:
            return "登入失敗: SSO 可能要求先變更密碼"

        has_turnstile = bool(soup.find(attrs={'name': 'cf-turnstile-response'}))
        has_recaptcha = bool(soup.find(attrs={'name': 'g-recaptcha-response'}))
        has_hcaptcha = bool(soup.find(attrs={'name': 'h-captcha-response'}))
        if has_turnstile or has_recaptcha or has_hcaptcha:
            return "登入失敗: SSO 需要 CAPTCHA / 瀏覽器端驗證，requests 流程無法完成"

        if 'ssoam2.ntust.edu.tw' in final_url:
            snippet = re.sub(r"\s+", " ", page_text)[:160]
            logger.warning(f"SSO 頁面內容（前 160 字）: {snippet}")
            return f"登入失敗: 停留在 SSO 頁面，認證未完成（最終 URL: {final_url[:80]}…）"

        return f"登入狀態不明，最終 URL: {final_url}"

    def _submit_oidc_form_if_present(self, response: requests.Response) -> requests.Response:
        """Submit the OIDC form_post callback when SSO returns an auto-submit form."""
        soup = BeautifulSoup(response.text or '', 'html.parser')
        for form in soup.find_all('form'):
            form_action = form.get('action', '')
            if form_action.startswith('http://') or form_action.startswith('https://'):
                submit_url = form_action
            elif form_action.startswith('/'):
                submit_url = f"{self.BASE_URL}{form_action}"
            else:
                submit_url = urljoin(f"{self.BASE_URL}/", form_action)

            if 'signin-oidc' not in submit_url and 'courseselection.ntust.edu.tw' not in submit_url:
                continue

            form_data = {}
            for input_tag in form.find_all('input'):
                name = input_tag.get('name')
                if name:
                    form_data[name] = input_tag.get('value', '')

            if not form_data:
                continue

            logger.info("正在提交 OIDC 回調表單...")
            return self.session.post(
                submit_url,
                data=form_data,
                verify=self.verify_ssl,
                timeout=self.REQUEST_TIMEOUT,
                allow_redirects=True
            )

        return response
        
    def _check_rate_limit(
        self,
        timestamps: deque,
        limits: Dict[str, int],
        min_interval: int,
        last_time: Optional[datetime],
        operation_name: str
    ) -> Tuple[bool, str]:
        """
        通用的速率限制檢查方法
        
        檢查操作是否超過速率限制，包括：
        - 每日限制（24小時內）
        - 每小時限制（1小時內）
        - 每分鐘限制（1分鐘內）
        - 最小間隔限制（兩次操作之間的最小時間間隔）
        
        Args:
            timestamps: 時間戳記錄隊列，按時間順序存儲操作時間
            limits: 限制字典，包含以下可選鍵：
                - 'minute' (int): 每分鐘最大操作次數
                - 'hour' (int): 每小時最大操作次數
                - 'day' (int): 每天最大操作次數
            min_interval: 最小間隔時間（秒），兩次操作之間必須間隔的時間
            last_time: 上次操作時間，如果為 None 則不檢查間隔
            operation_name: 操作名稱（用於錯誤訊息），例如 "登入" 或 "加選"
        
        Returns:
            Tuple[bool, str]: 
            - 第一個元素：是否允許執行操作（True 表示允許，False 表示不允許）
            - 第二個元素：訊息字符串，如果不允許則包含原因
        
        Note:
            此方法會自動清理超過 24 小時的舊記錄，以保持內存效率
        """
        now = datetime.now()
        
        # 清理過期的記錄（保留最近24小時）
        cutoff_24h = now - timedelta(hours=24)
        cutoff_1h = now - timedelta(hours=1)
        cutoff_1m = now - timedelta(minutes=1)
        
        with self._rate_limit_lock:
            # 移除超過24小時的記錄
            while timestamps and timestamps[0] < cutoff_24h:
                timestamps.popleft()
            
            # 檢查每日限制
            if 'day' in limits:
                daily_count = sum(1 for t in timestamps if t >= cutoff_24h)
                if daily_count >= limits['day']:
                    return False, f"已達到每日{operation_name}限制（{limits['day']}次），請稍後再試"
            
            # 檢查每小時限制
            if 'hour' in limits:
                hourly_count = sum(1 for t in timestamps if t >= cutoff_1h)
                if hourly_count >= limits['hour']:
                    return False, f"已達到每小時{operation_name}限制（{limits['hour']}次），請稍後再試"
            
            # 檢查每分鐘限制
            if 'minute' in limits:
                minute_count = sum(1 for t in timestamps if t >= cutoff_1m)
                if minute_count >= limits['minute']:
                    return False, f"已達到每分鐘{operation_name}限制（{limits['minute']}次），請稍後再試"
        
        # 檢查最小間隔
        if last_time:
            elapsed = (now - last_time).total_seconds()
            if elapsed < min_interval:
                wait_time = min_interval - elapsed
                return False, f"{operation_name}間隔過短，請等待 {wait_time:.1f} 秒後再試"
        
        return True, ""
    
    def _check_login_rate_limit(self) -> Tuple[bool, str]:
        """
        檢查登入速率限制
        
        Returns:
            (是否允許, 訊息)
        """
        limits = {
            'minute': self.MAX_LOGINS_PER_MINUTE,
            'hour': self.MAX_LOGINS_PER_HOUR,
            'day': self.MAX_LOGINS_PER_DAY
        }
        return self._check_rate_limit(
            self.login_times,
            limits,
            self.MIN_LOGIN_INTERVAL,
            self.last_login_time,
            "登入"
        )

    def _cleanup_enrollment_response_logs(self) -> None:
        """Delete old enrollment response logs based on retention policy."""
        if self._response_log_retention_days <= 0:
            return
        now_ts = time.time()
        if now_ts - self._last_log_cleanup_at < self.LOG_CLEANUP_INTERVAL_SECONDS:
            return
        self._last_log_cleanup_at = now_ts
        cutoff_ts = now_ts - (self._response_log_retention_days * 86400)
        removed = 0
        try:
            if not os.path.isdir(self._response_log_dir):
                return
            with os.scandir(self._response_log_dir) as entries:
                for entry in entries:
                    if not entry.is_file():
                        continue
                    if not entry.name.startswith('enroll_'):
                        continue
                    try:
                        mtime = entry.stat().st_mtime
                        if mtime < cutoff_ts:
                            os.remove(entry.path)
                            removed += 1
                    except Exception as e:
                        logger.debug(f"清理舊加選回應日誌失敗（{entry.name}）: {e}")
            if removed > 0:
                logger.info(f"已清理 {removed} 份過期加選回應日誌（保留 {self._response_log_retention_days} 天）")
        except Exception as e:
            logger.warning(f"清理加選回應日誌失敗: {e}")

    def _write_enrollment_response_log(self, course_no: str, content: str, suffix: str = '') -> None:
        """Write enrollment response to local log directory with periodic cleanup."""
        try:
            self._cleanup_enrollment_response_logs()
            os.makedirs(self._response_log_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_no = course_no or 'unknown'
            suffix_part = f"_{suffix}" if suffix else ''
            log_path = os.path.join(self._response_log_dir, f'enroll_{safe_no}_{ts}{suffix_part}.html')
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(content or '(空響應)')
            if suffix:
                logger.info(f"加選回應（{suffix}）已寫入: {log_path}")
            else:
                logger.info(f"加選 API 回傳已寫入: {log_path}")
        except Exception as e:
            logger.warning(f"寫入加選回傳 LOG 失敗: {e}")
    
    def _check_enroll_rate_limit(self) -> Tuple[bool, str]:
        """
        檢查加選速率限制
        
        Returns:
            (是否允許, 訊息)
        """
        limits = {
            'hour': self.MAX_ENROLLS_PER_HOUR,
            'day': self.MAX_ENROLLS_PER_DAY
        }
        return self._check_rate_limit(
            self.enroll_times,
            limits,
            self.MIN_ENROLL_INTERVAL,
            self.last_enroll_time,
            "加選"
        )
    
    LOGIN_FAILURE_COOLDOWN_AFTER = 3        # consecutive failures before pausing
    LOGIN_FAILURE_COOLDOWN_SECONDS = 15 * 60

    def _record_login_result(self, success: bool) -> None:
        with self._rate_limit_lock:
            if success:
                self._login_failures = 0
                self._login_cooldown_until = 0.0
                return
            self._login_failures = getattr(self, '_login_failures', 0) + 1
            if self._login_failures >= self.LOGIN_FAILURE_COOLDOWN_AFTER:
                self._login_cooldown_until = time.time() + self.LOGIN_FAILURE_COOLDOWN_SECONDS
                self._login_failures = 0
                logger.warning(f"連續登入失敗 {self.LOGIN_FAILURE_COOLDOWN_AFTER} 次，暫停自動登入 {self.LOGIN_FAILURE_COOLDOWN_SECONDS // 60} 分鐘")

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        success, message = self._login_once(username, password)
        # 速率限制／冷卻中的拒絕不是 SSO 的判定，不計入連續失敗
        if not (not success and ('間隔' in message or '限制' in message or '暫停自動登入' in message)):
            self._record_login_result(success)
        return success, message

    def _login_once(self, username: str, password: str) -> Tuple[bool, str]:
        """
        登入選課系統（通過 SSO 單一登入）
        
        重要提醒：請遵守學校選課公平原則，不要過度使用自動登入功能
        
        Args:
            username: 學號
            password: 密碼
        
        Returns:
            (是否成功, 訊息)
        """
        # 檢查速率限制
        allowed, limit_msg = self._check_login_rate_limit()
        if not allowed:
            return False, limit_msg

        # 連續登入失敗保護：學校規定密碼錯 10 次鎖 15 分鐘；連續失敗達門檻就暫停 15 分鐘，
        # 避免 worker 把帳號打到鎖住。成功一次即重置。
        with self._rate_limit_lock:
            cooldown_until = getattr(self, '_login_cooldown_until', 0.0)
        if cooldown_until > time.time():
            remaining = int(cooldown_until - time.time())
            return False, f"連續登入失敗已達 {self.LOGIN_FAILURE_COOLDOWN_AFTER} 次，暫停自動登入 {remaining // 60} 分 {remaining % 60} 秒（保護帳號不被鎖定）"

        # 以「嘗試」計入速率限制（不論成敗），否則密碼錯誤時會每個週期都重打 SSO
        now = datetime.now()
        with self._rate_limit_lock:
            self.login_times.append(now)
            self.last_login_time = now

        try:
            # 1. 訪問選課系統，會被重定向到 SSO 登入頁面
            # 記錄代理使用狀態
            proxy_info, proxy_details = self._get_proxy_info_for_logging()
            logger.info(f"正在訪問選課系統... - {proxy_info}{proxy_details}")
            response = self.session.get(self.LOGIN_URL, verify=self.verify_ssl, timeout=self.REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()
            
            # 2. 檢查是否已經在 SSO 登入頁面
            sso_base = "https://ssoam2.ntust.edu.tw"
            if sso_base in response.url:
                logger.info("已重定向到 SSO 登入頁面")
                sso_login_url = response.url
            else:
                # 如果沒有重定向，嘗試直接訪問 SSO
                soup = BeautifulSoup(response.text, 'html.parser')
                form = soup.find('form')
                if form:
                    # 從表單中獲取 ReturnUrl
                    return_url_input = form.find('input', {'name': 'ReturnUrl'})
                    if return_url_input:
                        return_url = return_url_input.get('value', '')
                        sso_login_url = f"{sso_base}/account/login?ReturnUrl={return_url}"
                    else:
                        sso_login_url = f"{sso_base}/account/login"
                else:
                    return False, "無法找到登入表單或重定向資訊"
            
            # 3. 獲取 SSO 登入頁面
            proxy_info, proxy_details = self._get_proxy_info_for_logging()
            logger.info(f"正在獲取 SSO 登入頁面... - {proxy_info}{proxy_details}")
            sso_response = self.session.get(sso_login_url, verify=self.verify_ssl, timeout=self.REQUEST_TIMEOUT)
            sso_response.raise_for_status()
            
            # 4. 解析 SSO 登入表單
            soup = BeautifulSoup(sso_response.text, 'html.parser')
            form = soup.find('form')
            if not form:
                return False, "無法找到 SSO 登入表單"
            
            # 5. 獲取 CSRF token
            csrf_token = None
            csrf_input = form.find('input', {'name': '__RequestVerificationToken'})
            if csrf_input:
                csrf_token = csrf_input.get('value', '')
            
            # 6. 準備登入資料
            login_data = {
                'Username': username,
                'Password': password,
                'captcha': ''  # 驗證碼留空
            }
            
            # 添加 CSRF token
            if csrf_token:
                login_data['__RequestVerificationToken'] = csrf_token
            
            # 添加表單中的其他隱藏欄位
            hidden_inputs = form.find_all('input', {'type': 'hidden'})
            for hidden_input in hidden_inputs:
                name = hidden_input.get('name')
                value = hidden_input.get('value', '')
                if name and name not in ['__RequestVerificationToken']:
                    login_data[name] = value
            
            # 7. 提交 SSO 登入表單
            form_action = form.get('action', '/')
            # 檢查 action 是否已經是完整 URL
            if form_action.startswith('http://') or form_action.startswith('https://'):
                sso_submit_url = form_action
            elif form_action.startswith('/'):
                # 絕對路徑，直接拼接
                sso_submit_url = f"{sso_base}{form_action}"
            else:
                # 相對路徑，需要拼接
                sso_submit_url = f"{sso_base}/{form_action}"
            proxy_info, proxy_details = self._get_proxy_info_for_logging()
            logger.info(f"正在提交 SSO 登入資訊... - {proxy_info}{proxy_details}")
            login_response = self.session.post(
                sso_submit_url,
                data=login_data,
                verify=self.verify_ssl,
                timeout=self.REQUEST_TIMEOUT,
                allow_redirects=True
            )
            
            # 8. 檢查登入是否成功
            # 登入成功應該會重定向回選課系統
            login_response = self._submit_oidc_form_if_present(login_response)
            final_url = login_response.url
            
            # 檢查是否仍停留在 SSO 頁面（表示登入失敗或驗證未完成）
            if 'ssoam2.ntust.edu.tw' in final_url:
                sso_soup = BeautifulSoup(login_response.text or '', 'html.parser')
                still_has_login_form = bool(sso_soup.find('input', {'name': 'Username'}) or sso_soup.find('input', {'name': 'Password'}))
                if still_has_login_form or '/account/login' in final_url.lower():
                    return False, self._extract_sso_failure_reason(login_response.text, final_url)
                # 落在 SSO 首頁且沒有登入表單：SSO 端很可能已建立 session，只是沒帶 ReturnUrl 回來。
                logger.info(f"SSO 登入後停在 {final_url}（無登入表單），嘗試重新進入選課系統...")
            
            # 檢查是否成功重定向到選課系統
            if 'courseselection.ntust.edu.tw' in final_url:
                # 可能需要處理 OIDC 回調
                if 'signin-oidc' in final_url:
                    # 處理 OIDC 回調表單
                    oidc_soup = BeautifulSoup(login_response.text, 'html.parser')
                    oidc_form = oidc_soup.find('form')
                    if oidc_form:
                        # 自動提交 OIDC 回調表單
                        form_action = oidc_form.get('action', '')
                        if not form_action.startswith('http'):
                            form_action = f"{self.BASE_URL}{form_action}"
                        
                        # 獲取表單中的所有隱藏欄位
                        form_data = {}
                        for input_tag in oidc_form.find_all('input', type='hidden'):
                            name = input_tag.get('name')
                            value = input_tag.get('value', '')
                            if name:
                                form_data[name] = value
                        
                        # 提交 OIDC 回調
                        oidc_response = self.session.post(
                            form_action,
                            data=form_data,
                            verify=self.verify_ssl,
                            timeout=self.REQUEST_TIMEOUT,
                            allow_redirects=True
                        )
                        final_url = oidc_response.url
                
                # 驗證登入狀態：訪問選課頁面
                verify_response = self.session.get(
                    f"{self.BASE_URL}/First/A06/A06",
                    verify=self.verify_ssl,
                    timeout=self.REQUEST_TIMEOUT,
                    allow_redirects=True
                )
                
                # 檢查是否成功訪問選課頁面
                if 'signin-oidc' not in verify_response.url and 'login' not in verify_response.url.lower():
                    self.is_logged_in = True
                    return True, f"登入成功，已重定向到選課系統"
                else:
                    return False, "登入後無法訪問選課頁面，可能認證未完成"
            
            # SSO 登入成功但被導到其他站台（例如 i.ntust.edu.tw 入口網），ReturnUrl 遺失。
            # 此時 SSO 端已有 session，重新進入選課系統會經 OIDC 靜默完成登入。
            if 'courseselection.ntust.edu.tw' not in final_url:
                if 'ssoam2.ntust.edu.tw' not in final_url:
                    logger.info(f"SSO 登入後落在 {final_url}，改以既有 SSO session 重新進入選課系統...")
                reenter = self.session.get(
                    self.LOGIN_URL,
                    verify=self.verify_ssl,
                    timeout=self.REQUEST_TIMEOUT,
                    allow_redirects=True,
                )
                reenter = self._submit_oidc_form_if_present(reenter)
                if 'ssoam2.ntust.edu.tw' not in reenter.url:
                    verify_response = self.session.get(
                        f"{self.BASE_URL}/First/A06/A06",
                        verify=self.verify_ssl,
                        timeout=self.REQUEST_TIMEOUT,
                        allow_redirects=True,
                    )
                    if 'signin-oidc' not in verify_response.url and 'login' not in verify_response.url.lower():
                        self.is_logged_in = True
                        return True, f"登入成功（經 {final_url.split('/')[2]} 轉回選課系統）"
                    final_url = verify_response.url
                else:
                    final_url = reenter.url

            # 檢查回應內容
            if '選課' in login_response.text or 'course' in login_response.text.lower():
                # 驗證登入狀態
                verify_response = self.session.get(
                    f"{self.BASE_URL}/First/A06/A06",
                    verify=self.verify_ssl,
                    timeout=self.REQUEST_TIMEOUT,
                    allow_redirects=True
                )
                
                if 'signin-oidc' not in verify_response.url and 'login' not in verify_response.url.lower():
                    self.is_logged_in = True
                    return True, "登入成功"
            
            return False, self._extract_sso_failure_reason(login_response.text, final_url)
            
        except requests.exceptions.Timeout as e:
            from .utils import _is_network_disconnected
            if _is_network_disconnected(e):
                logger.error(f"登入超時：當前網路已中斷 - {str(e)}")
                return False, f"登入超時：當前網路已中斷，請檢查網路連接"
            else:
                logger.error(f"登入超時: {str(e)}")
                return False, f"登入超時，請檢查網絡連接: {str(e)}"
        except requests.exceptions.ConnectionError as e:
            from .utils import _is_network_disconnected
            if _is_network_disconnected(e):
                logger.error(f"登入連接錯誤：當前網路已中斷 - {str(e)}")
                return False, f"無法連接到服務器：當前網路已中斷，請檢查網路連接"
            else:
                logger.error(f"登入連接錯誤: {str(e)}")
                return False, f"無法連接到服務器，請檢查網絡連接: {str(e)}"
        except requests.exceptions.RequestException as e:
            logger.error(f"登入請求錯誤: {str(e)}")
            return False, f"登入請求失敗: {str(e)}"
        except Exception as e:
            logger.error(f"登入過程發生未預期的錯誤: {str(e)}", exc_info=True)
            return False, f"登入錯誤: {str(e)}"
    
    def _check_session_quick(self) -> bool:
        """
        快速檢查 session 是否有效（使用 HEAD 請求，更快）
        
        即使 is_logged_in 為 True，也向伺服器發送 HEAD 請求驗證，
        因為伺服器端 session 可能已過期。
        
        Returns:
            bool: session 是否有效
        """
        try:
            # 使用 HEAD 請求快速檢查，比 GET 請求更快
            check_response = self.session.head(
                f"{self.BASE_URL}/First/A06/A06",
                verify=self.verify_ssl,
                timeout=3,  # 較短的超時時間
                allow_redirects=True
            )
            # 如果沒有被重定向到登入頁面，表示 session 還有效
            if 'signin-oidc' not in check_response.url and 'login' not in check_response.url.lower():
                self.is_logged_in = True
                logger.debug("Session 快速檢查：有效")
                return True
            else:
                self.is_logged_in = False
                logger.debug("Session 快速檢查：已過期")
                return False
        except Exception as e:
            # 檢查失敗，假設 session 無效
            logger.debug(f"Session 快速檢查失敗: {e}")
            self.is_logged_in = False
            return False
    
    def _keep_session_alive(self) -> bool:
        """
        保持 session 活躍（訪問選課頁面）
        
        注意：某些網站 HEAD 請求可能不會刷新 session，因此使用 GET 請求
        但只讀取部分內容以提高效率
        
        Returns:
            bool: 是否成功保持 session 活躍
        """
        try:
            # 使用 GET 請求保持 session 活躍（某些網站 HEAD 不會刷新 session）
            # 但設置 stream=True 只讀取響應頭，不讀取完整內容，提高效率
            response = self.session.get(
                f"{self.BASE_URL}/First/A06/A06",
                verify=self.verify_ssl,
                timeout=5,
                allow_redirects=True,
                stream=True  # 流式讀取，不立即下載完整內容
            )
            # 立即關閉連接，不讀取內容
            response.close()
            
            # 檢查是否被重定向到登入頁面
            if 'signin-oidc' in response.url or 'login' in response.url.lower():
                self.is_logged_in = False
                logger.debug("保持 session 活躍：檢測到需要重新登入")
                return False
            self.is_logged_in = True
            logger.debug("保持 session 活躍：成功")
            return True
        except Exception as e:
            logger.debug(f"保持 session 活躍失敗: {e}")
            self.is_logged_in = False
            return False

    def _extract_enrollment_outcome_from_html(self, html: str, course_no: str = "") -> Tuple[Optional[bool], str]:
        """
        從頁面 HTML 嘗試判斷加選結果。
        回傳:
            - True: 明確成功
            - False: 明確失敗
            - None: 無法判斷
        """
        if not html:
            return None, "頁面內容為空"

        success_indicators = ['選課成功', '加選成功', '已加入選課清單']
        for ind in success_indicators:
            if ind in html:
                return True, f"偵測到成功標記: {ind}"

        # 若選課清單(cartTable)出現目標課號，且同列可退選(delbtn)，通常代表已成功加選
        if course_no:
            cart_pat = re.compile(
                rf'id=["\']cartTable["\'][\s\S]*?{re.escape(course_no)}[\s\S]*?delbtn',
                re.IGNORECASE
            )
            if cart_pat.search(html):
                return True, "在選課清單(cartTable)偵測到課號且可退選"

        # 保守規則：僅在課號出現在「已選課程/選課清單/退選」等上下文時視為成功
        if course_no:
            pat = re.compile(rf'(?<![A-Za-z0-9]){re.escape(course_no)}(?![A-Za-z0-9])')
            for m in pat.finditer(html):
                s = max(0, m.start() - 140)
                e = min(len(html), m.end() + 140)
                context = html[s:e]
                if any(k in context for k in ['已選課程', '選課清單', '退選', '已選']):
                    return True, "課號出現在已選課程相關區段"

        fail_indicators = [
            '課程人數額滿', '人數額滿', '名額已滿', '已選過', '重複選課',
            '時間衝突', '衝堂', '無法選修', '無法加選', '選修失敗',
            '非加選期間', '非選課時間', '尚未開放加選', '目前無法加選'
        ]
        for kw in fail_indicators:
            if kw in html:
                return False, f"偵測到失敗訊號: {kw}"

        return None, "頁面未提供可判定訊號"

    def _verify_uncertain_enrollment(
        self,
        page_url: str,
        course_no: str,
        course_name: str,
        reason: str
    ) -> Dict[str, Any]:
        """針對不明結果做二次驗證，盡量縮小不確定性。"""
        try:
            # 後端頁面更新可能有延遲，短時間重試可大幅降低假陰性
            last_detail = "頁面未提供可判定訊號"
            for attempt in range(3):
                verify_resp = self.session.get(
                    page_url,
                    verify=self.verify_ssl,
                    timeout=self.REQUEST_TIMEOUT,
                    allow_redirects=True
                )
                final_url = verify_resp.url
                if 'signin-oidc' in final_url or ('login' in final_url.lower() and 'ssoam2' in final_url):
                    self.is_logged_in = False
                    return {
                        'success': False,
                        'message': f'加選失敗: Session 已過期（{reason}）'
                    }

                outcome, detail = self._extract_enrollment_outcome_from_html(verify_resp.text or '', course_no)
                last_detail = detail
                if outcome is True:
                    return {
                        'success': True,
                        'message': f'成功加選課程: {course_name} ({course_no})（二次驗證）'
                    }
                if outcome is False:
                    return {
                        'success': False,
                        'message': f'加選失敗: {detail}'
                    }
                if attempt < 2:
                    time.sleep(1.0)

            return {
                'success': False,
                'message': f'加選結果不明: {course_name} ({course_no})，{reason}；二次驗證: {last_detail}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'加選結果不明: {course_name} ({course_no})，{reason}；二次驗證失敗: {e}'
            }
    
    def enroll_course(
        self,
        course: CourseConfig,
        course_info: Dict,
        student_id: Optional[str] = None,
        password: Optional[str] = None,
        use_add_drop: bool = False
    ) -> Tuple[bool, str]:
        """
        嘗試加選課程

        重要提醒：請遵守學校選課公平原則，不要過度使用自動加選功能
        系統會自動限制加選頻率，避免違反學校規定

        Args:
            course: 課程配置
            course_info: 課程資訊（從查詢 API 取得）
            student_id: 學號（可選，可從配置或環境變數取得）
            password: 密碼（可選，可從配置或環境變數取得）
            use_add_drop: 若為 True 則使用加退選流程 (B01)，否則使用電腦抽選後選課 (A06)

        Returns:
            (是否成功, 訊息)
        """
        # 檢查加選速率限制
        allowed, limit_msg = self._check_enroll_rate_limit()
        if not allowed:
            return False, limit_msg
        
        # 檢查 session 是否有效，只在需要時登入
        if not self.is_logged_in:
            # 使用快速檢查方法
            if not self._check_session_quick():
                # Session 已過期，需要重新登入
                if not student_id or not password:
                    return False, "Session 已過期且未提供帳號密碼"
                
                logger.warning("Session 已過期，正在重新登入...")
                success, message = self.login(student_id, password)
                if not success:
                    return False, f"登入失敗，無法加選: {message}"
        
        course_no = course_info.get('CourseNo', course.course_no)
        course_name = course_info.get('CourseName', course.course_name)
        
        try:
            # 調用加選 API（可選加退選 B01 或電腦抽選後選課 A06）
            result = self._call_enrollment_api(
                course, course_info, student_id, password, use_add_drop=use_add_drop
            )
            
            # 僅在實際送出加選 POST 時才記錄嘗試時間
            if result.get('attempted', True):
                now = datetime.now()
                with self._rate_limit_lock:
                    self.enroll_times.append(now)
                    self.last_enroll_time = now
            
            if result.get('success', False):
                return True, result.get('message', f'成功加選課程: {course_name} ({course_no})')
            else:
                return False, result.get('message', f'加選失敗: {course_name} ({course_no})')
            
        except Exception as e:
            return False, f"加選錯誤: {str(e)}"
    
    def _call_enrollment_api(
        self,
        course: CourseConfig,
        course_info: Dict,
        student_id: Optional[str] = None,
        password: Optional[str] = None,
        use_add_drop: bool = False
    ) -> Dict[str, Any]:
        """
        調用選課系統加選 API

        此方法會：
        1. 訪問選課頁面獲取 CSRF token 和必要的表單數據
        2. 構建加選請求並提交
        3. 解析響應判斷加選是否成功

        Args:
            course: 課程配置對象，包含課程代碼、名稱等信息
            course_info: 課程資訊字典，從查詢 API 獲取，包含 CourseNo、CourseName 等
            student_id: 學號（可選），如果未提供則使用配置中的學號
            password: 密碼（可選），如果未提供則從環境變數或配置中讀取
            use_add_drop: 若為 True 則使用加退選流程 (B01)，否則使用電腦抽選後選課 (A06)

        Returns:
            包含以下鍵的字典：
            - 'success' (bool): 加選是否成功
            - 'message' (str): 詳細訊息，包含成功或失敗的原因

        Raises:
            requests.exceptions.RequestException: 網絡請求相關異常
            Exception: 其他未預期的異常
        """
        course_no = course_info.get('CourseNo', course.course_no)
        course_name = course_info.get('CourseName', course.course_name)

        # 依流程選擇頁面與加選 API URL
        if use_add_drop:
            page_url = f"{self.BASE_URL}/AddAndSub/B01/B01"
            enroll_url = f"{self.BASE_URL}/AddAndSub/B01/ExtraJoin"
        else:
            page_url = f"{self.BASE_URL}/First/A06/A06"
            enroll_url = f"{self.BASE_URL}/First/A06/ExtraJoin"
        attempted = False

        # 先訪問選課頁面以保持 session 活躍並獲取必要的資訊
        csrf_token = None
        try:
            page_response = self.session.get(
                page_url,
                verify=self.verify_ssl,
                timeout=self.REQUEST_TIMEOUT,
                allow_redirects=True
            )
            
            # 檢查是否被重定向到登入頁面
            final_url = page_response.url
            if 'signin-oidc' in final_url or ('login' in final_url.lower() and 'ssoam2' in final_url):
                # Session 已過期，嘗試重新登入
                self.is_logged_in = False
                if student_id and password:
                    logger.warning("Session 已過期，正在重新登入...")
                    login_success, login_msg = self.login(student_id, password)
                    if not login_success:
                        return {
                            'success': False,
                            'message': f'加選失敗: Session 已過期且重新登入失敗 - {login_msg}',
                            'attempted': attempted
                        }
                    # 重新登入成功，再次訪問選課頁面
                    page_response = self.session.get(
                        page_url,
                        verify=self.verify_ssl,
                        timeout=self.REQUEST_TIMEOUT,
                        allow_redirects=True
                    )
                    final_url = page_response.url
                    if 'signin-oidc' in final_url or ('login' in final_url.lower() and 'ssoam2' in final_url):
                        return {
                            'success': False,
                            'message': '加選失敗: 重新登入後仍無法訪問選課頁面',
                            'attempted': attempted
                        }
                else:
                    return {
                        'success': False,
                        'message': '加選失敗: Session 已過期，請重新登入（需要提供 student_id 和 password）',
                        'attempted': attempted
                    }
            
            # 從頁面中獲取 CSRF token（如果有的話）
            page_soup = BeautifulSoup(page_response.text, 'html.parser')
            csrf_input = page_soup.find('input', {'name': '__RequestVerificationToken'})
            if csrf_input:
                csrf_token = csrf_input.get('value', '')
        except Exception as e:
            return {
                'success': False,
                'message': f'加選失敗: 無法開啟選課頁面或取得 CSRF ({e})',
                'attempted': attempted
            }
        
        # 使用課碼輸入框加選 API (type: 3)
        # 這個 API 更通用，不需要從表格中點擊（A06 與 B01 皆同）

        # 準備請求參數
        data = {
            'CourseNo': course_no,
            'type': 3  # 使用課碼輸入框加選
        }
        
        # 如果有 CSRF token，添加到請求中
        if csrf_token:
            data['__RequestVerificationToken'] = csrf_token
        
        # 設置請求頭
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': page_url,
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        try:
            # 記錄代理使用狀態
            proxy_info, proxy_details = self._get_proxy_info_for_logging()
            logger.info(f"正在提交加選請求 - {proxy_info}{proxy_details} | 課程: {course_name} ({course_no})")
            
            # 發送 POST 請求（不自動跟隨重定向，以便檢查響應）
            response = self.session.post(
                enroll_url,
                data=data,
                headers=headers,
                verify=self.verify_ssl,
                timeout=self.REQUEST_TIMEOUT,
                allow_redirects=True  # 允許重定向，但我們會檢查最終響應
            )
            attempted = True
            
            # 檢查 HTTP 狀態碼
            if response.status_code != 200:
                return {
                    'success': False,
                    'message': f'加選請求失敗: HTTP {response.status_code}'
                }
            
            # 檢查最終 URL 是否仍在選課系統內
            final_url = response.url
            if 'signin-oidc' in final_url or 'login' in final_url.lower():
                # Session 已過期
                self.is_logged_in = False
                return {
                    'success': False,
                    'message': '加選失敗: Session 已過期，請重新登入'
                }
            
            # 解析響應（API 返回 HTML 格式）
            response_text = response.text

            # 將加選 API 回傳內容寫入 LOG 供檢視（協助 debug 非加選期間誤判等問題）
            self._write_enrollment_response_log(course_no=course_no, content=response_text)

            # 檢查響應是否為空
            if not response_text or len(response_text.strip()) == 0:
                # 空響應可能表示成功或失敗
                # 根據選課系統的行為，加選後會重定向到 A06 頁面
                # 如果返回空響應，需要訪問選課頁面來檢查是否有錯誤訊息
                
                # 等待一下讓系統處理請求
                import time
                time.sleep(1)
                
                # 訪問選課頁面檢查是否有錯誤訊息
                try:
                    check_response = self.session.get(
                        page_url,
                        verify=self.verify_ssl,
                        timeout=self.REQUEST_TIMEOUT,
                        allow_redirects=True
                    )
                    
                    check_text = check_response.text
                    self._write_enrollment_response_log(
                        course_no=course_no,
                        content=check_text or '(空)',
                        suffix='check'
                    )
                    check_soup = BeautifulSoup(check_text, 'html.parser')

                    # 檢查頁面中是否有錯誤訊息（特別是「課程人數額滿」「非選課時間」等）
                    # 排除公告訊息，只檢查彈出視窗、alert 等真正的錯誤提示
                    # 共用關鍵字（A06 / B01 都視為失敗）
                    error_keywords_common = [
                        '課程人數額滿', '人數額滿', '名額已滿', '已選過',
                        '已經在您的選課表', '已經修過', '重複選課', '請勿重複選課',
                        '時間衝突', '衝堂', '無法選修', '無法加選', '選修失敗',
                        '不符合條件', '不符合', '條件', '設有選課', '班級條件',
                    ]
                    # 僅 A06 流程才視為失敗：空響應後檢查頁常被導向首頁，首頁可能固定顯示「非電腦抽選後選課開放時間」提醒，B01 加退選不應因此誤判
                    error_keywords_a06_only = [
                        '非電腦抽選後選課', '選課開放時間', '非選課開放時間'
                    ]
                    error_keywords = (
                        error_keywords_common + error_keywords_a06_only
                        if not use_add_drop
                        else error_keywords_common
                    )

                    # 先做一次整頁 alert 字串掃描，避免因 BeautifulSoup 解析或 script 結構漏判
                    for alert_match in re.finditer(r"alert\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", check_text):
                        msg = alert_match.group(1).replace('\\n', ' ').replace('\\r', ' ').strip()
                        if '有人數設限' in msg or '先選先上' in msg or '至額滿為止' in msg:
                            continue
                        if any(kw in msg for kw in error_keywords):
                            return {
                                'success': False,
                                'message': f'加選失敗: {msg}'
                            }

                    # 優先檢查成功標記：若頁面有成功訊息，直接回傳成功，避免誤判（例如頁面同時有說明文字與成功結果）
                    success_indicators = ['選課成功', '加選成功', '已加入選課清單']
                    for ind in success_indicators:
                        if ind in check_text:
                            return {
                                'success': True,
                                'message': f'成功加選課程: {course_name} ({course_no})'
                            }

                    # 再從 script 標籤逐一檢查（使用 get_text() 以涵蓋多子節點的 script，避免 .string 為 None 漏判）
                    script_tags = check_soup.find_all('script')
                    for script in script_tags:
                        script_text = script.get_text() or ''
                        # 查找 alert 中的錯誤訊息（支援多行和更複雜的格式）
                        # 匹配 alert('...') 或 alert("...")
                        alert_patterns = [
                            r'alert\(["\']([^"\']+)["\']\)',
                            r'alert\(["\']([^"\']*(?:\\.[^"\']*)*)["\']\)',  # 支援轉義字符
                        ]
                        for pattern in alert_patterns:
                            alert_matches = re.findall(pattern, script_text, re.IGNORECASE | re.DOTALL)
                            for msg in alert_matches:
                                # 清理轉義字符
                                msg = msg.replace('\\n', ' ').replace('\\r', ' ').strip()
                                # 排除公告訊息
                                if '有人數設限' in msg or '先選先上' in msg or '至額滿為止' in msg:
                                    continue
                                if any(keyword in msg for keyword in error_keywords):
                                    return {
                                        'success': False,
                                        'message': f'加選失敗: {msg}'
                                    }
                    
                    # 檢查彈出視窗（modal）中的訊息
                    modal_elements = check_soup.find_all(['div'], class_=re.compile('modal|popup|dialog|alert', re.I))
                    for modal in modal_elements:
                        modal_text = modal.get_text(strip=True)
                        # 排除公告訊息
                        if '有人數設限' in modal_text or '先選先上' in modal_text or '至額滿為止' in modal_text:
                            continue
                        # 檢查是否包含錯誤關鍵字
                        for keyword in error_keywords:
                            if keyword in modal_text:
                                # 提取簡短的錯誤訊息
                                lines = modal_text.split('\n')
                                for line in lines:
                                    line = line.strip()
                                    if line and keyword in line and len(line) < 100:
                                        # 再次確認不是公告訊息
                                        if '有人數設限' not in line and '先選先上' not in line:
                                            return {
                                                'success': False,
                                                'message': f'加選失敗: {line}'
                                            }
                    
                    # 檢查特定的錯誤訊息容器（避免檢查整個頁面）
                    error_containers = check_soup.find_all(['div', 'span', 'p'], 
                                                          class_=re.compile('error|alert|warning|danger|message', re.I))
                    for container in error_containers:
                        container_text = container.get_text(strip=True)
                        # 排除公告訊息
                        if '有人數設限' in container_text or '先選先上' in container_text:
                            continue
                        for keyword in error_keywords:
                            if keyword in container_text and len(container_text) < 200:
                                return {
                                    'success': False,
                                    'message': f'加選失敗: {container_text}'
                                }
                    
                    # 沒有找到錯誤訊息，可能是成功
                    # 檢查響應頭中是否有重定向資訊
                    location = response.headers.get('Location', '')
                    if location:
                        if 'A06' in location or 'B01' in location or 'courseselection' in location:
                            return self._verify_uncertain_enrollment(
                                page_url, course_no, course_name,
                                "伺服器回傳重導資訊但未找到成功標記"
                            )
                    
                    # HTTP 200 且空響應，且頁面中沒有錯誤訊息
                    if response.status_code == 200:
                        return self._verify_uncertain_enrollment(
                            page_url, course_no, course_name,
                            "API 返回空響應（HTTP 200）"
                        )
                    else:
                        return {
                            'success': False,
                            'message': f'加選失敗: API 返回空響應 (HTTP {response.status_code})'
                        }
                except Exception:
                    return self._verify_uncertain_enrollment(
                        page_url, course_no, course_name,
                        f"API 返回空響應且無法驗證 (HTTP {response.status_code})"
                    )
            
            response_lower = response_text.lower()
            
            # 檢查是否是需要重新認證的重定向（signin-oidc）
            if 'signin-oidc' in response_text or 'signin-oidc' in response.url:
                # 這表示 session 可能過期，需要重新登入
                self.is_logged_in = False  # 標記為未登入
                return {
                    'success': False,
                    'message': '加選失敗: Session 已過期，請重新登入'
                }
            
            # 調試：保存響應內容（可選，用於調試）
            # 如果響應很短，可能是錯誤訊息
            if len(response_text) < 500:
                # 可能是純文字錯誤訊息或簡短的 HTML
                # 直接檢查是否包含錯誤關鍵字
                if any(keyword in response_text for keyword in ['額滿', '失敗', '錯誤', '已選', '衝突', '無法', '重複']):
                    return {
                        'success': False,
                        'message': f'加選失敗: {response_text.strip()}'
                    }
            
            # 使用 BeautifulSoup 解析 HTML
            soup = BeautifulSoup(response_text, 'html.parser')
            
            # 優先檢查錯誤訊息（因為即使 HTTP 200 也可能失敗）
            # 非加選期間：系統在非選課時間可能回傳此類訊息，必須視為失敗
            non_enrollment_keywords = [
                '非加選期間', '加選期間已過', '加選尚未開放', '選課時間未到',
                '非選課時間', '尚未開放加選', '不在加選期間', '加選時間已過',
                '非選課期間', '選課尚未開放', '目前無法加選'
            ]
            for kw in non_enrollment_keywords:
                if kw in response_text:
                    return {
                        'success': False,
                        'message': f'加選失敗: {kw}（目前非加選期間）'
                    }
            # 常見的錯誤訊息模式（更全面的匹配）
            error_patterns = [
                r'課程人數額滿[。.]?',
                r'人數額滿[。.]?',
                r'額滿[。.]?',
                r'名額已滿[。.]?',
                r'已選過[。.]?',
                r'已經在您的選課表.*重複選課',
                r'已經修過.*請勿重複選課',
                r'重複選課[（(].*[）)]?',
                r'已選[。.]?',
                r'時間衝突[。.]?',
                r'衝堂[，,].*無法選修[。.]?',
                r'衝堂[。.]?',
                r'無法選修[。.]?',
                r'無法加選[。.]?',
                r'選修失敗[。.]?',
                r'系統錯誤[！!]?',
                r'錯誤[：:]\s*(.+?)[。.]',
                r'課程.*額滿',
                r'選課.*失敗',
                r'加選.*失敗',
                r'選修的這門課與.*衝堂[，,].*無法選修[。.]?',  # 完整的衝堂錯誤訊息
                r'本門課設有選課.*條件[，,].*不符合條件[，,].*無法選修[。.]?',  # 選課班級條件不符合
                r'設有選課.*條件[，,].*不符合[，,].*無法選修[。.]?',  # 選課條件不符合（簡化版）
                r'不符合.*條件[，,].*無法選修[。.]?',  # 不符合條件
                r'不符合.*條件[，,].*無法[。.]?',  # 不符合條件（更簡化）
            ]
            
            # 檢查文字內容中的錯誤訊息
            for pattern in error_patterns:
                match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
                if match:
                    error_msg = match.group(0).strip()
                    # 清理多餘的空白字符
                    error_msg = re.sub(r'\s+', ' ', error_msg)
                    return {
                        'success': False,
                        'message': f'加選失敗: {error_msg}'
                    }
            
            # 檢查響應長度，如果很短可能是錯誤訊息
            if len(response_text.strip()) < 200:
                # 檢查是否包含中文字符（可能是錯誤訊息）
                if re.search(r'[\u4e00-\u9fff]', response_text):
                    # 提取所有中文字符和標點
                    chinese_text = re.findall(r'[\u4e00-\u9fff。，！？：；、]+', response_text)
                    if chinese_text:
                        error_msg = ''.join(chinese_text).strip()
                        if any(keyword in error_msg for keyword in ['額滿', '失敗', '錯誤', '已選', '衝突', '無法', '不符合', '條件', '重複']):
                            return {
                                'success': False,
                                'message': f'加選失敗: {error_msg}'
                            }
            
            # 檢查 HTML 元素中的錯誤訊息
            # 查找常見的錯誤訊息容器
            error_selectors = [
                {'class': re.compile('error|alert|warning|danger', re.I)},
                {'id': re.compile('error|alert|warning|danger', re.I)},
                {'role': 'alert'},
            ]
            
            for selector in error_selectors:
                error_elements = soup.find_all(['div', 'span', 'p', 'td', 'li'], selector)
                for elem in error_elements:
                    error_text = elem.get_text(strip=True)
                    if error_text and len(error_text) < 200:  # 避免提取整個頁面
                        # 檢查是否包含錯誤關鍵字
                        if any(keyword in error_text for keyword in ['額滿', '失敗', '錯誤', '已選', '衝突', '無法', '不符合', '條件', '重複']):
                            return {
                                'success': False,
                                'message': f'加選失敗: {error_text}'
                            }
            
            # 檢查 JavaScript alert 或 confirm 中的錯誤訊息
            script_tags = soup.find_all('script')
            for script in script_tags:
                script_text = script.string or ''
                # 查找 alert 或 confirm 中的錯誤訊息
                alert_matches = re.findall(r'alert\(["\']([^"\']+)["\']\)', script_text, re.IGNORECASE)
                confirm_matches = re.findall(r'confirm\(["\']([^"\']+)["\']\)', script_text, re.IGNORECASE)
                
                for msg in alert_matches + confirm_matches:
                    if any(keyword in msg for keyword in ['額滿', '失敗', '錯誤', '已選', '衝突', '無法', '不符合', '條件', '重複']):
                        return {
                            'success': False,
                            'message': f'加選失敗: {msg}'
                        }
            
            # 檢查彈出視窗（modal）中的訊息
            modal_elements = soup.find_all(['div'], class_=re.compile('modal|popup|dialog', re.I))
            for modal in modal_elements:
                modal_text = modal.get_text(strip=True)
                if any(keyword in modal_text for keyword in ['額滿', '失敗', '錯誤', '已選', '衝突', '無法', '不符合', '條件', '重複']):
                    # 提取簡短的錯誤訊息（通常是第一句或包含關鍵字的部分）
                    lines = modal_text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and any(keyword in line for keyword in ['額滿', '失敗', '錯誤', '已選', '衝突', '無法', '不符合', '條件', '重複']):
                            if len(line) < 100:  # 只取簡短的訊息
                                return {
                                    'success': False,
                                    'message': f'加選失敗: {line}'
                                }
            
            # 檢查成功標記（只有在沒有錯誤訊息時才檢查）
            # 注意：不使用「已成功」因太寬鬆（頁面可能顯示「系統已成功連線」等）
            success_indicators = [
                '選課成功', '加選成功', '已加入選課清單'
            ]
            
            for indicator in success_indicators:
                if indicator in response_text:
                    return {
                        'success': True,
                        'message': f'成功加選課程: {course_name} ({course_no})'
                    }
            
            # 如果響應是完整的 HTML 頁面（通常表示成功重定向）
            # 但需要確認沒有錯誤訊息
            if len(response_text) > 1000:
                # 再次檢查是否有錯誤訊息（可能在 HTML 註釋或隱藏元素中）
                # 檢查所有文字節點
                all_text = soup.get_text()
                if any(keyword in all_text for keyword in ['額滿', '失敗', '錯誤', '已選', '衝突', '無法', '不符合', '條件', '重複']):
                    # 提取包含錯誤關鍵字的句子
                    sentences = re.split(r'[。！？\n]', all_text)
                    for sentence in sentences:
                        if any(keyword in sentence for keyword in ['額滿', '失敗', '錯誤', '已選', '衝突', '無法', '不符合', '條件', '重複']):
                            if len(sentence.strip()) < 100:  # 只取簡短的錯誤訊息
                                return {
                                    'success': False,
                                    'message': f'加選失敗: {sentence.strip()}'
                                }
                
                # 再次確認沒有非加選期間的訊息（選單可能含「加選」等字）
                if any(kw in all_text for kw in non_enrollment_keywords):
                    return {
                        'success': False,
                        'message': f'加選失敗: 目前非加選期間'
                    }
                # 檢查是否包含選課系統的主要元素（表示成功載入頁面）
                has_course_selection_elements = any(
                    keyword in response_text for keyword in [
                        '待選清單', '選課清單', '加選', '退選',
                        'A06', 'B01', '加退選', 'course', '選課系統'
                    ]
                )
                
                if has_course_selection_elements:
                    # 可能是成功，但無法完全確定
                    # 建議檢查選課清單來確認
                    return self._verify_uncertain_enrollment(
                        page_url, course_no, course_name,
                        "頁面已載入選課系統但缺少成功標記"
                    )
            
            # 如果響應很短，可能是純文字錯誤訊息
            if len(response_text.strip()) < 500:
                # 直接返回響應內容作為錯誤訊息
                clean_text = response_text.strip()
                # 移除 HTML 標籤（如果有）
                if '<' in clean_text:
                    clean_text = soup.get_text(strip=True)
                if clean_text:
                    return {
                        'success': False,
                        'message': f'加選失敗: {clean_text[:200]}'  # 限制長度
                    }
            
            # 無法確定結果（可能是新的錯誤類型或成功但沒有明確標記）
            # 檢查響應長度和內容來判斷
            response_length = len(response_text)
            
            # 如果響應很短（< 1000 字符），可能是錯誤訊息或重定向
            if response_length < 1000:
                # 提取所有可見文字
                visible_text = soup.get_text(strip=True)
                if visible_text and len(visible_text) < 500:
                    return {
                        'success': False,
                        'message': f'加選失敗: {visible_text}'
                    }
            
            # 如果響應很長且包含選課系統的元素，可能是成功
            if response_length > 2000:
                # 先排除非加選期間（選單可能含「加選」等字）
                if any(kw in response_text for kw in non_enrollment_keywords):
                    return {
                        'success': False,
                        'message': f'加選失敗: 目前非加選期間'
                    }
                # 檢查是否包含選課系統的主要標識
                has_selection_system = any(
                    keyword in response_text for keyword in [
                        '待選清單', '選課清單', '加選', '退選',
                        '電腦抽選後選課', '加退選', '選課系統'
                    ]
                )
                
                if has_selection_system:
                    # 可能是成功，但為了安全起見，標記為需要確認
                    return self._verify_uncertain_enrollment(
                        page_url, course_no, course_name,
                        "回應內容不足以確認成功"
                    )
            
            # 無法確定結果
            # 嘗試保存響應內容到文件以便調試（可選）
            debug_dir = os.path.join(os.getcwd(), 'debug_responses')
            if os.getenv('NTUST_DEBUG_ENROLLMENT', '').lower() in ('true', '1', 'yes'):
                try:
                    os.makedirs(debug_dir, exist_ok=True)
                    debug_file = os.path.join(debug_dir, f'enroll_response_{course_no}_{int(time.time())}.html')
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(response_text)
                    logger.debug(f"調試: 響應內容已保存到 {debug_file}")
                except Exception as e:
                    logger.debug(f"無法保存調試文件: {e}")
            
            return self._verify_uncertain_enrollment(
                page_url, course_no, course_name,
                f"響應長度: {response_length} 字符。提示: 設定環境變數 NTUST_DEBUG_ENROLLMENT=true 可保存完整響應內容到 debug_responses/ 目錄"
            )
            
        except requests.exceptions.Timeout as e:
            from .utils import _is_network_disconnected
            if _is_network_disconnected(e):
                logger.error(f"加選請求超時：當前網路已中斷 - {str(e)}")
                return {
                    'success': False,
                    'message': f'加選請求超時：當前網路已中斷，請檢查網路連接'
                }
            else:
                logger.error(f"加選請求超時: {str(e)}")
                return {
                    'success': False,
                    'message': f'加選請求超時，請檢查網絡連接: {str(e)}'
                }
        except requests.exceptions.ConnectionError as e:
            from .utils import _is_network_disconnected
            if _is_network_disconnected(e):
                logger.error(f"加選請求連接錯誤：當前網路已中斷 - {str(e)}")
                return {
                    'success': False,
                    'message': f'無法連接到服務器：當前網路已中斷，請檢查網路連接'
                }
            else:
                logger.error(f"加選請求連接錯誤: {str(e)}")
                return {
                    'success': False,
                    'message': f'無法連接到服務器，請檢查網絡連接: {str(e)}'
                }
        except requests.exceptions.RequestException as e:
            logger.error(f"加選請求錯誤: {str(e)}")
            return {
                'success': False,
                'message': f'加選請求失敗: {str(e)}'
            }
        except Exception as e:
            logger.error(f"加選處理發生未預期的錯誤: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'加選處理錯誤: {str(e)}'
            }
