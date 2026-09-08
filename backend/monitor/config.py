"""
配置管理模組
管理監控的課程列表和設定
"""

import json
import os
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from .env_manager import EnvManager
from .utils import setup_logging

# 設置日誌
logger = setup_logging()


@dataclass
class CourseConfig:
    """課程配置"""
    course_no: str = ""  # 課程代碼
    course_name: str = ""  # 課程名稱（如果沒有課程代碼，則使用名稱）
    semester: str = ""  # 學年期（空字串時自動抓官方最新學期）
    alias: str = ""  # 別名（用於顯示）
    auto_enroll: bool = False  # 是否啟用自動加選
    max_enroll_attempts: int = 3  # 最大加選嘗試次數
    attempt_count: int = 0  # 已嘗試加選次數（資料庫來源；worker 重啟不歸零）
    
    def __post_init__(self):
        """初始化後處理"""
        if not self.semester:
            from .semester import get_default_semester

            self.semester = get_default_semester()
        if not self.alias:
            self.alias = self.course_no or self.course_name


@dataclass
class MonitorConfig:
    """監控配置"""
    courses: List[CourseConfig]
    check_interval: int = 30  # 檢查間隔（秒）- 固定時間模式時使用
    check_interval_type: str = "fixed"  # 檢查間隔類型：fixed（固定時間）或 random（隨機範圍）
    check_interval_min: Optional[int] = None  # 隨機範圍最小值（秒）
    check_interval_max: Optional[int] = None  # 隨機範圍最大值（秒）
    verify_ssl: Optional[bool] = None  # SSL 證書驗證（None=自動判斷）
    student_id: Optional[str] = None  # 學號（用於自動加選）
    student_password: Optional[str] = None  # 密碼（用於自動加選，建議使用環境變數）
    max_notifications: int = 6  # 最多顯示的名額通知數量
    max_system_notifications: int = 20  # 最多顯示的系統通知數量
    config_check_interval: int = 5  # 配置文件檢查間隔（秒，用於熱重載）
    
    def to_dict(self) -> Dict:
        """轉換為字典（不包含敏感資訊）"""
        result = {
            "courses": [asdict(course) for course in self.courses],
            "check_interval": self.check_interval,
            "check_interval_type": self.check_interval_type,
            "check_interval_min": self.check_interval_min,
            "check_interval_max": self.check_interval_max,
            "verify_ssl": self.verify_ssl,
            "max_notifications": self.max_notifications,
            "max_system_notifications": self.max_system_notifications,
            "config_check_interval": self.config_check_interval
        }
        # 注意：student_id 和 student_password 不再保存到配置文件
        # 這些敏感資訊應該存儲在 .env 檔案中
        return result
    
    @classmethod
    def from_dict(cls, data: Dict, env_manager: Optional['EnvManager'] = None) -> 'MonitorConfig':
        """從字典建立配置"""
        courses = [CourseConfig(**course_data) for course_data in data.get("courses", [])]
        
        # 從環境變數讀取敏感資訊
        if env_manager is None:
            from .env_manager import EnvManager
            env_manager = EnvManager()
        
        # 優先從環境變數讀取學號和密碼
        student_id = env_manager.get('NTUST_STUDENT_ID') or data.get("student_id", None)
        student_password = env_manager.get('NTUST_STUDENT_PASSWORD') or data.get("student_password", None)
        
        return cls(
            courses=courses,
            check_interval=data.get("check_interval", 30),
            check_interval_type=data.get("check_interval_type", "fixed"),
            check_interval_min=data.get("check_interval_min", None),
            check_interval_max=data.get("check_interval_max", None),
            verify_ssl=data.get("verify_ssl", None),
            student_id=student_id,
            student_password=student_password,
            max_notifications=data.get("max_notifications", 6),
            max_system_notifications=data.get("max_system_notifications", 20),
            config_check_interval=data.get("config_check_interval", 5)
        )


