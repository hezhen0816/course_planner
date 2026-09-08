from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

try:
    from .api.courses import create_courses_router
    from .api.health import create_health_router
    from .api.official_selection import create_official_selection_router
    from .api.planner import create_planner_router
    from .api.school_credentials import create_school_credentials_router
    from .api.sync import create_sync_router
    from .api.tr_rooms import create_tr_rooms_router
    from .credentials import (
        delete_school_credentials,
        get_school_credentials_secret,
        get_school_credentials_status,
        put_school_credentials,
        resolve_user_id,
    )
    from .history import fetch_history_records
    from .moodle import fetch_moodle_assignments
    from .official_selection import get_official_selection_client
    from .planner_pdf import parse_requirement_pdf
    from .schedule import fetch_schedule
    from .school_sessions import (
        delete_school_session,
        load_school_session_state,
        official_session_expires_at,
        save_school_session_state,
    )
    from .snapshots import (
        ensure_schedule_entry_slot_times,
        load_history_snapshot,
        load_moodle_assignments_snapshot,
        load_snapshot,
        persist_history_snapshot,
        persist_moodle_assignments_snapshot,
        persist_snapshot,
    )
    from .time_utils import now
    from .tr_rooms import (
        fetch_query_courses_filtered,
    )
    from .services import session_context
except ImportError:  # pragma: no cover - supports Railway backend/ cwd imports.
    from api.courses import create_courses_router
    from api.health import create_health_router
    from api.official_selection import create_official_selection_router
    from api.planner import create_planner_router
    from api.school_credentials import create_school_credentials_router
    from api.sync import create_sync_router
    from api.tr_rooms import create_tr_rooms_router
    from credentials import (
        delete_school_credentials,
        get_school_credentials_secret,
        get_school_credentials_status,
        put_school_credentials,
        resolve_user_id,
    )
    from history import fetch_history_records
    from moodle import fetch_moodle_assignments
    from official_selection import get_official_selection_client
    from planner_pdf import parse_requirement_pdf
    from schedule import fetch_schedule
    from school_sessions import (
        delete_school_session,
        load_school_session_state,
        official_session_expires_at,
        save_school_session_state,
    )
    from snapshots import (
        ensure_schedule_entry_slot_times,
        load_history_snapshot,
        load_moodle_assignments_snapshot,
        load_snapshot,
        persist_history_snapshot,
        persist_moodle_assignments_snapshot,
        persist_snapshot,
    )
    from time_utils import now
    from tr_rooms import (
        fetch_query_courses_filtered,
    )
    from services import session_context


API_VERSION = "0.3.0"
OFFICIAL_SELECTION_CAPABILITIES = {
    "school_credentials": True,
    "school_sessions": True,
    "official_selection": True,
    "official_selection_actions": [
        "sync",
        "keep_alive",
        "join",
        "add_to_waitlist",
        "remove",
        "reorder",
    ],
}

