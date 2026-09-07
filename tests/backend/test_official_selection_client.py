from __future__ import annotations

from backend import official_selection


class FakeHTTPResponse:
    def __init__(self, text: str = "", url: str = "https://example.test/a02", status_code: int = 200) -> None:
        self.text = text
        self.url = url
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None


def test_official_selection_workspace_prefers_course_list_schedule_when_a02_schedule_differs(monkeypatch) -> None:
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
              <td>2</td><td>9:10～10:00</td><td></td><td>數位系統設計</td><td>數位系統設計</td>
              <td></td><td></td><td></td><td></td>
            </tr>
          </table>
        </div>
      </body>
    </html>
    """
    course_list_rows = official_selection._schedule_rows_from_slots(
        [
            {
                "weekday_label": "星期四",
                "period": "6",
                "course_name": "數位系統設計",
            },
            {
                "weekday_label": "星期四",
                "period": "7",
                "course_name": "數位系統設計",
            },
        ]
    )

    client = official_selection.OfficialSelectionClient()
    monkeypatch.setattr(client, "_fetch_course_list_schedule_rows", lambda verify_ssl: course_list_rows)

    payload = client._workspace_payload(FakeHTTPResponse(text=html), verify_ssl=False)

    assert payload["schedule_rows"][1]["星期二"] == ""
    assert payload["schedule_rows"][1]["星期三"] == ""
    assert payload["schedule_rows"][5]["星期四"] == "數位系統設計"
    assert payload["schedule_rows"][6]["星期四"] == "數位系統設計"
    assert "官方功課表由正式課程清單校正。" in payload["notices"]


def test_official_selection_arraydata_form_rows_matches_saveidx_shape() -> None:
    rows = official_selection._arraydata_form_rows(
        [
            ["志願序", "課碼", "課程名稱", "取消加入"],
            ["1", "PE127A022", "體育(撞球)(上)", "取消加入"],
        ]
    )

    assert rows == [
        ("Arraydata[0][0]", "志願序"),
        ("Arraydata[0][1]", "課碼"),
        ("Arraydata[0][2]", "課程名稱"),
        ("Arraydata[0][3]", "取消加入"),
        ("Arraydata[1][0]", "1"),
        ("Arraydata[1][1]", "PE127A022"),
        ("Arraydata[1][2]", "體育(撞球)(上)"),
        ("Arraydata[1][3]", "取消加入"),
    ]


def test_official_selection_client_exports_and_restores_session_cookies() -> None:
    client = official_selection.OfficialSelectionClient()
    client.session.cookies.set(
        "OfficialSelection.Auth",
        "cookie-secret",
        domain="courseselection.ntust.edu.tw",
        path="/",
    )
    client.is_logged_in = True

    restored = official_selection.OfficialSelectionClient()

    assert restored.restore_session_state(client.export_session_state()) is True
    assert (
        restored.session.cookies.get(
            "OfficialSelection.Auth",
            domain="courseselection.ntust.edu.tw",
            path="/",
        )
        == "cookie-secret"
    )
    assert restored.is_logged_in is True


def test_official_selection_join_refreshes_workspace_before_and_after_post(monkeypatch) -> None:
    events: list[object] = []
    workspace_html = """
    <html>
      <head><title>初選登記選課</title></head>
      <body>
        <table id="cartTable">
          <tr><td>志願序</td><td>課碼</td><td>課程名稱</td><td>取消加入</td></tr>
          <tr><td>1</td><td>CS2002302</td><td>資料結構</td><td>取消加入</td></tr>
        </table>
        <div id="loginModal">
          <table>
            <tr><th>節次</th><th>時間</th><th>星期一</th><th>星期二</th></tr>
            <tr><td>1</td><td>08:10～09:00</td><td>資料結構</td><td></td></tr>
          </table>
        </div>
      </body>
    </html>
    """

    class FakeSession:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

        def post(self, endpoint: str, **kwargs: object) -> FakeHTTPResponse:
            events.append(("post", endpoint, kwargs["data"]))
            return FakeHTTPResponse(url=endpoint)

    client = official_selection.OfficialSelectionClient()
    client.session = FakeSession()  # type: ignore[assignment]

    def fake_get_workspace_page(verify_ssl: bool) -> FakeHTTPResponse:
        events.append(("get_workspace", verify_ssl))
        return FakeHTTPResponse(text=workspace_html)

    monkeypatch.setattr(client, "_get_workspace_page", fake_get_workspace_page)
    monkeypatch.setattr(client, "_fetch_course_list_schedule_rows", lambda verify_ssl: [])

    payload = client.join_course(" cs2002302 ", verify_ssl=False)

    assert events == [
        ("get_workspace", False),
        (
            "post",
            official_selection.INITIAL_SELECTION_JOIN_URL,
            {"CourseNo": "CS2002302", "type": 1},
        ),
        ("get_workspace", False),
    ]
    assert payload["session_valid"] is True
    assert payload["registered_courses"][0]["course_no"] == "CS2002302"


def test_official_selection_waitlist_uses_single_add_endpoint(monkeypatch) -> None:
    events: list[object] = []
    workspace_html = """
    <html>
      <body>
        <div id="draggable"></div>
        <table id="cartTable">
          <tr><td>志願序</td><td>課碼</td><td>課程名稱</td><td>取消加入</td></tr>
        </table>
      </body>
    </html>
    """

    class FakeSession:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

        def post(self, endpoint: str, **kwargs: object) -> FakeHTTPResponse:
            events.append(("post", endpoint, kwargs["data"]))
            return FakeHTTPResponse(url=endpoint)

    client = official_selection.OfficialSelectionClient()
    client.session = FakeSession()  # type: ignore[assignment]

    def fake_get_workspace_page(verify_ssl: bool) -> FakeHTTPResponse:
        events.append(("get_workspace", verify_ssl))
        return FakeHTTPResponse(text=workspace_html)

    monkeypatch.setattr(client, "_get_workspace_page", fake_get_workspace_page)
    monkeypatch.setattr(client, "_fetch_course_list_schedule_rows", lambda verify_ssl: [])

    client.add_course_to_waitlist(" ba2208302 ", verify_ssl=False)

    assert events == [
        ("get_workspace", False),
        (
            "post",
            official_selection.INITIAL_SELECTION_EXTRA_JOIN_URL,
            {"CourseNo": "BA2208302", "type": 3},
        ),
        ("get_workspace", False),
    ]


def test_official_selection_join_preserves_action_rejection_notice(monkeypatch) -> None:
    events: list[object] = []
    workspace_html = """
    <html>
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
            <div class="table-cell">PE139A021</div>
            <div class="table-cell">體育(重量訓練)(上)</div>
            <div class="table-cell">翁睿忻</div>
            <div class="table-cell">加入登記</div>
          </div>
        </div>
      </body>
    </html>
    """
    rejection_html = """
    <html>
      <body>
        <div class="modal-body">本門課設有選課班級條件，您不符合條件，無法選修。</div>
      </body>
    </html>
    """

    class FakeSession:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

        def post(self, endpoint: str, **kwargs: object) -> FakeHTTPResponse:
            events.append(("post", endpoint, kwargs["data"]))
            return FakeHTTPResponse(text=rejection_html, url=endpoint)

    client = official_selection.OfficialSelectionClient()
    client.session = FakeSession()  # type: ignore[assignment]

    def fake_get_workspace_page(verify_ssl: bool) -> FakeHTTPResponse:
        events.append(("get_workspace", verify_ssl))
        return FakeHTTPResponse(text=workspace_html)

    monkeypatch.setattr(client, "_get_workspace_page", fake_get_workspace_page)
    monkeypatch.setattr(client, "_fetch_course_list_schedule_rows", lambda verify_ssl: [])

    payload = client.join_course("pe139a021", verify_ssl=False)

    assert events == [
        ("get_workspace", False),
        (
            "post",
            official_selection.INITIAL_SELECTION_JOIN_URL,
            {"CourseNo": "PE139A021", "type": 1},
        ),
        ("get_workspace", False),
    ]
    assert payload["notices"][0] == "本門課設有選課班級條件，您不符合條件，無法選修。"
    assert payload["notices"][1] == "請直接拖拉「登記志願清單」中的課程來變更志願序。"


def test_official_selection_join_reads_rejection_notice_from_refreshed_workspace(monkeypatch) -> None:
    events: list[object] = []
    workspace_html = """
    <html>
      <body>
        <div class="panel">訊息公告(點選可展開、收合) ※請直接拖拉「登記志願清單」中的課程來變更志願序。</div>
        <script>alert('本門課設有選課班級條件，您不符合條件，無法選修。');</script>
        <div id="draggable">
          <div class="table-row">
            <div class="table-cell">課碼</div>
            <div class="table-cell">課程名稱</div>
            <div class="table-cell">上課教師</div>
            <div class="table-cell">加入登記</div>
          </div>
          <div class="table-row">
            <div class="table-cell">BA2208302</div>
            <div class="table-cell">成本會計</div>
            <div class="table-cell">郭啟賢</div>
            <div class="table-cell">加入登記</div>
          </div>
        </div>
      </body>
    </html>
    """

    class FakeSession:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

        def post(self, endpoint: str, **kwargs: object) -> FakeHTTPResponse:
            events.append(("post", endpoint, kwargs["data"]))
            return FakeHTTPResponse(text="", url=endpoint)

    client = official_selection.OfficialSelectionClient()
    client.session = FakeSession()  # type: ignore[assignment]

    def fake_get_workspace_page(verify_ssl: bool) -> FakeHTTPResponse:
        events.append(("get_workspace", verify_ssl))
        return FakeHTTPResponse(text=workspace_html)

    monkeypatch.setattr(client, "_get_workspace_page", fake_get_workspace_page)
    monkeypatch.setattr(client, "_fetch_course_list_schedule_rows", lambda verify_ssl: [])

    payload = client.join_course("ba2208302", verify_ssl=False)

    assert events == [
        ("get_workspace", False),
        (
            "post",
            official_selection.INITIAL_SELECTION_JOIN_URL,
            {"CourseNo": "BA2208302", "type": 1},
        ),
        ("get_workspace", False),
    ]
    assert payload["notices"][0] == "本門課設有選課班級條件，您不符合條件，無法選修。"
