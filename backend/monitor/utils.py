"""
工具函數模組
提供通用的工具函數
"""

import logging
import time
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple
from ..logging_setup import get_logger

try:
    import requests
except ImportError:
    requests = None  # 如果沒有安裝 requests，設為 None


def setup_logging(level: int = logging.INFO, log_to_file: bool = True, log_to_console: bool = False) -> logging.Logger:
    """相容包裝：設定集中在 backend/logging_setup.py，由進入點呼叫一次。

    模組層級請改用 `get_logger(__name__)`；這支保留給既有呼叫端與 worker 進入點。
    """
    from ..logging_setup import configure_worker_logging

    return configure_worker_logging(level=level, log_to_file=log_to_file, log_to_console=log_to_console)

def find_course_by_identifier(
    courses: List[Any],
    identifier: Optional[str] = None,
    course_no: Optional[str] = None,
    course_name: Optional[str] = None,
    semester: Optional[str] = None
) -> Optional[Any]:
    """
    根據多種條件查找課程（統一匹配邏輯）
    
    Args:
        courses: 課程列表
        identifier: 課程唯一標識符（課程代碼、名稱或別名）
        course_no: 課程代碼
        course_name: 課程名稱
        semester: 學年期
        
    Returns:
        找到的課程，如果找不到則返回 None
    """
    for course in courses:
        matched = False
        
        # 優先使用 identifier 匹配
        if identifier:
            course_identifier = getattr(course, 'course_no', '') or \
                              getattr(course, 'course_name', '') or \
                              getattr(course, 'alias', '')
            if course_identifier == identifier:
                matched = True
        
        # 使用課程代碼和學年期匹配
        elif course_no and semester:
            if (getattr(course, 'course_no', '') == course_no and 
                getattr(course, 'semester', '') == semester):
                matched = True
        
        # 使用課程名稱和學年期匹配
        elif course_name and semester:
            if (getattr(course, 'course_name', '') == course_name and 
                getattr(course, 'semester', '') == semester):
                matched = True
        
        if matched:
            return course
    
    return None


