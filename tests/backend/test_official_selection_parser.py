from __future__ import annotations

from backend import official_selection


def test_official_selection_parser_reads_a02_workspace_div_tables() -> None:
    html = """
    <html>
      <head><title>初選登記選課</title></head>
      <body>
        <div class="panel">請直接拖拉「登記志願清單」中的課程來變更志願序。</div>
        <div id="draggable">
          <div class="table-row">
            <div class="table-cell">課碼</div>
            <div class="table-cell">課程名稱</div>
            <div class="table-cell">上課教師</div>
            <div class="table-cell">加入登記</div>
          </div>
          <div class="table-row">
            <div class="table-cell">PE127A022</div>
            <div class="table-cell">體育(撞球)(上)</div>
            <div class="table-cell">蔡尚明</div>
            <div class="table-cell"><span class="addbtn btn">加入登記</span></div>
          </div>
        </div>
        <table id="cartTable">
          <tr><td>志願序</td><td>課碼</td><td>課程名稱</td><td>取消加入</td></tr>
          <tr><td>1</td><td>FE1581701</td><td>休閒英文</td><td>取消加入</td></tr>
        </table>
        <div id="loginModal">
          <table>
            <tr><th>節次</th><th>星期一</th><th>星期二</th></tr>
            <tr><td>1</td><td></td><td>休閒英文<br>TR-312</td></tr>
          </table>
        </div>
      </body>
    </html>
    """

    parsed = official_selection.parse_a02_workspace(html)

    assert parsed["page_title"] == "初選登記選課"
    assert parsed["available_courses"] == [
        {"course_no": "PE127A022", "course_name": "體育(撞球)(上)", "teacher": "蔡尚明"}
    ]
    assert parsed["registered_courses"] == [
        {
            "priority": 1,
            "course_no": "FE1581701",
            "course_name": "休閒英文",
            "raw_priority": "1",
            "credits": None,
            "require_option": "",
            "teacher": "",
        }
    ]
    assert parsed["schedule_rows"] == [{"節次": "1", "星期一": "", "星期二": "休閒英文 TR-312"}]
    assert parsed["notices"] == ["請直接拖拉「登記志願清單」中的課程來變更志願序。"]


def test_official_selection_parser_reads_action_modal_message() -> None:
    html = """
    <html>
      <body>
        <div class="modal-body">
          本門課設有選課班級條件，您不符合條件，無法選修。
        </div>
      </body>
    </html>
    """

    assert official_selection._parse_action_response_notices(html) == [
        "本門課設有選課班級條件，您不符合條件，無法選修。"
    ]


def test_official_selection_parser_prefers_action_error_over_announcements() -> None:
    html = """
    <html>
      <body>
        <div>訊息公告(點選可展開、收合) ※請直接拖拉「登記志願清單」中的課程來變更志願序。</div>
        <script>alert('本門課設有選課班級條件，您不符合條件，無法選修。');</script>
      </body>
    </html>
    """

    assert official_selection._parse_action_response_notices(html) == [
        "本門課設有選課班級條件，您不符合條件，無法選修。"
    ]


def test_official_selection_parser_expands_split_class_restriction_message() -> None:
    html = """
    <html>
      <body>
        <div class="panel">訊息公告(點選可展開、收合) ※請直接拖拉「登記志願清單」中的課程來變更志願序。</div>
        <div id="Msg">
          <span>本門課設有選課</span>
          <span>班級條件</span>
          <span>您不符合條件</span>
          <span>無法選修。</span>
        </div>
      </body>
    </html>
    """

    assert official_selection._parse_action_response_notices(html) == [
        "本門課設有選課班級條件，您不符合條件，無法選修。"
    ]


def test_official_selection_parser_keeps_full_script_alert_before_regex_fallback() -> None:
    html = """
    <html>
      <body>
        <script>alert("這門課遴選不開放選修，所以無法選修。");</script>
      </body>
    </html>
    """

    assert official_selection._parse_action_response_notices(html) == [
        "這門課遴選不開放選修，所以無法選修。"
    ]


def test_official_selection_parser_maps_schedule_weekday_columns_by_position() -> None:
    html = """
    <html>
      <body>
        <div id="loginModal">
          <table>
            <tr>
              <th>節次</th><th>時間</th><th>星期一</th><th>星期二</th><th>星期三</th>
              <th>星期四</th><th>星期五</th><th>星期六</th><th>星期日</th>
            </tr>
            <tr>
              <td>6</td><td>13:20～14:10</td><td></td><td>體育(撞球)(上)（1）</td><td></td>
              <td>數位系統設計</td><td></td><td></td><td></td>
            </tr>
            <tr>
              <td>7</td><td>14:20～15:10</td><td></td><td>體育(撞球)(上)（1）</td><td></td>
              <td>數位系統設計</td><td></td><td></td><td></td>
            </tr>
          </table>
        </div>
      </body>
    </html>
    """

    parsed = official_selection.parse_a02_workspace(html)

    assert parsed["schedule_rows"][0]["時間"] == "13:20～14:10"
    assert parsed["schedule_rows"][0]["星期二"] == "體育(撞球)(上)（1）"
    assert parsed["schedule_rows"][0]["星期四"] == "數位系統設計"
    assert parsed["schedule_rows"][1]["星期二"] == "體育(撞球)(上)（1）"


def test_official_selection_schedule_rows_from_synced_slots() -> None:
    rows = official_selection._schedule_rows_from_slots(
        [
            {
                "weekday_label": "星期二",
                "period": "6",
                "course_name": "體育(撞球)(上)",
            },
            {
                "weekday_label": "星期二",
                "period": "7",
                "course_name": "體育(撞球)(上)",
            },
            {
                "weekday_label": "星期四",
                "period": "6",
                "course_name": "數位系統設計",
            },
        ]
    )

    assert rows[5]["節次"] == "6"
    assert rows[5]["星期二"] == "體育(撞球)(上)"
    assert rows[5]["星期四"] == "數位系統設計"
    assert rows[6]["星期二"] == "體育(撞球)(上)"
