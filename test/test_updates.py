"""Fixed-host release metadata, daily throttling and bounded network failures, without live networking."""

import io
import json
import threading

import pytest

from je_file_tree.core import updates


def _payload(version="1.2.3", **info):
    return json.dumps({"info": {"name": "je_file_tree", "version": version, "yanked": False, **info}}).encode()


@pytest.mark.parametrize(("latest", "expected"), [
    ("0.1.0", None), ("0.0.9", None), ("0.1.1", "0.1.1"), ("0.10.0", "0.10.0"),
    ("0.2.0rc1", None), ("1.0.0.dev1", None), ("1.0.0+local", None), ("<script>", None),
])
def test_only_newer_stable_repository_release_forms_are_notified(latest, expected):
    assert updates.newer_release(_payload(latest), "0.1.0") == expected
    assert updates.newer_release(_payload("9.0.0", yanked=True), "0.1.0") is None


@pytest.mark.parametrize("payload", [b"[]", b"{}", b"not-json", b"\xff", _payload(name="foreign"),
                                     _payload(yanked="false"), _payload(version=3)])
def test_malformed_or_foreign_project_metadata_is_refused(payload):
    with pytest.raises((ValueError, UnicodeError)):
        updates.newer_release(payload, "0.1.0")


def test_response_size_installed_version_and_elapsed_day_bounds():
    with pytest.raises(ValueError):
        updates.newer_release(b"x" * (updates.MAX_RESPONSE + 1), "0.1.0")
    with pytest.raises(ValueError):
        updates.newer_release(_payload(), "0.1.0\r\nInjected: yes")
    now = updates.CHECK_INTERVAL * 2
    assert updates.check_due(None, now) and updates.check_due("invalid", now)
    assert updates.check_due(now - updates.CHECK_INTERVAL, now)
    assert not updates.check_due(now - 1, now) and not updates.check_due(now + 1, now)
    assert not updates.check_due(None, float("nan"))


class _Response(io.BytesIO):
    def __init__(self, body, *, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = {"Content-Type": "application/json; charset=utf-8", **(headers or {})}

    def getheader(self, key, default=None):
        return self.headers.get(key, default)


@pytest.mark.parametrize(("status", "headers"), [
    (302, {"Location": "https://foreign.example/"}), (503, {}),
    (200, {"Content-Type": "text/html"}), (200, {"Content-Encoding": "gzip"}),
    (200, {"Content-Length": str(updates.MAX_RESPONSE + 1)}), (200, {"Content-Length": "-1"}),
    (200, {"Content-Length": "999"}),
])
def test_redirects_errors_unexpected_encoding_and_incomplete_metadata_are_refused(status, headers):
    with _Response(_payload(), status=status, headers=headers) as response, pytest.raises(ValueError):
        updates._read(response, threading.Event())


def test_unannounced_oversize_body_and_canceled_read_are_refused():
    with _Response(b"x" * (updates.MAX_RESPONSE + 1)) as response, pytest.raises(ValueError):
        updates._read(response, threading.Event())
    canceled = threading.Event()
    canceled.set()
    with _Response(_payload()) as response, pytest.raises(InterruptedError):
        updates._read(response, canceled)


def test_one_fixed_tls_host_request_closes_transport_even_when_response_fails(monkeypatch):
    calls = []

    class Connection:
        def __init__(self, host, timeout):
            calls.append((host, timeout))

        def request(self, method, path, headers):
            calls.append((method, path, headers))

        def getresponse(self):
            return _Response(_payload())

        def close(self):
            calls.append("closed")

    monkeypatch.setattr(updates.http.client, "HTTPSConnection", Connection)
    assert updates.fetch_release("0.1.0", threading.Event()) == "1.2.3"
    assert calls[0] == ("pypi.org", 8) and calls[1][:2] == ("GET", "/pypi/je_file_tree/json")
    assert calls[-1] == "closed"
    monkeypatch.setattr(Connection, "getresponse", lambda _self: _Response(b"broken"))
    with pytest.raises(ValueError):
        updates.fetch_release("0.1.0", threading.Event())
    assert calls[-1] == "closed"
