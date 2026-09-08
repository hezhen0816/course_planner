from __future__ import annotations

from backend.monitor import utils


class _Env:
    def __init__(self, values: dict[str, str]):
        self.values = values

    def get(self, key: str, default: str = ""):
        return self.values.get(key, default)


def test_verify_ssl_explicit_wins_over_env() -> None:
    env = _Env({"NTUST_VERIFY_SSL": "false"})
    assert utils.resolve_verify_ssl(True, env) is True
    assert utils.resolve_verify_ssl(False, env) is False


def test_verify_ssl_falls_back_to_env_and_defaults_to_on() -> None:
    assert utils.resolve_verify_ssl(None, _Env({"NTUST_VERIFY_SSL": "false"})) is False
    assert utils.resolve_verify_ssl(None, _Env({"NTUST_VERIFY_SSL": "YES"})) is True
    assert utils.resolve_verify_ssl(None, _Env({})) is True


def test_socks5_becomes_socks5h_so_dns_goes_through_the_proxy() -> None:
    env = _Env({
        "NTUST_PROXY_TYPE": "socks5",
        "NTUST_PROXY_HOST": "proxy.example",
        "NTUST_PROXY_PORT": "1080",
        "NTUST_PROXY_USERNAME": "u",
        "NTUST_PROXY_PASSWORD": "p",
    })
    proxies = utils.proxies_from_env(env)
    assert proxies == {
        "http": "socks5h://u:p@proxy.example:1080",
        "https": "socks5h://u:p@proxy.example:1080",
    }


def test_http_proxy_without_credentials() -> None:
    env = _Env({"NTUST_PROXY_TYPE": "http", "NTUST_PROXY_HOST": "h", "NTUST_PROXY_PORT": "8080"})
    assert utils.proxies_from_env(env) == {"http": "http://h:8080", "https": "http://h:8080"}


def test_incomplete_or_unsupported_proxy_is_ignored() -> None:
    assert utils.proxies_from_env(_Env({})) is None
    assert utils.proxies_from_env(_Env({"NTUST_PROXY_TYPE": "http", "NTUST_PROXY_HOST": "h"})) is None
    assert utils.proxies_from_env(_Env({
        "NTUST_PROXY_TYPE": "ftp", "NTUST_PROXY_HOST": "h", "NTUST_PROXY_PORT": "1",
    })) is None


def test_explicit_proxies_win_over_environment() -> None:
    env = _Env({"NTUST_PROXY_TYPE": "http", "NTUST_PROXY_HOST": "env-host", "NTUST_PROXY_PORT": "8080"})
    session, verify = utils.build_session(False, {"http": "http://given:1", "https": "http://given:1"}, env_manager=env)
    assert verify is False
    assert session.proxies["http"] == "http://given:1"


def test_session_carries_user_agent_and_env_proxy() -> None:
    env = _Env({"NTUST_PROXY_TYPE": "http", "NTUST_PROXY_HOST": "env-host", "NTUST_PROXY_PORT": "8080"})
    session, verify = utils.build_session(None, None, user_agent="UA/1.0", env_manager=env)
    assert verify is True
    assert session.headers["User-Agent"] == "UA/1.0"
    assert session.proxies["https"] == "http://env-host:8080"
