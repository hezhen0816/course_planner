import logging
from typing import Optional

from cryptography.fernet import Fernet

from ..credentials import CredentialStoreError, _fernet
try:
    from ..logging_setup import get_logger
except ImportError:  # pragma: no cover - supports `uvicorn app:app --app-dir backend`
    from logging_setup import get_logger

logger = get_logger(__name__)


class CryptoError(RuntimeError):
    pass


class CryptoManager:
    """Fernet for user_settings secrets (smtp_password, resend_api_key).

    Uses the same SCHOOL_CREDENTIALS_ENCRYPTION_SECRET as app_private.school_credentials,
    so the worker needs exactly one secret. ENCRYPTION_KEY was retired on 2026-09-08.
    """

    def __init__(self):
        self.fernet: Optional[Fernet] = None
        try:
            self.fernet = _fernet()
        except CredentialStoreError as e:
            logger.warning(f"未設定 SCHOOL_CREDENTIALS_ENCRYPTION_SECRET，user_settings 的敏感欄位將無法加解密：{e}")

    def encrypt(self, data: str) -> str:
        if not data:
            return data
        if not self.fernet:
            raise CryptoError("未設定 SCHOOL_CREDENTIALS_ENCRYPTION_SECRET，無法加密")
        try:
            return self.fernet.encrypt(data.encode()).decode()
        except Exception as e:
            # 絕不把明文當密文回傳（原本 fail-open 會讓明文被標成已加密）
            raise CryptoError(f"加密失敗: {e}") from e

    def is_ciphertext(self, data: str) -> bool:
        """True if `data` is a Fernet token encrypted with the current secret."""
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
            raise CryptoError("未設定 SCHOOL_CREDENTIALS_ENCRYPTION_SECRET，無法解密")
        try:
            return self.fernet.decrypt(data.encode()).decode()
        except Exception as e:
            # 絕不把密文當明文回傳（會被拿去當密碼登入而鎖帳號）
            raise CryptoError(f"解密失敗: {e}") from e
