from __future__ import annotations

from fastapi.testclient import TestClient

from backend import app as backend_app


def test_course_search_endpoint_supports_name_and_code(monkeypatch) -> None:
    courses = [
        {
            "Semester": "1142",
            "CourseNo": "CS3005301",
            "CourseName": "物件導向程式設計",
            "CourseTeacher": "戴文凱",
            "CreditPoint": "3",
            "RequireOption": "R",
            "ClassRoomNo": "TR-311",
            "Node": "T6,T7,T8",
            "Contents": "學號單數",
            "ChooseStudent": 43,
            "Restrict2": "55",
        },
        {
            "Semester": "1142",
            "CourseNo": "CS1010301",
            "CourseName": "物件導向程式設計實習",
            "CourseTeacher": "戴文凱",
            "CreditPoint": "1",
            "RequireOption": "R",
            "ClassRoomNo": "RB-509",
            "Node": "W6,W7,W8",
        },
    ]
    monkeypatch.setattr(
        backend_app,
        "fetch_query_courses_filtered",
        lambda semester, course_no, course_name, verify_ssl: courses,
    )
    client = TestClient(backend_app.app)

    by_name = client.get("/api/courses/search", params={"semester": "1142", "q": "物件導向程式設計", "mode": "name"})
    by_code = client.get("/api/courses/search", params={"semester": "1142", "q": "CS3005301", "mode": "code"})

    assert by_name.status_code == 200
    assert [item["course_no"] for item in by_name.json()] == ["CS3005301", "CS1010301"]
    assert by_code.status_code == 200
    assert by_code.json()[0]["node"] == "T6,T7,T8"


def test_course_search_endpoint_supports_partial_course_name(monkeypatch) -> None:
    courses = [
        {
            "Semester": "1151",
            "CourseNo": "PE127A011",
            "CourseName": "體育(撞球)(上)",
            "CourseTeacher": "蔡尚明",
            "CreditPoint": "0",
            "RequireOption": "R",
            "ClassRoomNo": "",
            "Node": "M9,M10",
        },
        {
            "Semester": "1151",
            "CourseNo": "PE127A022",
            "CourseName": "體育(撞球)(上)",
            "CourseTeacher": "蔡尚明",
            "CreditPoint": "0",
            "RequireOption": "R",
            "ClassRoomNo": "",
            "Node": "T6,T7",
        },
        {
            "Semester": "1151",
            "CourseNo": "PE127B011",
            "CourseName": "體育(羽球)(上)",
            "CourseTeacher": "林教授",
            "CreditPoint": "0",
            "RequireOption": "R",
            "ClassRoomNo": "",
            "Node": "W1,W2",
        },
    ]
    monkeypatch.setattr(
        backend_app,
        "fetch_query_courses_filtered",
        lambda semester, course_no, course_name, verify_ssl: courses,
    )
    client = TestClient(backend_app.app)

    response = client.get("/api/courses/search", params={"semester": "1151", "q": "撞球", "mode": "name"})

    assert response.status_code == 200
    assert [item["course_no"] for item in response.json()] == ["PE127A011", "PE127A022"]


def test_course_search_endpoint_merges_same_course_code_nodes(monkeypatch) -> None:
    courses = [
        {
            "Semester": "1151",
            "CourseNo": "CS2002302",
            "CourseName": "資料結構",
            "CourseTeacher": "陳冠宇",
            "CreditPoint": "3",
            "RequireOption": "R",
            "ClassRoomNo": "",
            "Node": "M3,M4",
        },
        {
            "Semester": "1151",
            "CourseNo": "CS2002302",
            "CourseName": "資料結構",
            "CourseTeacher": "陳冠宇",
            "CreditPoint": "3",
            "RequireOption": "R",
            "ClassRoomNo": "",
            "Node": "W4",
        },
    ]
    monkeypatch.setattr(
        backend_app,
        "fetch_query_courses_filtered",
        lambda semester, course_no, course_name, verify_ssl: courses,
    )
    client = TestClient(backend_app.app)

    response = client.get("/api/courses/search", params={"semester": "1151", "q": "CS2002302", "mode": "code"})

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["course_no"] == "CS2002302"
    assert response.json()[0]["node"] == "M3, M4, W4"
