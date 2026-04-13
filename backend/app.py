from __future__ import annotations

from typing import Any

import requests
from fastapi import FastAPI, HTTPException

try:
    from .config import DEFAULT_VERIFY_SSL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
    from .history import fetch_history_records
    from .models import (
        HistoryImportRequest,
        HistoryImportResponse,
        MoodleAssignmentsRequest,
        MoodleAssignmentsResponse,
        SyncRequest,
        SyncResponse,
        TRRoomStatusResponse,
    )
    from .moodle import fetch_moodle_assignments
    from .schedule import fetch_schedule
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
        build_tr_meetings,
        fetch_current_query_semester,
        fetch_query_courses,
        label_for_node,
        next_node_from_datetime,
        node_from_datetime,
        normalize_room_code,
        occupied_meetings,
        room_sort_key,
    )
except ImportError:  # pragma: no cover - supports Railway backend/ cwd imports.
    from config import DEFAULT_VERIFY_SSL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
    from history import fetch_history_records
    from models import (
        HistoryImportRequest,
        HistoryImportResponse,
        MoodleAssignmentsRequest,
        MoodleAssignmentsResponse,
        SyncRequest,
        SyncResponse,
        TRRoomStatusResponse,
    )
    from moodle import fetch_moodle_assignments
    from schedule import fetch_schedule
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
        build_tr_meetings,
        fetch_current_query_semester,
        fetch_query_courses,
        label_for_node,
        next_node_from_datetime,
        node_from_datetime,
        normalize_room_code,
        occupied_meetings,
        room_sort_key,
    )


app = FastAPI(title="Course Compass Sync API", version="0.1.0")


@app.get("/health")
def healthcheck() -> dict[str, Any]:
    return {
        "ok": True,
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY),
        "timestamp": now().isoformat(),
    }


@app.get("/api/tr-rooms/status", response_model=TRRoomStatusResponse)
def get_tr_room_status(
    room: str | None = None,
    semester: str | None = None,
    node: str | None = None,
    target: str = "current",
    refresh: bool = False,
    verify_ssl: bool = DEFAULT_VERIFY_SSL,
) -> TRRoomStatusResponse:
    try:
        query_time = now().replace(microsecond=0)
        selected_semester = semester or fetch_current_query_semester(verify_ssl=verify_ssl)
        courses = fetch_query_courses(selected_semester, refresh=refresh, verify_ssl=verify_ssl)
        meetings = build_tr_meetings(courses)
        normalized_target = target.lower()
        if normalized_target not in {"current", "next"}:
            raise RuntimeError("target 只能是 current 或 next。")
        selected_node = node.upper() if node else (
            next_node_from_datetime(query_time) if normalized_target == "next" else node_from_datetime(query_time)
        )
        occupied = occupied_meetings(meetings, selected_node)
        rooms = sorted({meeting.room for meeting in meetings}, key=room_sort_key)
        busy_rooms = [room_code for room_code in rooms if room_code in occupied]
        free_rooms = [room_code for room_code in rooms if room_code not in occupied]

        requested_room = normalize_room_code(room)
        room_meetings = occupied.get(requested_room, []) if requested_room else []
        return TRRoomStatusResponse(
            semester=selected_semester,
            queried_at=query_time,
            target=normalized_target,
            node=selected_node,
            node_label=label_for_node(selected_node, query_time),
            is_class_time=selected_node is not None,
            room=requested_room,
            room_is_free=None if requested_room is None else not room_meetings,
            room_meetings=room_meetings,
            free_rooms=free_rooms,
            busy_rooms=busy_rooms,
            total_rooms=len(rooms),
            note="結果只代表正式課表，不包含臨時借用、活動或現場使用狀態。",
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"課程查詢系統請求失敗：{exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/schedule/sync", response_model=SyncResponse)
def sync_schedule(request: SyncRequest) -> SyncResponse:
    try:
        payload = fetch_schedule(request.username, request.password, request.verify_ssl)
        synced_at = now().isoformat()
        response_payload = {
            **payload,
            "profile_key": request.profile_key or request.username,
            "school_account": request.username,
            "student_name": None,
            "synced_at": synced_at,
            "course_count": len(payload["courses"]),
            "scheduled_slot_count": len(payload["slots"]),
            "schedule_entry_count": len(payload["schedule_entries"]),
            "persisted_to_supabase": False,
        }
        if request.persist_to_supabase:
            response_payload["persisted_to_supabase"] = persist_snapshot(
                profile_key=response_payload["profile_key"],
                school_account=request.username,
                payload=response_payload,
            )
        return SyncResponse.model_validate(response_payload)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"課表系統請求失敗：{exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/schedule/{profile_key}", response_model=SyncResponse)
def get_latest_schedule(profile_key: str) -> SyncResponse:
    try:
        payload = load_snapshot(profile_key)
        if payload is None:
            raise HTTPException(status_code=404, detail="Supabase 找不到此 profile 的課表快照。")
        payload = ensure_schedule_entry_slot_times(payload)
        return SyncResponse.model_validate(payload)
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/history/import", response_model=HistoryImportResponse)
def import_history(request: HistoryImportRequest) -> HistoryImportResponse:
    try:
        payload = fetch_history_records(request.username, request.password, request.verify_ssl)
        response_payload = {
            **payload,
            "profile_key": request.profile_key or request.username,
            "school_account": request.username,
            "imported_at": now().isoformat(),
            "record_count": len(payload["records"]),
            "persisted_to_supabase": False,
        }
        if request.persist_to_supabase:
            response_payload["persisted_to_supabase"] = persist_history_snapshot(
                profile_key=response_payload["profile_key"],
                school_account=request.username,
                payload=response_payload,
            )
        return HistoryImportResponse.model_validate(response_payload)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"歷史修課系統請求失敗：{exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/history/{profile_key}", response_model=HistoryImportResponse)
def get_latest_history(profile_key: str) -> HistoryImportResponse:
    try:
        payload = load_history_snapshot(profile_key)
        if payload is None:
            raise HTTPException(status_code=404, detail="Supabase 找不到此 profile 的歷史修課紀錄。")
        return HistoryImportResponse.model_validate(payload)
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/moodle/assignments/sync", response_model=MoodleAssignmentsResponse)
def sync_moodle_assignments(request: MoodleAssignmentsRequest) -> MoodleAssignmentsResponse:
    try:
        payload = fetch_moodle_assignments(request.username, request.password, request.verify_ssl)
        response_payload = {
            **payload,
            "profile_key": request.profile_key or request.username,
            "school_account": request.username,
            "synced_at": now().isoformat(),
            "item_count": len(payload["items"]),
            "persisted_to_supabase": False,
        }
        if request.persist_to_supabase:
            response_payload["persisted_to_supabase"] = persist_moodle_assignments_snapshot(
                profile_key=response_payload["profile_key"],
                school_account=request.username,
                payload=response_payload,
            )
        return MoodleAssignmentsResponse.model_validate(response_payload)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Moodle 待繳事項請求失敗：{exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/moodle/assignments/{profile_key}", response_model=MoodleAssignmentsResponse)
def get_latest_moodle_assignments(profile_key: str) -> MoodleAssignmentsResponse:
    try:
        payload = load_moodle_assignments_snapshot(profile_key)
        if payload is None:
            raise HTTPException(status_code=404, detail="Supabase 找不到此 profile 的待繳事項快照。")
        return MoodleAssignmentsResponse.model_validate(payload)
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
