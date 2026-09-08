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
from .utils import setup_logging, is_proxy_configured, get_proxy_info_for_logging, handle_request_exception

# 禁用 SSL 警告（如果禁用驗證）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設置日誌
logger = setup_logging()


class NTUSTCourseAPI:
    """NTUST 課程查詢 API 客戶端"""
    
    BASE_URL = "https://querycourse.ntust.edu.tw/QueryCourse/api/courses"
    
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
        # 初始化環境變數管理器
        self.env_manager = EnvManager()
        
        # 檢查環境變數
        if verify_ssl is None:
            env_verify = self.env_manager.get('NTUST_VERIFY_SSL', 'true').lower()
            verify_ssl = env_verify in ('true', '1', 'yes')
        
        self.verify_ssl = verify_ssl
        self.last_request_latency_ms: Optional[float] = None
        self.last_search_failed: bool = False  # True when the last search_courses hit a transport/HTTP error
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json; charset=utf-8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 設置代理
        if proxies:
            self.session.proxies.update(proxies)
            _, proxy_details = self._get_proxy_info_for_logging()
            logger.info(f"已設置代理（通過參數）{proxy_details}")
        else:
            self._setup_proxy()
        
        # 記錄代理配置狀態
        self._log_proxy_status()
        
        if not self.verify_ssl:
            logger.warning("SSL 證書驗證已禁用，這可能帶來安全風險")
    
    def _setup_proxy(self):
        """從環境變數設置代理"""
        proxy_type = self.env_manager.get('NTUST_PROXY_TYPE', '').lower()
        proxy_host = self.env_manager.get('NTUST_PROXY_HOST')
        proxy_port = self.env_manager.get('NTUST_PROXY_PORT')
        proxy_username = self.env_manager.get('NTUST_PROXY_USERNAME')
        proxy_password = self.env_manager.get('NTUST_PROXY_PASSWORD')
        
        if not proxy_type or not proxy_host or not proxy_port:
            logger.info("未配置代理伺服器，將使用直接連接")
            return
        
        # 構建代理 URL（用於日誌，不包含密碼）
        if proxy_username and proxy_password:
            proxy_url = f"{proxy_type}://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}"
            proxy_url_log = f"{proxy_type}://{proxy_username}:***@{proxy_host}:{proxy_port}"
        else:
            proxy_url = f"{proxy_type}://{proxy_host}:{proxy_port}"
            proxy_url_log = proxy_url
        
        # 設置代理
        if proxy_type in ['http', 'https']:
            self.session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            logger.info(f"已設置 HTTP/HTTPS 代理: {proxy_url_log}")
        elif proxy_type == 'socks5':
            # 使用 requests session scoped SOCKS5，避免全域 socket 汙染
            socks_proxy_url = proxy_url.replace('socks5://', 'socks5h://', 1)
            self.session.proxies = {
                'http': socks_proxy_url,
                'https': socks_proxy_url
            }
            logger.info(f"已設置 SOCKS5 代理（session scoped）: {proxy_url_log}")
        else:
            logger.warning(f"不支援的代理類型: {proxy_type}")
    
    def _is_proxy_configured(self):
        """檢查是否配置了代理（包括 SOCKS5）"""
        return is_proxy_configured(self.session.proxies, self.env_manager)
    
    def _get_proxy_info_for_logging(self):
        """獲取代理信息用於日誌記錄"""
        return get_proxy_info_for_logging(self.session.proxies, self.env_manager)
    
    def _log_proxy_status(self):
        """記錄當前代理配置狀態"""
        if self.session.proxies:
            _, proxy_details = self._get_proxy_info_for_logging()
            logger.info(f"當前 session 已配置代理{proxy_details}")
        else:
            logger.info("當前 session 未配置代理，將使用直接連接")
    
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
    
    def search_courses(
        self,
        semester: str = "",
        course_no: str = "",
        course_name: str = "",
        course_teacher: str = "",
        dimension: str = "",
        course_notes: str = "",
        campus_notes: str = "",
        language: str = "zh",
        **kwargs
    ) -> List[Dict]:
        """
        查詢課程
        
        Args:
            semester: 學年期，格式如 "1142" (114學年第2學期)
            course_no: 課程代碼
            course_name: 課程名稱
            course_teacher: 教師名稱
            dimension: 向度
            course_notes: 課程備註
            campus_notes: 校區備註
            language: 語言，預設 "zh"
            **kwargs: 其他查詢參數
        
        Returns:
            課程列表，每個課程為一個字典
        """
        if not semester:
            semester = get_default_semester(verify_ssl=self.verify_ssl)
        payload = {
            "Semester": semester,
            "CourseNo": course_no,
            "CourseName": course_name,
            "CourseTeacher": course_teacher,
            "Dimension": dimension,
            "CourseNotes": course_notes,
            "CampusNotes": campus_notes,
            "ForeignLanguage": kwargs.get("foreign_language", 0),
            "OnlyIntensive": kwargs.get("only_intensive", 0),
            "OnlyGeneral": kwargs.get("only_general", 0),
            # The school API really spells this key "OnleyNTUST"; the correctly-spelled
            # name is ignored, which used to let cross-school sections leak into results.
            "OnleyNTUST": kwargs.get("only_ntust", 0),
            "OnlyMaster": kwargs.get("only_master", 0),
            "OnlyUnderGraduate": kwargs.get("only_undergraduate", 0),
            "OnlyNode": kwargs.get("only_node", 0),
            "Language": language
        }
        
        self.last_search_failed = False
        try:
            req_start = time.perf_counter()
            # 記錄代理使用狀態（總是記錄，不只是 debug 模式）
            proxy_info, proxy_details = self._get_proxy_info_for_logging()
            
            # 決定日誌中顯示的課程名稱
            log_course_name = kwargs.get('display_name') or course_name or 'N/A'
            logger.info(f"發送課程查詢 API 請求 - {proxy_info}{proxy_details} | 課程代碼: {course_no or 'N/A'}, 課程名稱: {log_course_name}")
            
            # 檢查 socket 異常類是否可用（用於調試）
            try:
                import socket
                has_gaierror = hasattr(socket, 'gaierror')
                logger.debug(f"Socket 異常類檢查 - gaierror 可用: {has_gaierror}")
            except:
                pass
            
            response = self.session.post(
                self.BASE_URL,
                json=payload,
                timeout=10,
                verify=self.verify_ssl
            )
            self.last_request_latency_ms = (time.perf_counter() - req_start) * 1000
            response.raise_for_status()
            
            # 記錄成功響應（包含代理使用信息）
            logger.info(f"課程查詢 API 請求成功 - {proxy_info}{proxy_details} | 返回 {len(response.json()) if response.json() else 0} 個課程")
            
            return response.json()
        except requests.exceptions.SSLError as e:
            self.last_request_latency_ms = (time.perf_counter() - req_start) * 1000
            error_msg = str(e)
            logger.error(f"SSL 證書驗證錯誤: {error_msg}")
            logger.info("可能的解決方案：")
            logger.info("1. 設定環境變數禁用 SSL 驗證（不推薦）：")
            logger.info("   export NTUST_VERIFY_SSL=false")
            logger.info("   或在 Windows: set NTUST_VERIFY_SSL=false")
            logger.info("2. 更新 Python 的證書庫：")
            logger.info("   macOS: /Applications/Python\\ 3.x/Install\\ Certificates.command")
            logger.info("   或執行: pip install --upgrade certifi")
            logger.info("3. 如果確定要禁用驗證，可以在程式中設定 verify_ssl=False")
            self.last_search_failed = True
            return []
        except requests.exceptions.Timeout as e:
            self.last_request_latency_ms = (time.perf_counter() - req_start) * 1000
            from .utils import _is_network_disconnected
            if _is_network_disconnected(e):
                logger.error(f"API 請求超時：當前網路已中斷 - {e}")
                # 重新拋出異常，讓上層能夠檢測到網路中斷
                raise
            else:
                logger.error(f"API 請求超時: {e}")
            self.last_search_failed = True
            return []
        except requests.exceptions.ConnectionError as e:
            self.last_request_latency_ms = (time.perf_counter() - req_start) * 1000
            from .utils import _is_network_disconnected
            # 檢查是否是 socket.gaierror 相關錯誤
            error_str = str(e)
            if _is_network_disconnected(e):
                logger.error(f"API 連接錯誤：當前網路已中斷 - {e}")
                # 重新拋出異常，讓上層能夠檢測到網路中斷
                raise
            elif 'gaierror' in error_str.lower() or 'socket' in error_str.lower():
                logger.error(f"API 連接錯誤（可能是 socket 異常類問題）: {e}")
                logger.debug(f"錯誤類型: {type(e)}, 錯誤詳情: {error_str}")
            else:
                logger.error(f"API 連接錯誤: {e}")
            self.last_search_failed = True
            return []
        except requests.exceptions.RequestException as e:
            self.last_request_latency_ms = (time.perf_counter() - req_start) * 1000
            from .utils import _is_network_disconnected
            error_str = str(e)
            if _is_network_disconnected(e):
                logger.error(f"API 請求錯誤：當前網路已中斷 - {e}")
                # 重新拋出異常，讓上層能夠檢測到網路中斷
                raise
            elif 'gaierror' in error_str.lower():
                logger.error(f"API 請求錯誤（socket.gaierror 問題）: {e}")
                logger.debug(f"錯誤類型: {type(e)}, 錯誤詳情: {error_str}")
            else:
                logger.error(f"API 請求錯誤: {e}")
            self.last_search_failed = True
            return []
        except AttributeError as e:
            self.last_request_latency_ms = (time.perf_counter() - req_start) * 1000
            # 捕獲可能的 socket.gaierror 屬性錯誤
            error_str = str(e)
            if 'gaierror' in error_str.lower():
                logger.error(f"API 請求錯誤（socket.gaierror 屬性不存在）: {e}")
                logger.debug(f"錯誤類型: {type(e)}, 錯誤詳情: {error_str}")
                # 嘗試修復：恢復 socket 異常類
                try:
                    import socket
                    if hasattr(socket, '_original_gaierror') and socket._original_gaierror:
                        socket.gaierror = socket._original_gaierror
                        logger.info("已嘗試恢復 socket.gaierror")
                except:
                    pass
            self.last_search_failed = True
            return []
    
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
