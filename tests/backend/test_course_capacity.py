from __future__ import annotations

from backend.course_capacity import (
    ADD_DROP_PERIOD,
    capacity_limit,
    format_enrolled,
    remaining_seats,
    selected_count,
)


def _course(r1, r2, chosen=10):
    return {"Restrict1": r1, "Restrict2": r2, "ChooseStudent": chosen}


def test_preregistration_prefers_restrict1_and_add_drop_prefers_restrict2() -> None:
    course = _course("30", "45")
    assert capacity_limit(course, "A06") == 30
    assert capacity_limit(course, ADD_DROP_PERIOD) == 45


def test_9999_falls_back_to_the_other_field() -> None:
    # 1151 學期有 810 門課是這個形狀；只看 Restrict1 會誤判成無上限
    course = _course("9999", "55")
    assert capacity_limit(course, "A06") == 55
    assert capacity_limit(course, ADD_DROP_PERIOD) == 55
    assert remaining_seats(course, "A06") == 45


def test_both_unlimited_means_no_cap() -> None:
    course = _course("9999", "9999")
    assert capacity_limit(course, "A06") is None
    assert remaining_seats(course, "A06") is None
    assert format_enrolled(course, "A06") == "10"


def test_blank_and_unparseable_values_are_treated_as_absent() -> None:
    assert capacity_limit(_course("", ""), "A06") is None
    assert capacity_limit(_course(None, None), "A06") is None
    assert capacity_limit(_course("abc", "40"), "A06") == 40


def test_selected_count_handles_null_and_strings() -> None:
    assert selected_count({"ChooseStudent": None}) == 0
    assert selected_count({"ChooseStudent": "12"}) == 12
    assert selected_count({}) == 0


def test_over_enrolled_courses_report_negative_remaining() -> None:
    # 授權加簽會讓已選人數超過上限，1151 學期有 319 門是這種
    assert remaining_seats(_course("55", "55", chosen=72), "A06") == -17
    assert format_enrolled(_course("55", "55", chosen=72), "A06") == "72/55"


def test_ntu_system_students_do_not_count_against_the_ntust_cap() -> None:
    # 台大/師大學生有自己的名額（NTURestrict/NTNURestrict），分母是本校上限，
    # 分子就必須是本校選課人數，不能用 AllStudent
    course = {"Restrict1": "50", "Restrict2": "50", "ChooseStudent": 45, "ThreeStudent": 5, "AllStudent": 50}
    assert selected_count(course) == 45
    assert remaining_seats(course, "A06") == 5
