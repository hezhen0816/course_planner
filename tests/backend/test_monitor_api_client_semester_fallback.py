from __future__ import annotations

from backend.monitor.api_client import NTUSTCourseAPI


def test_get_course_by_code_falls_back_to_newer_semester(monkeypatch) -> None:
    api = NTUSTCourseAPI.__new__(NTUSTCourseAPI)
    api.verify_ssl = False

    searched_semesters: list[str] = []

    def fake_search_courses(*, semester: str, course_no: str, display_name: str = ""):
        searched_semesters.append(semester)
        if semester == "1151":
            return [{"Semester": "1151", "CourseNo": course_no, "CourseName": "造型藝術與創意美學"}]
        return []

    monkeypatch.setattr(api, "search_courses", fake_search_courses)
    monkeypatch.setattr(
        "backend.monitor.api_client.fetch_semester_candidates",
        lambda verify_ssl=True: ["1151", "1142", "1141"],
    )
    monkeypatch.setattr(
        "backend.monitor.api_client.get_default_semester",
        lambda verify_ssl=True: "1142",
    )

    course = api.get_course_by_code("ADG015301", semester="1142")

    assert course is not None
    assert course["Semester"] == "1151"
    assert searched_semesters == ["1142", "1151"]


def test_get_course_by_code_does_not_fall_back_on_transport_failure(monkeypatch) -> None:
    api = NTUSTCourseAPI.__new__(NTUSTCourseAPI)
    api.verify_ssl = False
    api.last_search_failed = False

    searched_semesters: list[str] = []

    def fake_search_courses(*, semester: str, course_no: str, display_name: str = ""):
        searched_semesters.append(semester)
        api.last_search_failed = True  # simulate timeout / connection error
        return []

    monkeypatch.setattr(api, "search_courses", fake_search_courses)
    monkeypatch.setattr(
        "backend.monitor.api_client.fetch_semester_candidates",
        lambda verify_ssl=True: ["1152", "1151", "1142"],
    )

    course = api.get_course_by_code("ADG015301", semester="1151")

    assert course is None
    assert searched_semesters == ["1151"]


def test_get_course_by_code_never_falls_back_to_older_semester(monkeypatch) -> None:
    api = NTUSTCourseAPI.__new__(NTUSTCourseAPI)
    api.verify_ssl = False
    api.last_search_failed = False

    searched_semesters: list[str] = []

    def fake_search_courses(*, semester: str, course_no: str, display_name: str = ""):
        searched_semesters.append(semester)
        return [{"Semester": semester}] if semester == "1142" else []

    monkeypatch.setattr(api, "search_courses", fake_search_courses)
    monkeypatch.setattr(
        "backend.monitor.api_client.fetch_semester_candidates",
        lambda verify_ssl=True: ["1151", "1142", "1141"],
    )

    assert api.get_course_by_code("ADG015301", semester="1151") is None
    assert "1142" not in searched_semesters
