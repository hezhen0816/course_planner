import os
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger('ntust_monitor')

class CryptoError(RuntimeError):
    pass


class CryptoManager:
    def __init__(self):
        self.key = os.getenv('ENCRYPTION_KEY')
        self.fernet = None
        if self.key:
            try:
                self.fernet = Fernet(self.key.encode())
            except Exception as e:
                logger.error(f"初始化加密模組失敗，請檢查 ENCRYPTION_KEY 格式: {e}")
        else:
            logger.warning("未設定 ENCRYPTION_KEY，加密功能將無法使用")

    def encrypt(self, data: str) -> str:
        if not data:
            return data
        if not self.fernet:
            raise CryptoError("未設定 ENCRYPTION_KEY，無法加密")
        try:
            return self.fernet.encrypt(data.encode()).decode()
        except Exception as e:
            # 絕不把明文當密文回傳（原本 fail-open 會讓明文被標成已加密）
            raise CryptoError(f"加密失敗: {e}") from e

    def is_ciphertext(self, data: str) -> bool:
        """True if `data` is a Fernet token encrypted with the current key."""
        if not data or not self.fernet:
            return False
        try:
            self.fernet.decrypt(data.encode())
            return True
        except Exception:
            return False

    def decrypt(self, data: str) -> str:
        if not data:
            return data
        if not self.fernet:
            raise CryptoError("未設定 ENCRYPTION_KEY，無法解密")
        try:
            return self.fernet.decrypt(data.encode()).decode()
        except Exception as e:
            # 絕不把密文當明文回傳（會被拿去當密碼登入而鎖帳號）
            raise CryptoError(f"解密失敗: {e}") from e
