from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import requests
from fastapi import APIRouter, Header, HTTPException, Query

try:
    from ..config import DEFAULT_VERIFY_SSL, SEMESTERS_INFO_URL
    from ..gpa import fetch_course_gpa
    from ..models import CourseSearchResult, CourseSemesterInfo
except ImportError:  # pragma: no cover - supports PYTHONPATH=backend imports.
    from config import DEFAULT_VERIFY_SSL, SEMESTERS_INFO_URL
    from gpa import fetch_course_gpa
    from models import CourseSearchResult, CourseSemesterInfo


CourseSearchFetcher = Callable[..., list[dict[str, Any]]]


def create_courses_router(fetch_courses_filtered: CourseSearchFetcher) -> APIRouter:
    router = APIRouter(prefix="/api/courses", tags=["courses"])

    @router.get("/semesters", response_model=list[CourseSemesterInfo])
    def get_course_semesters() -> list[CourseSemesterInfo]:
        try:
            response = requests.get(
                SEMESTERS_INFO_URL,
                headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
                timeout=30,
                verify=DEFAULT_VERIFY_SSL,
            )
            response.raise_for_status()
            semesters = response.json()
            if not isinstance(semesters, list):
                raise RuntimeError("課程查詢系統回傳格式不是學期清單。")
            return [
                CourseSemesterInfo(
                    semester=str(item.get("Semester") or ""),
                    english_label=str(item.get("EngSemester") or ""),
                    current=bool(item.get("CurrentSemester")),
                )
                for item in semesters
                if item.get("Semester")
            ]
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"課程查詢系統請求失敗：{exc}") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/search", response_model=list[CourseSearchResult])
    def search_courses(
        semester: str,
        q: str = Query(min_length=1),
        mode: str = "name",
        refresh: bool = False,
        include_cross_school: bool = False,
        gpa_api_key: str | None = Header(default=None, alias="X-GPA-API-Key"),
    ) -> list[CourseSearchResult]:
        try:
            if mode not in {"name", "code"}:
                raise RuntimeError("mode 只能是 name 或 code。")
            courses = fetch_courses_filtered(
                semester,
                course_no=q.strip() if mode == "code" else "",
                course_name=q.strip() if mode == "name" else "",
                verify_ssl=DEFAULT_VERIFY_SSL,
                include_cross_school=include_cross_school,
            )
            normalized_query = _normalize_course_lookup_text(q)
            filtered = []
            for course in courses:
                course_no = str(course.get("CourseNo") or "")
                course_name = str(course.get("CourseName") or "")
                normalized_course_name = _normalize_course_lookup_text(course_name)
                normalized_course_no = _normalize_course_lookup_text(course_no)
                if mode == "name" and normalized_query not in normalized_course_name:
                    continue
                if mode == "code" and normalized_query not in normalized_course_no:
                    continue
                filtered.append(_course_search_result(course))
            results = _sort_course_search_results(_merge_course_search_results(filtered), q)
            if gpa_api_key:
                _attach_gpa_to_courses(results, gpa_api_key, DEFAULT_VERIFY_SSL)
            return results
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"課程查詢系統請求失敗：{exc}") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router


def _attach_gpa_to_courses(courses: list[CourseSearchResult], api_key: str, verify_ssl: bool) -> None:
    for course in courses:
        if not course.course_no:
            continue
        course.gpa, course.gpa_status = fetch_course_gpa(course.course_no, api_key, verify_ssl)


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_course_lookup_text(value: str) -> str:
    return value.strip().replace(" ", "").replace("（", "(").replace("）", ")").lower()


def _course_search_result(course: dict[str, Any]) -> CourseSearchResult:
    return CourseSearchResult(
        semester=str(course.get("Semester") or ""),
        course_no=str(course.get("CourseNo") or ""),
        course_name=str(course.get("CourseName") or ""),
        teacher=str(course.get("CourseTeacher") or ""),
        dimension=str(course.get("Dimension") or ""),
        credits=_as_float(course.get("CreditPoint")),
        require_option=str(course.get("RequireOption") or ""),
        classroom=str(course.get("ClassRoomNo") or ""),
        node=str(course.get("Node") or ""),
        contents=str(course.get("Contents") or ""),
        selected_count=_as_int(course.get("ChooseStudent")),
        capacity=_as_int(course.get("Restrict2")),
    )


def _merge_course_search_results(courses: list[CourseSearchResult]) -> list[CourseSearchResult]:
    merged: dict[tuple[str, str, str, str, str], CourseSearchResult] = {}

    for course in courses:
        key = (
            course.semester,
            course.course_no,
            course.course_name,
            course.teacher,
            course.require_option,
        )
        existing = merged.get(key)
        if existing is None:
            merged[key] = course.model_copy()
            continue

        existing.node = _merge_token_text(existing.node, course.node)
        existing.classroom = _merge_token_text(existing.classroom, course.classroom)
        existing.contents = _merge_note_text(existing.contents, course.contents)
        existing.dimension = existing.dimension or course.dimension
        existing.selected_count = _max_optional_int(existing.selected_count, course.selected_count)
        existing.capacity = _max_optional_int(existing.capacity, course.capacity)

    return list(merged.values())


def _sort_course_search_results(courses: list[CourseSearchResult], query: str) -> list[CourseSearchResult]:
    normalized_query = _normalize_course_lookup_text(query)
    return sorted(
        courses,
        key=lambda course: (
            _normalize_course_lookup_text(course.course_name) != normalized_query,
            course.course_no,
            course.course_name,
            course.teacher,
        ),
    )


def _merge_token_text(left: str, right: str) -> str:
    tokens: list[str] = []
    seen: set[str] = set()
    for value in (left, right):
        for token in re.split(r"[,、/\s]+", value):
            normalized = token.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            tokens.append(normalized)
    return ", ".join(tokens)


def _merge_note_text(left: str, right: str) -> str:
    notes: list[str] = []
    for note in (left.strip(), right.strip()):
        if note and note not in notes:
            notes.append(note)
    return "；".join(notes)


def _max_optional_int(left: int | None, right: int | None) -> int | None:
    values = [value for value in (left, right) if value is not None]
    return max(values) if values else None
