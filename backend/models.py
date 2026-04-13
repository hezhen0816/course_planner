from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

try:
    from .config import DEFAULT_VERIFY_SSL
except ImportError:  # pragma: no cover
    from config import DEFAULT_VERIFY_SSL

class SyncRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    profile_key: str | None = None
    persist_to_supabase: bool = True
    verify_ssl: bool = DEFAULT_VERIFY_SSL


class HistoryImportRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    profile_key: str | None = None
    persist_to_supabase: bool = True
    verify_ssl: bool = DEFAULT_VERIFY_SSL


class MoodleAssignmentsRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    profile_key: str | None = None
    persist_to_supabase: bool = True
    verify_ssl: bool = DEFAULT_VERIFY_SSL


class CourseRow(BaseModel):
    course_code: str
    course_name: str
    credits: float | str
    required_type: str
    professor: str
    note: str


class ScheduleSlot(BaseModel):
    weekday_key: str
    weekday_label: str
    period: str
    time: str
    course_name: str
    location: str
    raw: str


class ScheduleEntryPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    weekday_key: str
    weekday_label: str
    title: str
    time_range: str
    slot_times: list[str] = []
    room: str
    instructor: str
    accent: str


class SyncResponse(BaseModel):
    profile_key: str
    school_account: str
    student_name: str | None = None
    source_url: str
    page_title: str
    total_credits_text: str
    total_credits: float | None
    synced_at: datetime
    course_count: int
    scheduled_slot_count: int
    schedule_entry_count: int
    persisted_to_supabase: bool
    courses: list[CourseRow]
    slots: list[ScheduleSlot]
    schedule_entries: list[ScheduleEntryPayload]


class HistoryCourseRecord(BaseModel):
    category: str
    course_code: str
    course_name: str
    academic_term: str
    grade: str
    earned_credits: str


class HistoryImportResponse(BaseModel):
    profile_key: str
    school_account: str
    student_name: str | None = None
    student_no: str | None = None
    department: str | None = None
    status: str | None = None
    source_url: str
    page_title: str
    imported_at: datetime
    record_count: int
    persisted_to_supabase: bool
    summary_texts: list[str]
    records: list[HistoryCourseRecord]


class MoodleAssignmentItem(BaseModel):
    due_at: datetime
    title: str
    summary: str
    course_name: str
    action_label: str
    action_url: str
    event_url: str
    overdue: bool


class MoodleAssignmentsResponse(BaseModel):
    profile_key: str
    school_account: str
    source_url: str
    page_title: str
    timeline_filter: str
    synced_at: datetime
    item_count: int
    persisted_to_supabase: bool
    items: list[MoodleAssignmentItem]


class TRRoomMeeting(BaseModel):
    room: str
    node: str
    course_no: str
    course_name: str
    teacher: str


class TRRoomStatusResponse(BaseModel):
    semester: str
    queried_at: datetime
    target: str
    node: str | None
    node_label: str
    is_class_time: bool
    room: str | None = None
    room_is_free: bool | None = None
    room_meetings: list[TRRoomMeeting] = Field(default_factory=list)
    free_rooms: list[str]
    busy_rooms: list[str]
    total_rooms: int
    note: str
