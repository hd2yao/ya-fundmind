import json
import socket
from urllib.error import HTTPError, URLError

from fund_agent.providers import TiantianProviderError, _TiantianHttpClient, _tiantian_client_from_env


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


def test_tiantian_client_from_env_requires_base_url(monkeypatch):
    monkeypatch.delenv("TIANTIAN_API_BASE_URL", raising=False)

    assert _tiantian_client_from_env() is None


def test_tiantian_client_fetches_nav_history_with_pagination(monkeypatch):
    calls = []

    def fake_urlopen(url, timeout):
        calls.append((url, timeout))
        if "pageIndex=1" in url:
            return FakeResponse(
                json.dumps(
                    {
                        "Datas": {
                            "LSJZList": [
                                {"FSRQ": "2026-06-20", "DWJZ": "1.00"},
                                {"FSRQ": "2026-06-21", "DWJZ": "1.01"},
                            ]
                        },
                        "TotalPages": 2,
                    }
                ).encode("utf-8")
            )
        return FakeResponse(
            json.dumps(
                {
                    "Datas": {
                        "LSJZList": [
                            {"FSRQ": "2026-06-22", "DWJZ": "1.02"},
                        ]
                    },
                    "TotalPages": 2,
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr("fund_agent.providers.urlopen", fake_urlopen)
    client = _TiantianHttpClient("https://example.test", timeout_seconds=7.0)

    rows = client.nav_history("510300")

    assert [row["FSRQ"] for row in rows] == ["2026-06-20", "2026-06-21", "2026-06-22"]
    assert len(calls) == 2
    assert all(timeout == 7.0 for _, timeout in calls)
    assert [trace.attempts for trace in client.last_endpoint_traces] == [1, 1]
    assert all(trace.endpoint == "tiantian_nav_history" for trace in client.last_endpoint_traces)


def test_tiantian_client_retries_timeout_then_succeeds(monkeypatch):
    calls = 0

    def fake_urlopen(url, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise socket.timeout("slow")
        return FakeResponse(json.dumps({"Datas": {"FCODE": "510300"}}).encode("utf-8"))

    monkeypatch.setattr("fund_agent.providers.urlopen", fake_urlopen)
    client = _TiantianHttpClient(
        "https://example.test",
        timeout_seconds=3.0,
        retry_count=1,
        retry_backoff_seconds=0,
    )

    payload = client.fund_detail("510300")

    assert payload == {"FCODE": "510300"}
    assert calls == 2
    assert client.last_endpoint_traces[0].attempts == 2
    assert client.last_endpoint_traces[0].timeout_seconds == 3.0


def test_tiantian_client_classifies_invalid_response(monkeypatch):
    monkeypatch.setattr(
        "fund_agent.providers.urlopen",
        lambda url, timeout: FakeResponse(b"{not-json"),
    )
    client = _TiantianHttpClient("https://example.test")

    try:
        client.fund_detail("510300")
    except TiantianProviderError as exc:
        assert exc.code == "invalid_response"
    else:
        raise AssertionError("expected TiantianProviderError")


def test_tiantian_client_classifies_http_and_connection_errors(monkeypatch):
    monkeypatch.setattr(
        "fund_agent.providers.urlopen",
        lambda url, timeout: (_ for _ in ()).throw(HTTPError(url, 500, "boom", None, None)),
    )
    client = _TiantianHttpClient("https://example.test")

    try:
        client.fund_detail("510300")
    except TiantianProviderError as exc:
        assert exc.code == "http_error"
    else:
        raise AssertionError("expected TiantianProviderError")

    monkeypatch.setattr(
        "fund_agent.providers.urlopen",
        lambda url, timeout: (_ for _ in ()).throw(URLError("down")),
    )

    try:
        client.fund_detail("510300")
    except TiantianProviderError as exc:
        assert exc.code == "connection_error"
    else:
        raise AssertionError("expected TiantianProviderError")
