from __future__ import annotations

from collections.abc import Callable

import requests
from fastapi import APIRouter, Header, HTTPException

try:
    from ..credentials import CredentialStoreError
    from ..models import GpaApiKeyResponse, GpaApiKeySaveRequest
except ImportError:  # pragma: no cover - supports PYTHONPATH=backend imports.
    from credentials import CredentialStoreError
    from models import GpaApiKeyResponse, GpaApiKeySaveRequest


UserContextResolver = Callable[[str | None], tuple[str, str]]


def create_gpa_api_key_router(
    current_user_context: UserContextResolver,
    read_status: Callable[[str], dict[str, object]],
    write_key: Callable[[str, str, bool], dict[str, object]],
    delete_key: Callable[[str], dict[str, object]],
) -> APIRouter:
    """CRUD for the caller's own myNTUST GPA token.

    The token itself is never returned: the Web only needs to know whether one is
    stored, and course search uses it server-side.
    """
    router = APIRouter(prefix="/api/gpa-api-key", tags=["gpa"])

    def _context(authorization: str | None) -> str:
        user_id, _access_token = current_user_context(authorization)
        return user_id

    @router.get("", response_model=GpaApiKeyResponse)
    def get_gpa_api_key(authorization: str | None = Header(default=None)) -> GpaApiKeyResponse:
        user_id = _context(authorization)
        try:
            return GpaApiKeyResponse.model_validate(read_status(user_id))
        except CredentialStoreError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"讀取 GPA API 設定失敗：{exc}") from exc

    @router.put("", response_model=GpaApiKeyResponse)
    def save_gpa_api_key(
        request: GpaApiKeySaveRequest,
        authorization: str | None = Header(default=None),
    ) -> GpaApiKeyResponse:
        user_id = _context(authorization)
        try:
            return GpaApiKeyResponse.model_validate(
                write_key(user_id, request.apiKey.strip(), request.enabled)
            )
        except CredentialStoreError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"保存 GPA API 設定失敗：{exc}") from exc

    @router.delete("", response_model=GpaApiKeyResponse)
    def remove_gpa_api_key(authorization: str | None = Header(default=None)) -> GpaApiKeyResponse:
        user_id = _context(authorization)
        try:
            return GpaApiKeyResponse.model_validate(delete_key(user_id))
        except CredentialStoreError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"刪除 GPA API 設定失敗：{exc}") from exc

    return router
