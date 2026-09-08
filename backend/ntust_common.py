from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

try:
    from .config import DEFAULT_TIMEOUT, ENTRY_URL, VERIFY_URL
except ImportError:  # pragma: no cover
    from config import DEFAULT_TIMEOUT, ENTRY_URL, VERIFY_URL

def normalize(text: str | None) -> str:
    return (text or "").replace("\xa0", " ").replace("\r", "").strip()


def split_lines(text: str | None) -> list[str]:
    return [line.strip() for line in normalize(text).split("\n") if line.strip()]


def first_form(soup: BeautifulSoup) -> Tag:
    form = soup.find("form")
    if not isinstance(form, Tag):
        raise RuntimeError("無法找到表單。")
    return form


def parse_hidden_inputs(form: Tag) -> dict[str, str]:
    values: dict[str, str] = {}
    for input_tag in form.find_all("input"):
        if not isinstance(input_tag, Tag):
            continue
        name = input_tag.get("name")
        if not name:
            continue
        input_type = (input_tag.get("type") or "").lower()
        if input_type in {"hidden", ""}:
            values[name] = input_tag.get("value", "")
    return values


def is_hidden_element(tag: Tag) -> bool:
    """True when the tag or any ancestor is not rendered by default.

    Covers inline ``display:none``, the HTML ``hidden`` attribute and Vue's
    ``v-show`` / ``v-if`` toggles — the SSO login page keeps its CAPTCHA boxes,
    "Caps Lock is on" hint and field validation messages in the DOM but hidden.
    """
    node: Tag | None = tag
    while isinstance(node, Tag):
        style = (node.get("style") or "").replace(" ", "").lower()
        if "display:none" in style or node.has_attr("hidden") or node.has_attr("v-show") or node.has_attr("v-if"):
            return True
        node = node.parent
    return False


def captcha_required(soup: BeautifulSoup) -> bool:
    """True only when a CAPTCHA widget is actually rendered.

    The SSO login page always ships hidden ``cf-turnstile`` / ``h-captcha`` /
    ``g-recaptcha`` containers (``display:none``) and their ``*-response``
    inputs; JS reveals one after repeated failures. Checking mere presence
    therefore mislabels every ordinary failure as "needs CAPTCHA".
    """
    for widget in soup.find_all(class_=re.compile(r"cf-turnstile|g-recaptcha|h-captcha", re.I)):
        if isinstance(widget, Tag) and not is_hidden_element(widget):
            return True
    return False


def find_error_text(soup: BeautifulSoup) -> str | None:
    # Browser-side verification cannot be completed from requests; say so explicitly.
    if captcha_required(soup):
        return "SSO 需要 CAPTCHA／瀏覽器端驗證，自動登入無法完成"
    page_text = normalize(soup.get_text(" ", strip=True))
    if "帳號或密碼輸入錯誤" in page_text:
        return "帳號或密碼錯誤"
    if "變更密碼" in page_text and "180天" in page_text and soup.find("input", {"name": "Password"}) is None:
        return "SSO 要求先變更密碼（密碼已超過 180 天）"
    containers = soup.find_all(
        ["div", "span", "p"],
        class_=re.compile(r"error|alert|warning|danger|validation", re.I),
    )
    for container in containers:
        if not isinstance(container, Tag) or is_hidden_element(container):
            continue
        text = normalize(container.get_text(" ", strip=True))
        if text:
            return text

    for node in soup.find_all(string=re.compile("帳號或密碼|incorrect|失敗|錯誤", re.I)):
        if isinstance(node.parent, Tag) and is_hidden_element(node.parent):
            continue
        text = normalize(str(node))
        if text:
            return text
    return None


def build_login_url(entry_response: requests.Response) -> str:
    if "ssoam" in entry_response.url:
        return entry_response.url

    soup = BeautifulSoup(entry_response.text, "html.parser")
    form = soup.find("form")
    if not isinstance(form, Tag):
        raise RuntimeError("入口頁沒有提供 SSO 登入資訊。")

    action = form.get("action")
    if action:
        return urljoin(entry_response.url, action)

    return_url_input = form.find("input", {"name": "ReturnUrl"})
    if isinstance(return_url_input, Tag):
        return_url = return_url_input.get("value", "")
        if return_url:
            return f"https://ssoam2.ntust.edu.tw/account/login?ReturnUrl={return_url}"

    raise RuntimeError("無法從入口頁推導 SSO 登入網址。")


def _callback_form(soup: BeautifulSoup) -> Tag:
    """Prefer the OIDC/auth callback form over whatever form happens to come first."""
    for form in soup.find_all("form"):
        if not isinstance(form, Tag):
            continue
        action = (form.get("action") or "").lower()
        if "signin-oidc" in action or "auth/oidc" in action or "courseselection.ntust.edu.tw" in action:
            return form
    return first_form(soup)


def _stuck_on_sso_login(response: requests.Response) -> bool:
    """True when SSO still shows a login form (wrong password, CAPTCHA, ...)."""
    if "ssoam" not in response.url:
        return False
    if "login" in response.url.lower():
        return True
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.find("input", {"name": "Password"}) is not None


