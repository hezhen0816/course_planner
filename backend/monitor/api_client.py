"""
NTUST 課程查詢 API 客戶端
封裝對課程查詢系統的 API 請求
"""

import os
import time
from typing import Dict, List, Optional

import requests
import urllib3

from .env_manager import EnvManager
from .semester import fetch_semester_candidates, get_default_semester
from .utils import setup_logging, is_proxy_configured, get_proxy_info_for_logging, _is_network_disconnected, build_session
from ..tr_rooms import fetch_query_courses_filtered
from ..logging_setup import get_logger

# 禁用 SSL 警告（如果禁用驗證）

# 設置日誌
logger = get_logger(__name__)


class NTUSTCourseAPI:
    """NTUST 課程查詢 API 客戶端"""
    
    
    def __init__(self, verify_ssl: Optional[bool] = None, proxies: Optional[Dict] = None):
        """
        初始化 API 客戶端
        
        Args:
            verify_ssl: 是否驗證 SSL 證書
                       - None: 自動判斷（優先使用環境變數 NTUST_VERIFY_SSL）
                       - True: 驗證 SSL 證書（推薦，但可能在某些環境下失敗）
                       - False: 不驗證 SSL 證書（不推薦，僅用於解決證書問題）
            proxies: 代理配置字典，如果為 None 則從環境變數讀取
        """
        self.env_manager = EnvManager()
        self.last_request_latency_ms: Optional[float] = None
        self.last_search_failed: bool = False  # True when the last search_courses hit a transport/HTTP error
        # verify_ssl 與代理的解析共用 utils.build_session（原本三個檔各解析一次）
        self.session, self.verify_ssl = build_session(
            verify_ssl,
            proxies,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            env_manager=self.env_manager,
        )
    
    def _is_proxy_configured(self):
        """檢查是否配置了代理（包括 SOCKS5）"""
        return is_proxy_configured(self.session.proxies, self.env_manager)
    
    def _get_proxy_info_for_logging(self):
        """獲取代理信息用於日誌記錄"""
        return get_proxy_info_for_logging(self.session.proxies, self.env_manager)
    
    def verify_proxy_usage(self) -> Dict[str, any]:
        """
        驗證代理是否真的在使用
        
        通過檢查實際的 IP 地址來確認代理是否生效
        比較直接連接和通過代理連接的 IP 地址來確認
        
        Returns:
            包含驗證結果的字典：
            - using_proxy: bool - 是否使用代理
            - configured: bool - 是否配置了代理
            - actual_ip: str - 實際使用的 IP 地址
            - proxy_host: str - 代理主機（如果配置了）
            - message: str - 驗證訊息
        """
        result = {
            'using_proxy': False,
            'configured': False,
            'actual_ip': None,
            'proxy_host': None,
            'message': ''
        }
        
        # 檢查是否配置了代理
        proxy_type = self.env_manager.get('NTUST_PROXY_TYPE', '').lower()
        proxy_host = self.env_manager.get('NTUST_PROXY_HOST')
        proxy_port = self.env_manager.get('NTUST_PROXY_PORT')
        
        if proxy_type and proxy_host and proxy_port:
            result['configured'] = True
            result['proxy_host'] = proxy_host
        else:
            result['message'] = '未配置代理伺服器'
            return result
        
        # 檢查 session 是否配置了代理（SOCKS5 可能不會設置 session.proxies）
        # 對於 SOCKS5，socket.socket 可能已被替換，所以即使 session.proxies 為空也可能在使用代理
        if not self.session.proxies and proxy_type != 'socks5':
            result['message'] = 'Session 未配置代理，可能配置失敗'
            logger.warning("Session 未配置代理，但環境變數中有代理配置")
            return result
        
        # 嘗試獲取實際 IP 地址來驗證代理
        try:
            # 使用 httpbin.org 來獲取 IP（設置較短的超時，避免代理不可用時長時間等待）
            response = self.session.get(
                'https://httpbin.org/ip',
                timeout=8,  # 減少超時時間到 8 秒
                verify=self.verify_ssl
            )
            if response.status_code == 200:
                ip_info = response.json()
                result['actual_ip'] = ip_info.get('origin', 'N/A')
                
                # 嘗試以「不讀取環境代理」的直接連線 session 取得直連 IP（不改寫全域 socket）
                direct_ip = None
                try:
                    direct_session = requests.Session()
                    direct_session.trust_env = False
                    direct_response = direct_session.get(
                        'https://httpbin.org/ip',
                        timeout=5,
                        verify=self.verify_ssl
                    )
                    if direct_response.status_code == 200:
                        direct_ip_info = direct_response.json()
                        direct_ip = (direct_ip_info.get('origin', '') or '').split(',')[0].strip()
                except Exception as e:
                    logger.info(f"無法取得直接連接 IP（略過比較）: {e}")

                proxy_ip = (result['actual_ip'] or '').split(',')[0].strip()
                if direct_ip and proxy_ip:
                    if direct_ip != proxy_ip:
                        result['using_proxy'] = True
                        result['message'] = f'代理驗證成功，當前 IP: {proxy_ip}（直接連接 IP: {direct_ip}）'
                        logger.info(f"代理驗證成功 - 配置的代理: {proxy_host}, 代理 IP: {proxy_ip}, 直接 IP: {direct_ip}")
                    else:
                        # 在雲端或企業網路中，直連與代理可能同出口 IP，避免誤判為未走代理
                        result['using_proxy'] = True
                        result['message'] = f'代理連線可用（IP 與直連相同: {proxy_ip}）'
                        logger.warning(f"代理 IP 與直連 IP 相同: {proxy_ip}，可能為同出口網路")
                else:
                    result['using_proxy'] = True
                    result['message'] = f"代理連線可用，當前 IP: {result['actual_ip']}"
                    logger.info(f"代理驗證成功 - 配置的代理: {proxy_host}, 實際 IP: {result['actual_ip']}")
            else:
                result['message'] = f'無法驗證代理，HTTP 狀態碼: {response.status_code}'
                logger.warning(f"無法驗證代理，HTTP 狀態碼: {response.status_code}")
        except Exception as e:
            error_msg = str(e)
            result['message'] = f'代理驗證失敗: {error_msg}'
            logger.warning(f"代理驗證失敗: {e}", exc_info=True)
        
        return result
    
    SEARCH_TIMEOUT = 10  # worker polls every few seconds; a slow answer counts as one missed check

    def search_courses(
        self,
        semester: str = "",
        course_no: str = "",
        course_name: str = "",
        display_name: str = "",
        include_cross_school: bool = True,
    ) -> List[Dict]:
        """查詢課程（傳輸層共用 backend/tr_rooms.fetch_query_courses_filtered）。

        回傳 [] 代表「查無資料」或「傳輸失敗」，以 last_search_failed 區分；網路中斷則重新拋出，
        讓上層能辨識離線狀態。延遲寫入 last_request_latency_ms 供儀表板心跳使用。
        """
        if not semester:
            semester = get_default_semester(verify_ssl=self.verify_ssl)

        self.last_search_failed = False
        proxy_info, proxy_details = self._get_proxy_info_for_logging()
        logger.info(
            f"發送課程查詢 API 請求 - {proxy_info}{proxy_details} | 課程代碼: {course_no or 'N/A'}, "
            f"課程名稱: {display_name or course_name or 'N/A'}"
        )
        req_start = time.perf_counter()
        try:
            courses = fetch_query_courses_filtered(
                semester,
                course_no=course_no,
                course_name=course_name,
                verify_ssl=self.verify_ssl,
                include_cross_school=include_cross_school,
                session=self.session,
                timeout=self.SEARCH_TIMEOUT,
            )
        except requests.exceptions.SSLError as e:
            self.last_request_latency_ms = (time.perf_counter() - req_start) * 1000
            logger.error(f"SSL 證書驗證錯誤: {e}（可在監控設定關閉 SSL 驗證，或更新 certifi）")
            self.last_search_failed = True
            return []
        except requests.exceptions.RequestException as e:
            self.last_request_latency_ms = (time.perf_counter() - req_start) * 1000
            if _is_network_disconnected(e):
                logger.error(f"API 請求失敗：當前網路已中斷 - {e}")
                raise  # 讓上層辨識離線，不當成查無資料
            logger.error(f"API 請求失敗: {e}")
            self.last_search_failed = True
            return []
        except RuntimeError as e:  # 回傳格式不是清單
            self.last_request_latency_ms = (time.perf_counter() - req_start) * 1000
            logger.error(f"API 回傳異常: {e}")
            self.last_search_failed = True
            return []
        self.last_request_latency_ms = (time.perf_counter() - req_start) * 1000
        logger.info(f"課程查詢 API 請求成功 - {proxy_info}{proxy_details} | 返回 {len(courses)} 個課程")
        return courses

    def get_course_by_code(self, course_no: str, semester: str = "", course_name: str = "") -> Optional[Dict]:
        """
        根據課程代碼查詢單一課程
        
        Args:
            course_no: 課程代碼
            semester: 學年期
            course_name: 課程名稱（僅用於日誌記錄，不參與查詢條件）
        
        Returns:
            課程資訊字典，如果找不到則返回 None
        """
        # 查詢時不使用 course_name，避免因名稱不匹配導致查不到（例如使用者輸入了簡稱或錯誤名稱）
        # 但將其作為 display_name 傳入，以便在日誌中顯示
        semester_candidates: List[str] = []
        if semester:
            semester_candidates.append(semester)
            for candidate in fetch_semester_candidates(verify_ssl=self.verify_ssl):
                if candidate not in semester_candidates:
                    semester_candidates.append(candidate)
        else:
            semester_candidates.append(get_default_semester(verify_ssl=self.verify_ssl))
            for candidate in fetch_semester_candidates(verify_ssl=self.verify_ssl):
                if candidate not in semester_candidates:
                    semester_candidates.append(candidate)

        # 只允許往「更新的」學期回退，避免以舊學期的資料覆蓋現況
        if semester:
            semester_candidates = [c for c in semester_candidates if c == semester or c > semester]

        for candidate in semester_candidates:
            courses = self.search_courses(semester=candidate, course_no=course_no, display_name=course_name)
            if not courses and getattr(self, 'last_search_failed', False):
                # 傳輸/HTTP 失敗 ≠ 查無資料；不要因此改查其他學期
                logger.warning(f"課程 {course_no} 學期 {candidate} 查詢失敗，暫不回退到其他學期")
                return None
            if courses:
                if candidate != semester:
                    logger.info(f"課程 {course_no} 在學期 {semester or 'N/A'} 無結果，改以學期 {candidate} 查得資料")
                return courses[0]
        return None
    
    def get_courses_by_name(self, course_name: str, semester: str = "") -> List[Dict]:
        """
        根據課程名稱查詢課程（可能有多個同名課程）
        
        Args:
            course_name: 課程名稱
            semester: 學年期
        
        Returns:
            課程列表
        """
        return self.search_courses(semester=semester, course_name=course_name)
    
    def get_enrollment_count(self, course_no: str, semester: str = "") -> Optional[int]:
        """
        取得指定課程的選課人數
        
        Args:
            course_no: 課程代碼
            semester: 學年期
        
        Returns:
            選課人數，如果找不到課程則返回 None
        """
        course = self.get_course_by_code(course_no, semester)
        if course:
            return course.get("ChooseStudent")
        return None
