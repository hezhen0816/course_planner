from __future__ import annotations

from backend.monitor.enrollment import EnrollmentClient


class FakeResponse:
    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, data, verify, timeout, allow_redirects):
        self.calls.append(
            {
                "url": url,
                "data": data,
                "verify": verify,
                "timeout": timeout,
                "allow_redirects": allow_redirects,
            }
        )
        return FakeResponse("ok", "https://courseselection.ntust.edu.tw/Home/Index")


def make_client(session: FakeSession) -> EnrollmentClient:
    client = EnrollmentClient.__new__(EnrollmentClient)
    client.session = session
    client.verify_ssl = True
    client.REQUEST_TIMEOUT = 25
    return client


def test_submit_oidc_form_posts_hidden_fields_to_course_selection() -> None:
    session = FakeSession()
    client = make_client(session)
    response = FakeResponse(
        """
        <html>
          <body>
            <form method="post" action="https://courseselection.ntust.edu.tw/signin-oidc">
              <input type="hidden" name="code" value="abc">
              <input type="hidden" name="state" value="xyz">
            </form>
          </body>
        </html>
        """,
        "https://ssoam2.ntust.edu.tw/connect/authorize",
    )

    result = client._submit_oidc_form_if_present(response)

    assert result.url == "https://courseselection.ntust.edu.tw/Home/Index"
    assert session.calls == [
        {
            "url": "https://courseselection.ntust.edu.tw/signin-oidc",
            "data": {"code": "abc", "state": "xyz"},
            "verify": True,
            "timeout": 25,
            "allow_redirects": True,
        }
    ]


def test_submit_oidc_form_returns_original_response_when_no_callback_form() -> None:
    session = FakeSession()
    client = make_client(session)
    response = FakeResponse("<html><body>No callback form</body></html>", "https://ssoam2.ntust.edu.tw/")

    result = client._submit_oidc_form_if_present(response)

    assert result is response
    assert session.calls == []