app = FastAPI(title="Course Compass Sync API", version=API_VERSION)
app.add_middleware(
    CORSMiddleware,
    # The tailnet origin served by this backend, the Vercel-hosted web app
    # (production + preview URLs) and local Vite dev servers. Vercel pages can
    # only reach this backend when the browser is on the tailnet.
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://hezhen.taile9e4a0.ts.net",
        "https://course-compass.vercel.app",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+|https://course-compass-[a-z0-9-]+\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _current_user_context(authorization: str | None) -> tuple[str, str]:
    return session_context.current_user_context(authorization, lambda token: resolve_user_id(token))


def _authorization_context(authorization: str | None) -> tuple[str, str] | None:
    return session_context.authorization_context(authorization, lambda value: _current_user_context(value))


def _optional_authorization_context(authorization: str | None) -> tuple[str, str] | None:
    return session_context.optional_authorization_context(
        authorization,
        lambda value: _authorization_context(value),
    )


def _required_user_context(authorization: str | None) -> tuple[str, str]:
    return session_context.required_user_context(authorization, lambda value: _authorization_context(value))


def _assert_school_account_ownership(context: tuple[str, str], username: str) -> None:
    session_context.assert_school_account_ownership(
        context,
        username,
        lambda user_id, access_token: get_school_credentials_status(user_id, access_token),
    )


def _assert_owned_profile_key(context: tuple[str, str], profile_key: str) -> None:
    session_context.assert_owned_profile_key(
        context,
        profile_key,
        lambda user_id, access_token: get_school_credentials_status(user_id, access_token),
    )


def _saved_school_credentials(
    username: str,
    authorization: str | None,
    *,
    required: bool = False,
) -> tuple[str, str] | None:
    return session_context.saved_school_credentials(
        username,
        authorization,
        lambda value: _authorization_context(value),
        lambda user_id, access_token: get_school_credentials_secret(user_id, access_token),
        required=required,
    )


def _official_password(username: str, password: str | None, authorization: str | None) -> str | None:
    return session_context.official_password(
        username,
        password,
        authorization,
        lambda saved_username, saved_authorization: _saved_school_credentials(saved_username, saved_authorization),
    )


def _required_school_password(username: str, password: str | None, authorization: str | None) -> str:
    return session_context.required_school_password(
        username,
        password,
        authorization,
        lambda school_username, school_password, school_authorization: _official_password(
            school_username,
            school_password,
            school_authorization,
        ),
    )


def _ensure_official_session(
    profile_key: str,
    username: str,
    password: str | None,
    authorization: str | None,
    verify_ssl: bool,
) -> Any:
    return session_context.ensure_official_session(
        profile_key,
        username,
        password,
        authorization,
        verify_ssl,
        lambda selected_profile_key: get_official_selection_client(selected_profile_key),
        lambda value: _optional_authorization_context(value),
        lambda client, selected_username, context, selected_verify_ssl: _reuse_official_session(
            client,
            selected_username,
            context,
            selected_verify_ssl,
        ),
        lambda selected_username, selected_password, selected_authorization: _official_password(
            selected_username,
            selected_password,
            selected_authorization,
        ),
        lambda context, selected_username, client: _persist_official_session(context, selected_username, client),
    )


def _persist_official_session(
    context: tuple[str, str] | None,
    username: str,
    client: Any,
) -> None:
    session_context.persist_official_session(
        context,
        username,
        client,
        lambda *args, **kwargs: save_school_session_state(*args, **kwargs),
        lambda: official_session_expires_at(),
        lambda: datetime.now(timezone.utc),
    )


def _delete_official_session(context: tuple[str, str] | None, username: str | None = None) -> None:
    session_context.delete_official_session(
        context,
        username,
        lambda user_id, selected_username: delete_school_session(user_id, selected_username),
    )


def _reuse_official_session(
    client: Any,
    username: str,
    context: tuple[str, str] | None,
    verify_ssl: bool,
) -> bool:
    return session_context.reuse_official_session(
        client,
        username,
        context,
        verify_ssl,
        lambda selected_context, selected_username, selected_client: _persist_official_session(
            selected_context,
            selected_username,
            selected_client,
        ),
        lambda selected_context, selected_username=None: _delete_official_session(
            selected_context,
            selected_username,
        ),
        lambda user_id, selected_username: load_school_session_state(user_id, selected_username),
    )


def _require_official_action_confirmation(confirmed: bool) -> None:
    session_context.require_official_action_confirmation(confirmed)


app.include_router(create_health_router(API_VERSION, OFFICIAL_SELECTION_CAPABILITIES))
app.include_router(
    create_courses_router(
        lambda semester, course_no, course_name, verify_ssl, include_cross_school=False: fetch_query_courses_filtered(
            semester,
            course_no=course_no,
            course_name=course_name,
            verify_ssl=verify_ssl,
            include_cross_school=include_cross_school,
        )
    )
)
app.include_router(create_planner_router(lambda pdf_bytes, filename: parse_requirement_pdf(pdf_bytes, filename)))
app.include_router(
    create_school_credentials_router(
        lambda authorization: _current_user_context(authorization),
        lambda context, username: _delete_official_session(context, username),
        lambda user_id, access_token: get_school_credentials_status(user_id, access_token),
        lambda user_id, username, password, access_token: put_school_credentials(
            user_id,
            username,
            password,
            access_token,
        ),
        lambda user_id, access_token: delete_school_credentials(user_id, access_token),
    )
)
app.include_router(create_tr_rooms_router())
app.include_router(
    create_sync_router(
        lambda authorization: _required_user_context(authorization),
        lambda context, username: _assert_school_account_ownership(context, username),
        lambda context, profile_key: _assert_owned_profile_key(context, profile_key),
        lambda username, password, authorization: _required_school_password(username, password, authorization),
        lambda username, password, verify_ssl: fetch_schedule(username, password, verify_ssl),
        lambda username, password, verify_ssl: fetch_history_records(username, password, verify_ssl),
        lambda username, password, verify_ssl: fetch_moodle_assignments(username, password, verify_ssl),
        lambda profile_key, school_account, payload: persist_snapshot(profile_key, school_account, payload),
        lambda profile_key, school_account, payload: persist_history_snapshot(profile_key, school_account, payload),
        lambda profile_key, school_account, payload: persist_moodle_assignments_snapshot(
            profile_key,
            school_account,
            payload,
        ),
        lambda profile_key: load_snapshot(profile_key),
        lambda profile_key: load_history_snapshot(profile_key),
        lambda profile_key: load_moodle_assignments_snapshot(profile_key),
        lambda payload: ensure_schedule_entry_slot_times(payload),
        lambda: now().isoformat(),
    )
)
app.include_router(
    create_official_selection_router(
        lambda profile_key: get_official_selection_client(profile_key),
        lambda authorization: _required_user_context(authorization),
        lambda context, username: _assert_school_account_ownership(context, username),
        lambda context, username: session_context.official_client_key(context, username),
        lambda client, username, context, verify_ssl: _reuse_official_session(client, username, context, verify_ssl),
        lambda profile_key, username, password, authorization, verify_ssl: _ensure_official_session(
            profile_key,
            username,
            password,
            authorization,
            verify_ssl,
        ),
        lambda context, username, client: _persist_official_session(context, username, client),
        lambda context, username: _delete_official_session(context, username),
        lambda username, password, authorization: _official_password(username, password, authorization),
        lambda username, authorization: _saved_school_credentials(username, authorization),
        lambda confirmed: _require_official_action_confirmation(confirmed),
        lambda: now().isoformat(),
    )
)


# --- Optional: serve the built web app from the same origin --------------------
# When web/dist exists next to backend/ (the home Windows deployment), the SPA is
# served at "/" and API routes keep their /api prefix. Same origin means no CORS
# and no mixed-content issues behind `tailscale serve`.
WEB_DIST_DIR = Path(os.environ.get("WEB_DIST_DIR") or Path(__file__).resolve().parent.parent / "web" / "dist")

if (WEB_DIST_DIR / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=WEB_DIST_DIR / "assets"), name="web-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_web_app(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path in {"docs", "openapi.json", "redoc"}:
            raise HTTPException(status_code=404)
        candidate = (WEB_DIST_DIR / full_path).resolve()
        if full_path and candidate.is_file() and WEB_DIST_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(WEB_DIST_DIR / "index.html")
