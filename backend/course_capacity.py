"""Which seat-limit field applies, per the school's own course-query labels.

Confirmed 2026-09-08 from querycourse's app.js label table:

    ChooseStudent  本校選課人數
    ThreeStudent   系統學校選課人數（台大系統）
    AllStudent     選課總人數(本校/系統學校)
    Restrict1      本校初選人數上限(限舊生)
    Restrict2      本校加退選人數上限/新生第一學期初選人數上限
    NTURestrict / NTNURestrict  台大 / 師大名額

So the list column `50(45/5)` is 總人數(本校/系統學校), not "extra seats", and the
limit to compare against depends on the period: 初選 uses Restrict1, 加退選 uses
Restrict2. Both caps count NTUST students only — NTU/NTNU students have their own
quotas — so the matching numerator is ChooseStudent, not AllStudent.

Neither cap is enforced absolutely (authorised adds push ChooseStudent past it),
so "remaining" can be negative; callers treat <= 0 as full.
"""
from __future__ import annotations

from typing import Any

# 9999 is the school's "no cap in this phase" sentinel.
UNLIMITED = "9999"

ADD_DROP_PERIOD = "B01"


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == UNLIMITED:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def selected_count(course_info: dict[str, Any]) -> int:
    """本校選課人數；API 可能回 null 或字串。"""
    return _as_int(course_info.get("ChooseStudent")) or 0


def capacity_limit(course_info: dict[str, Any], enrollment_period: str = "A06") -> int | None:
    """該階段適用的本校人數上限；None 代表這門課在該階段沒有上限。

    先看階段對應的欄位，該欄位是 9999／空值時退回另一個：課程只填其中一邊很常見
    （1151 學期 2189 門課有 833 門 Restrict1=9999 但 Restrict2 是實際數字），
    只看單一欄位會把有上限的課誤判成無上限而永遠不通知額滿。
    """
    if str(enrollment_period or "").strip().upper() == ADD_DROP_PERIOD:
        preferred, fallback = "Restrict2", "Restrict1"
    else:
        preferred, fallback = "Restrict1", "Restrict2"
    limit = _as_int(course_info.get(preferred))
    if limit is None:
        limit = _as_int(course_info.get(fallback))
    return limit


def remaining_seats(course_info: dict[str, Any], enrollment_period: str = "A06") -> int | None:
    """剩餘名額；None 代表無上限（呼叫端一律視為有名額）。"""
    limit = capacity_limit(course_info, enrollment_period)
    if limit is None:
        return None
    return limit - selected_count(course_info)


def format_enrolled(course_info: dict[str, Any], enrollment_period: str = "A06") -> str:
    """給儀表板顯示的「已選/上限」；無上限時只顯示已選人數。"""
    limit = capacity_limit(course_info, enrollment_period)
    count = selected_count(course_info)
    return f"{count}/{limit}" if limit is not None else str(count)