def deep_compare_dict(dict1: Dict[str, Any], dict2: Dict[str, Any], 
                      exclude_keys: Optional[List[str]] = None) -> bool:
    """
    深度比較兩個字典，排除指定的鍵
    
    Args:
        dict1: 第一個字典
        dict2: 第二個字典
        exclude_keys: 要排除的鍵列表（例如：['last_check', 'timestamp']）
        
    Returns:
        如果字典相等（排除指定鍵後）則返回 True
    """
    if exclude_keys is None:
        exclude_keys = []
    
    # 獲取所有唯一的鍵
    all_keys = set(dict1.keys()) | set(dict2.keys())
    
    for key in all_keys:
        if key in exclude_keys:
            continue
        
        val1 = dict1.get(key)
        val2 = dict2.get(key)
        
        # 如果兩個值都是字典，遞歸比較
        if isinstance(val1, dict) and isinstance(val2, dict):
            if not deep_compare_dict(val1, val2, exclude_keys):
                return False
        # 如果兩個值都是列表，比較列表內容
        elif isinstance(val1, list) and isinstance(val2, list):
            if len(val1) != len(val2):
                return False
            for i, item1 in enumerate(val1):
                item2 = val2[i]
                if isinstance(item1, dict) and isinstance(item2, dict):
                    if not deep_compare_dict(item1, item2, exclude_keys):
                        return False
                elif item1 != item2:
                    return False
        # 其他情況直接比較
        elif val1 != val2:
            return False
    
    return True


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, 
                     exceptions: tuple = (Exception,)):
    """
    重試裝飾器
    
    Args:
        max_retries: 最大重試次數
        delay: 重試延遲（秒）
        exceptions: 要捕獲的異常類型
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
                    else:
                        raise
            if last_exception:
                raise last_exception
        return wrapper
    return decorator


def validate_semester(semester: str) -> bool:
    """
    驗證學年期格式
    
    Args:
        semester: 學年期字符串（格式：1142）
        
    Returns:
        如果格式正確則返回 True
    """
    if not semester or len(semester) != 4:
        return False
    try:
        year = int(semester[:3])
        term = int(semester[3])
        return 100 <= year <= 999 and 1 <= term <= 3
    except ValueError:
        return False


def sanitize_input(text: str, max_length: int = 100) -> str:
    """
    清理用戶輸入
    
    Args:
        text: 輸入文本
        max_length: 最大長度
        
    Returns:
        清理後的文本
    """
    if not text:
        return ""
    
    # 移除前後空白
    text = text.strip()
    
    # 限制長度
    if len(text) > max_length:
        text = text[:max_length]
    
    # 移除危險字符（可根據需要擴展）
    dangerous_chars = ['<', '>', '"', "'", '&']
    for char in dangerous_chars:
        text = text.replace(char, '')
    
    return text


def _is_network_disconnected(e: Exception) -> bool:
    """
    檢測是否是網路中斷錯誤
    
    Args:
        e: 異常對象
        
    Returns:
        如果是網路中斷則返回 True
    """
    if requests is None:
        return False
    
    error_str = str(e).lower()
    error_type = type(e).__name__.lower()
    
    # 檢查常見的網路中斷錯誤特徵
    network_disconnect_indicators = [
        'network is unreachable',
        'no route to host',
        'connection refused',
        'name or service not known',
        'temporary failure in name resolution',
        'nodename nor servname provided',
        'network unreachable',
        'host unreachable',
        'connection timed out',
        'errno 101',  # Network is unreachable
        'errno 113',  # No route to host
        'errno 110',  # Connection timed out
    ]
    
    # 檢查錯誤消息中是否包含網路中斷指標
    for indicator in network_disconnect_indicators:
        if indicator in error_str:
            return True
    
    # 檢查是否是 ConnectionError 或 Timeout，且包含特定錯誤
    if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        # 檢查底層異常
        if hasattr(e, 'args') and e.args:
            for arg in e.args:
                if isinstance(arg, Exception):
                    arg_str = str(arg).lower()
                    for indicator in network_disconnect_indicators:
                        if indicator in arg_str:
                            return True
        
        # 檢查是否是 DNS 解析失敗（通常是網路中斷的標誌）
        if 'gaierror' in error_str or 'name resolution' in error_str:
            return True
    
    return False


def handle_request_exception(e: Exception, operation: str = "操作") -> Tuple[bool, str]:
    """
    統一處理 requests 異常
    
    Args:
        e: 異常對象
        operation: 操作名稱（用於錯誤訊息）
        
    Returns:
        (是否成功, 錯誤訊息)
    """
    if requests is None:
        return False, f"{operation}失敗: requests 模組未安裝"
    
    # 檢查是否是網路中斷
    if _is_network_disconnected(e):
        if isinstance(e, requests.exceptions.Timeout):
            return False, f"{operation}超時：當前網路已中斷，請檢查網路連接"
        elif isinstance(e, requests.exceptions.ConnectionError):
            return False, f"無法連接到服務器：當前網路已中斷，請檢查網路連接"
        else:
            return False, f"{operation}失敗：當前網路已中斷，請檢查網路連接"
    
    if isinstance(e, requests.exceptions.Timeout):
        return False, f"{operation}超時，請檢查網絡連接"
    elif isinstance(e, requests.exceptions.ConnectionError):
        return False, f"無法連接到服務器，請檢查網絡連接"
    elif isinstance(e, requests.exceptions.SSLError):
        return False, f"SSL 證書驗證失敗: {str(e)}"
    elif isinstance(e, requests.exceptions.HTTPError):
        return False, f"HTTP 錯誤: {str(e)}"
    elif isinstance(e, requests.exceptions.RequestException):
        return False, f"{operation}請求失敗: {str(e)}"
    else:
        return False, f"{operation}發生未預期的錯誤: {str(e)}"


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """
    安全地解析 JSON 字符串
    
    Args:
        json_str: JSON 字符串
        default: 解析失敗時的默認值
        
    Returns:
        解析後的對象或默認值
    """
    import json
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def is_proxy_configured(session_proxies: Optional[Dict], env_manager: Optional['EnvManager'] = None) -> bool:
    """
    檢查是否配置了代理（包括 SOCKS5）
    
    Args:
        session_proxies: requests.Session 的 proxies 字典
        env_manager: 環境變數管理器實例（可選）
        
    Returns:
        如果配置了代理則返回 True，否則返回 False
    """
    # 檢查 session.proxies（HTTP/HTTPS 代理）
    if session_proxies:
        return True
    
    # 檢查環境變數（SOCKS5 代理可能不會設置 session.proxies）
    if env_manager is None:
        from .env_manager import EnvManager
        env_manager = EnvManager()
    
    proxy_type = env_manager.get('NTUST_PROXY_TYPE', '').lower()
    proxy_host = env_manager.get('NTUST_PROXY_HOST')
    proxy_port = env_manager.get('NTUST_PROXY_PORT')
    
    if proxy_type and proxy_host and proxy_port:
        return True
    
    return False


def get_proxy_info_for_logging(session_proxies: Optional[Dict], env_manager: Optional['EnvManager'] = None) -> Tuple[str, str]:
    """
    獲取代理信息用於日誌記錄
    
    Args:
        session_proxies: requests.Session 的 proxies 字典
        env_manager: 環境變數管理器實例（可選）
        
    Returns:
        (proxy_info, proxy_details) 元組
        - proxy_info: "使用代理" 或 "直接連接"
        - proxy_details: 代理詳細信息字符串（如 "(代理: host, 類型: TYPE)"）
    """
    if env_manager is None:
        from .env_manager import EnvManager
        env_manager = EnvManager()
    
    is_proxy = is_proxy_configured(session_proxies, env_manager)
    proxy_info = "使用代理" if is_proxy else "直接連接"
    proxy_details = ""
    
    if is_proxy:
        # 優先從 session.proxies 獲取（HTTP/HTTPS 代理）
        if session_proxies:
            http_proxy = session_proxies.get('http', '') or session_proxies.get('https', '')
            if http_proxy:
                if '@' in http_proxy:
                    proxy_host = http_proxy.split('@')[1].split(':')[0] if ':' in http_proxy.split('@')[1] else http_proxy.split('@')[1]
                    proxy_details = f" (代理: {proxy_host})"
                else:
                    proxy_details = f" (代理: {http_proxy})"
        else:
            # SOCKS5 代理，從環境變數獲取
            proxy_host = env_manager.get('NTUST_PROXY_HOST')
            proxy_type = env_manager.get('NTUST_PROXY_TYPE', '').upper()
            if proxy_host:
                proxy_details = f" (代理: {proxy_host}, 類型: {proxy_type})"
    
    return proxy_info, proxy_details



# 與 worker／client 共用同一棵 logger（setup_logging 設定的是 'ntust_monitor'）

logger = get_logger(__name__)


# --- 共用的 requests session 建立 ---------------------------------------------
# NTUST_VERIFY_SSL 原本在 config.py、api_client.py、enrollment.py 各解析一次，
# 代理設定也在 api_client 與 enrollment 各有一份幾乎相同的 _setup_proxy。
# 這裡收成一處，兩個 client 共用。

def resolve_verify_ssl(explicit: Optional[bool] = None, env_manager: Optional['EnvManager'] = None) -> bool:
    """None 代表依環境變數 NTUST_VERIFY_SSL 決定（預設開啟驗證）。"""
    if explicit is not None:
        return bool(explicit)
    if env_manager is None:
        from .env_manager import EnvManager
        env_manager = EnvManager()
    return (env_manager.get('NTUST_VERIFY_SSL', 'true') or 'true').lower() in ('true', '1', 'yes')


def proxies_from_env(env_manager: Optional['EnvManager'] = None) -> Optional[Dict[str, str]]:
    """由環境變數組出 requests 用的 proxies；未設定回 None。

    SOCKS5 一律轉成 socks5h（DNS 走代理）並走 session.proxies，
    不動全域 socket，避免汙染同一行程裡的其他連線。
    """
    if env_manager is None:
        from .env_manager import EnvManager
        env_manager = EnvManager()
    proxy_type = (env_manager.get('NTUST_PROXY_TYPE', '') or '').lower()
    host = env_manager.get('NTUST_PROXY_HOST')
    port = env_manager.get('NTUST_PROXY_PORT')
    if not proxy_type or not host or not port:
        return None

    username = env_manager.get('NTUST_PROXY_USERNAME')
    password = env_manager.get('NTUST_PROXY_PASSWORD')
    auth = f"{username}:{password}@" if username and password else ''
    url = f"{proxy_type}://{auth}{host}:{port}"

    if proxy_type in ('http', 'https'):
        pass
    elif proxy_type == 'socks5':
        url = url.replace('socks5://', 'socks5h://', 1)
    else:
        logger.warning(f"不支援的代理類型: {proxy_type}")
        return None
    return {'http': url, 'https': url}


def build_session(
    verify_ssl: Optional[bool] = None,
    proxies: Optional[Dict[str, str]] = None,
    user_agent: Optional[str] = None,
    env_manager: Optional['EnvManager'] = None,
) -> Tuple['requests.Session', bool]:
    """建立設定好 verify_ssl 與代理的 session，回傳 (session, verify_ssl)。

    `proxies` 傳入時直接採用（每位使用者自己的代理設定）；沒傳才讀環境變數。
    """
    import requests

    if env_manager is None:
        from .env_manager import EnvManager
        env_manager = EnvManager()
    resolved_verify = resolve_verify_ssl(verify_ssl, env_manager)

    session = requests.Session()
    if user_agent:
        session.headers.update({'User-Agent': user_agent})

    effective = proxies if proxies else proxies_from_env(env_manager)
    if effective:
        session.proxies.update(effective)
        _, details = get_proxy_info_for_logging(session.proxies, env_manager)
        logger.info(f"已設置代理{details}")
    else:
        logger.info("未配置代理伺服器，將使用直接連接")

    if not resolved_verify:
        logger.warning("SSL 證書驗證已禁用，這可能帶來安全風險")
    return session, resolved_verify