def submit_hidden_form(
    session: requests.Session,
    page_response: requests.Response,
    verify_ssl: bool,
) -> requests.Response:
    soup = BeautifulSoup(page_response.text, "html.parser")
    form = _callback_form(soup)
    form_data = parse_hidden_inputs(form)
    action = urljoin(page_response.url, form.get("action", ""))
    response = session.post(
        action,
        data=form_data,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    response.raise_for_status()
    return response


def requires_hidden_form_callback(page_response: requests.Response) -> bool:
    # Match the path only: the SSO login page's ReturnUrl query string also
    # contains "signin-oidc", and treating that page as a callback would POST
    # the empty login form back to SSO.
    if urlparse(page_response.url).path.rstrip("/").endswith("/signin-oidc"):
        return True

    soup = BeautifulSoup(page_response.text, "html.parser")
    if not isinstance(soup.find("form"), Tag):
        return False

    # Scan every form (same rule as _callback_form) so a leading logout/search
    # form does not hide the OIDC form_post callback.
    action = urljoin(page_response.url, _callback_form(soup).get("action", ""))
    return "auth/oidc" in action or "signin-oidc" in action


def login_to_target(
    session: requests.Session,
    username: str,
    password: str,
    target_url: str,
    verify_ssl: bool,
    entry_url: str | None = None,
) -> requests.Response:
    """Log in through SSO and return the target page.

    ``entry_url`` is the page used to start the OIDC handshake. The course
    selection site must be entered at its root: after ``signin-oidc`` it goes
    through ``/Account/OpenIDCallback`` → ``/Home/Index`` and only then creates
    its own ``ASP.NET_SessionId``; entering at a deep page (e.g. ``/First/A06/A06``)
    lands there without that session and the page redirects to ``/Account/Logout``,
    which also kills the SSO session. Defaults to ``target_url`` for sites that
    do not have this quirk (Moodle, score history).
    """
    handshake_url = entry_url or target_url
    entry_response = session.get(
        handshake_url,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    entry_response.raise_for_status()

    if "ssoam" not in entry_response.url:
        if handshake_url == target_url:
            return entry_response
        page_response = session.get(target_url, timeout=DEFAULT_TIMEOUT, allow_redirects=True, verify=verify_ssl)
        page_response.raise_for_status()
        if "ssoam" not in page_response.url:
            return page_response
        entry_response = page_response

    soup = BeautifulSoup(entry_response.text, "html.parser")
    form = first_form(soup)
    login_data = parse_hidden_inputs(form)
    login_data["Username"] = username
    login_data["Password"] = password
    login_data.setdefault("captcha", "")

    submit_url = urljoin(entry_response.url, form.get("action", ""))
    login_response = session.post(
        submit_url,
        data=login_data,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    login_response.raise_for_status()

    if requires_hidden_form_callback(login_response):
        login_response = submit_hidden_form(session, login_response, verify_ssl)

    # Landing anywhere else (the i.ntust.edu.tw portal, SSO home without a login
    # form) means SSO accepted the credentials but dropped the ReturnUrl; the
    # target GET below completes the OIDC handshake silently.
    if _stuck_on_sso_login(login_response):
        error_text = find_error_text(BeautifulSoup(login_response.text, "html.parser"))
        if error_text:
            raise RuntimeError(f"SSO 登入失敗：{error_text}")
        raise RuntimeError(f"SSO 登入失敗，仍停留在登入頁：{login_response.url}")

    page_response = session.get(
        target_url,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    page_response.raise_for_status()

    if requires_hidden_form_callback(page_response):
        page_response = submit_hidden_form(session, page_response, verify_ssl)
        page_response = session.get(
            target_url,
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True,
            verify=verify_ssl,
        )
        page_response.raise_for_status()

    if "login" in page_response.url.lower() or "ssoam" in page_response.url:
        raise RuntimeError(f"登入後無法進入目標頁面，目前停在 {page_response.url}")

    return page_response


def login(session: requests.Session, username: str, password: str, verify_ssl: bool) -> None:
    entry_response = session.get(
        ENTRY_URL,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    entry_response.raise_for_status()

    login_url = build_login_url(entry_response)
    login_page = session.get(
        login_url,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    login_page.raise_for_status()

    soup = BeautifulSoup(login_page.text, "html.parser")
    form = first_form(soup)
    login_data = parse_hidden_inputs(form)
    login_data["Username"] = username
    login_data["Password"] = password
    login_data.setdefault("captcha", "")

    submit_url = urljoin(login_page.url, form.get("action", ""))
    login_response = session.post(
        submit_url,
        data=login_data,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    login_response.raise_for_status()

    if requires_hidden_form_callback(login_response):
        login_response = submit_hidden_form(session, login_response, verify_ssl)

    # Landing anywhere else (the i.ntust.edu.tw portal, SSO home without a login
    # form) means SSO accepted the credentials but dropped the ReturnUrl; the
    # target GET below completes the OIDC handshake silently.
    if _stuck_on_sso_login(login_response):
        error_text = find_error_text(BeautifulSoup(login_response.text, "html.parser"))
        if error_text:
            raise RuntimeError(f"SSO 登入失敗：{error_text}")
        raise RuntimeError(f"SSO 登入失敗，仍停留在登入頁：{login_response.url}")

    verify_response = session.get(
        VERIFY_URL,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    verify_response.raise_for_status()

    if requires_hidden_form_callback(verify_response):
        verify_response = submit_hidden_form(session, verify_response, verify_ssl)

    if "login" in verify_response.url.lower() or "ssoam" in verify_response.url:
        raise RuntimeError(f"登入後驗證失敗，目前停在 {verify_response.url}")
