from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from backend import ntust_common as nc
from backend.monitor.enrollment import EnrollmentClient

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sso" / "login_page.html"
LOGIN_URL = "https://ssoam2.ntust.edu.tw/account/login?ReturnUrl=%2Fconnect%2Fauthorize%3Fclient_id%3DCourseSelection"


class _Resp:
    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url


def _soup() -> BeautifulSoup:
    return BeautifulSoup(FIXTURE.read_text(encoding="utf-8"), "html.parser")


def test_login_page_hidden_captcha_containers_are_not_reported_as_captcha() -> None:
    soup = _soup()
    assert soup.find(attrs={"name": "cf-turnstile-response"}) is not None  # fixture really has them
    assert nc.captcha_required(soup) is False
    assert nc.find_error_text(soup) is None


def test_visible_captcha_widget_is_detected() -> None:
    soup = BeautifulSoup('<form><div class="cf-turnstile"></div><input name="cf-turnstile-response"></form>', "html.parser")
    assert nc.captcha_required(soup) is True
    assert "CAPTCHA" in (nc.find_error_text(soup) or "")


def test_monitor_failure_reason_on_plain_login_page_is_not_captcha() -> None:
    client = EnrollmentClient.__new__(EnrollmentClient)
    reason = client._extract_sso_failure_reason(FIXTURE.read_text(encoding="utf-8"), LOGIN_URL)
    assert "CAPTCHA" not in reason
    assert "停留在 SSO 頁面" in reason


def test_both_login_flows_build_the_same_post() -> None:
    """離線比對：ntust_common 與 monitor 對同一份登入頁產生的 POST URL 與欄位完全相同。"""
    soup = _soup()
    form = nc.first_form(soup)
    common = nc.parse_hidden_inputs(form)
    common.update(Username="U", Password="P")
    common.setdefault("captcha", "")
    common_url = urljoin(LOGIN_URL, form.get("action", ""))

    monitor = {"Username": "U", "Password": "P", "captcha": ""}
    csrf = form.find("input", {"name": "__RequestVerificationToken"})
    monitor["__RequestVerificationToken"] = csrf.get("value", "")
    for hidden in form.find_all("input", {"type": "hidden"}):
        name = hidden.get("name")
        if name and name != "__RequestVerificationToken":
            monitor[name] = hidden.get("value", "")
    action = form.get("action", "/")
    monitor_url = action if action.startswith("http") else f"https://ssoam2.ntust.edu.tw{action}"

    assert common_url == monitor_url == "https://ssoam2.ntust.edu.tw/"
    assert common == monitor


def test_login_page_is_stuck_and_needs_no_callback() -> None:
    resp = _Resp(FIXTURE.read_text(encoding="utf-8"), LOGIN_URL)
    assert nc._stuck_on_sso_login(resp) is True
    assert nc.requires_hidden_form_callback(resp) is False


def test_callback_detection_scans_past_a_leading_non_oidc_form() -> None:
    html = """
    <form action="/account/logout" method="post"><input type="hidden" name="x" value="1"></form>
    <form action="https://courseselection.ntust.edu.tw/signin-oidc" method="post">
      <input type="hidden" name="code" value="abc"><input type="hidden" name="state" value="s">
    </form>
    """
    resp = _Resp(html, "https://ssoam2.ntust.edu.tw/connect/authorize/callback")
    assert nc.requires_hidden_form_callback(resp) is True


def test_login_page_with_signin_oidc_in_return_url_is_not_a_callback() -> None:
    url = (
        "https://ssoam2.ntust.edu.tw/account/login?ReturnUrl=%2Fconnect%2Fauthorize%3Fclient_id%3DCourseSelection"
        "%26redirect_uri%3Dhttps%253A%252F%252Fcourseselection.ntust.edu.tw%252Fsignin-oidc"
    )
    assert nc.requires_hidden_form_callback(_Resp(FIXTURE.read_text(encoding="utf-8"), url)) is False
    assert nc.requires_hidden_form_callback(_Resp("<html></html>", "https://courseselection.ntust.edu.tw/signin-oidc")) is True


class _ChainSession:
    """Replays the real course-selection handshake: root entry → SSO → callback → Home, then target."""

    LOGIN_PAGE = FIXTURE.read_text(encoding="utf-8")
    CALLBACK_PAGE = '<form method="post" action="https://courseselection.ntust.edu.tw/signin-oidc"><input type="hidden" name="code" value="c"></form>'

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.logged_in = False

    def get(self, url, **kw):
        self.calls.append(("GET", url))
        if url == "https://courseselection.ntust.edu.tw/":
            if self.logged_in:
                return _Resp("<html>home</html>", "https://courseselection.ntust.edu.tw/Home/Index")
            return _Resp(self.LOGIN_PAGE, LOGIN_URL)
        if url == "https://courseselection.ntust.edu.tw/First/A06/A06":
            if self.logged_in:
                return _Resp("<html>home</html>", "https://courseselection.ntust.edu.tw/Home/Index")
            return _Resp(self.LOGIN_PAGE, LOGIN_URL)
        raise AssertionError(url)

    def post(self, url, data, **kw):
        self.calls.append(("POST", url))
        if url == "https://ssoam2.ntust.edu.tw/":
            assert data["Username"] == "U" and data["Password"] == "P"
            return _Resp(self.CALLBACK_PAGE, "https://ssoam2.ntust.edu.tw/connect/authorize?client_id=CourseSelection")
        if url == "https://courseselection.ntust.edu.tw/signin-oidc":
            self.logged_in = True
            return _Resp("<html>home</html>", "https://courseselection.ntust.edu.tw/Home/Index")
        raise AssertionError(url)


def _patch_raise(monkeypatch):
    monkeypatch.setattr(_Resp, "raise_for_status", lambda self: None, raising=False)


def test_login_to_target_uses_entry_url_for_the_handshake_then_fetches_target(monkeypatch) -> None:
    _patch_raise(monkeypatch)
    session = _ChainSession()
    page = nc.login_to_target(session, "U", "P", "https://courseselection.ntust.edu.tw/First/A06/A06", False,
                              entry_url="https://courseselection.ntust.edu.tw/")
    assert page.url == "https://courseselection.ntust.edu.tw/Home/Index"
    assert [c for c in session.calls] == [
        ("GET", "https://courseselection.ntust.edu.tw/"),
        ("POST", "https://ssoam2.ntust.edu.tw/"),
        ("POST", "https://courseselection.ntust.edu.tw/signin-oidc"),
        ("GET", "https://courseselection.ntust.edu.tw/First/A06/A06"),
    ]


def test_login_to_target_skips_sso_when_entry_already_logged_in(monkeypatch) -> None:
    _patch_raise(monkeypatch)
    session = _ChainSession()
    session.logged_in = True
    page = nc.login_to_target(session, "U", "P", "https://courseselection.ntust.edu.tw/First/A06/A06", False,
                              entry_url="https://courseselection.ntust.edu.tw/")
    assert page.url.endswith("/Home/Index")
    assert all(m == "GET" for m, _ in session.calls)