class ConfigManager:
    """配置管理器"""
    
    DEFAULT_CONFIG_FILE = "config/monitor_config.json"
    
    @staticmethod
    def _get_base_dir() -> str:
        """取得配置檔案應該建立的基礎目錄"""
        # 使用當前工作目錄
        # repo root (backend/monitor/config.py -> three levels up), independent of cwd
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    def __init__(self, config_file: Optional[str] = None):
        if config_file:
            # 如果指定了絕對路徑，直接使用
            if os.path.isabs(config_file):
                self.config_file = config_file
            else:
                # 相對路徑，建立在基礎目錄
                self.config_file = os.path.join(self._get_base_dir(), config_file)
        else:
            # 使用預設檔名，建立在基礎目錄
            self.config_file = os.path.join(self._get_base_dir(), self.DEFAULT_CONFIG_FILE)
        self.config: Optional[MonitorConfig] = None
        # 初始化環境變數管理器
        self.env_manager = EnvManager()
    
    def get_config_dir(self) -> str:
        """取得配置檔案所在目錄"""
        return os.path.dirname(os.path.abspath(self.config_file))
    
    def load_config(self) -> MonitorConfig:
        """載入配置檔案"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config = MonitorConfig.from_dict(data, self.env_manager)
                    return self.config
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"載入配置檔案錯誤: {e}")
                logger.info("使用預設配置")
        
        # 如果沒有配置檔案或載入失敗，使用預設配置
        self.config = MonitorConfig(courses=[])
        
        # 如果配置檔案不存在，自動建立一個預設配置檔案
        if not os.path.exists(self.config_file):
            try:
                # 確保目錄存在
                config_dir = os.path.dirname(self.config_file)
                if config_dir and not os.path.exists(config_dir):
                    os.makedirs(config_dir, exist_ok=True)
                # 建立預設配置檔案
                self.save_config(self.config)
            except Exception as e:
                logger.warning(f"無法建立預設配置檔案 {self.config_file}: {e}")
        
        return self.config
    
    def save_config(self, config: MonitorConfig):
        """儲存配置檔案"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
            self.config = config
        except Exception as e:
            logger.error(f"儲存配置檔案錯誤: {e}")
    
    def add_course(
        self,
        course_no: str = "",
        course_name: str = "",
        semester: str = "",
        alias: str = "",
        auto_enroll: bool = False,
        max_enroll_attempts: int = 3
    ) -> bool:
        """
        新增監控課程
        
        Args:
            course_no: 課程代碼
            course_name: 課程名稱
            semester: 學年期
            alias: 別名
            auto_enroll: 是否啟用自動加選
            max_enroll_attempts: 最大加選嘗試次數
            
        Returns:
            如果成功新增則返回 True，如果課程已存在則返回 False
        """
        if not self.config:
            self.load_config()
        
        course = CourseConfig(
            course_no=course_no,
            course_name=course_name,
            semester=semester,
            alias=alias,
            auto_enroll=auto_enroll,
            max_enroll_attempts=max_enroll_attempts
        )
        
        # 檢查是否已存在
        for existing in self.config.courses:
            if (existing.course_no == course_no and course_no) or \
               (existing.course_name == course_name and course_name and not course_no):
                logger.warning(f"課程已存在: {existing.alias}")
                return False
        
        self.config.courses.append(course)
        self.save_config(self.config)
        logger.info(f"已新增監控課程: {course.alias}")
        return True
    
    def remove_course(self, identifier: str) -> bool:
        """
        移除監控課程（根據課程代碼、名稱或別名）
        
        Args:
            identifier: 課程代碼、名稱或別名
            
        Returns:
            如果成功移除則返回 True，如果找不到課程則返回 False
        """
        if not self.config:
            self.load_config()
        
        original_count = len(self.config.courses)
        self.config.courses = [
            course for course in self.config.courses
            if course.course_no != identifier and
               course.course_name != identifier and
               course.alias != identifier
        ]
        
        if len(self.config.courses) < original_count:
            self.save_config(self.config)
            logger.info(f"已移除課程: {identifier}")
            return True
        else:
            logger.warning(f"找不到課程: {identifier}")
            return False
    
    def list_courses(self) -> List[CourseConfig]:
        """列出所有監控課程"""
        if not self.config:
            self.load_config()
        return self.config.courses.copy()
