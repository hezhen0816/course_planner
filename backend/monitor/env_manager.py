"""
環境變數管理器
統一從環境變數讀取設定值
"""

import os
from typing import Optional


class EnvManager:
    """環境變數管理器，統一讀取環境變數"""

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        讀取環境變數

        Args:
            key: 環境變數名稱
            default: 找不到時的預設值

        Returns:
            環境變數的值，找不到則回傳 default
        """
        return os.environ.get(key, default)
