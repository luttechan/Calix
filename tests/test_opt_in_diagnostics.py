import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from engine_diagnostics import Diagnostics
from engine_logging import configure
from engine_portable_browser import configure as configure_browser


def test_normal_operation_does_not_collect_or_create_files(tmp_path):
    configure(tmp_path)
    log = Diagnostics()
    log.add("not collected")
    assert log.read() == dict(enabled=False, rows=[])
    assert not list(tmp_path.iterdir())


def test_log_bound_redaction_and_disable_clears_memory():
    log = Diagnostics()
    log.set_enabled(True)
    for i in range(800):
        log.add(f"{i} Authorization: Bearer synthetic-secret")
    assert len(log.rows) == 600
    assert "synthetic-secret" not in repr(log.read())
    last = log.rows[-1]["id"]
    assert log.read(last)["rows"] == []
    log.set_enabled(False)
    assert not log.rows
    log.add("after close")
    assert not log.rows


def test_http_trace_has_no_query_headers_body_or_response_content(monkeypatch):
    import requests
    from types import SimpleNamespace

    monkeypatch.setattr(
        requests.Session, "send", lambda *a, **k: SimpleNamespace(status_code=200)
    )
    original = requests.Session.send
    log = Diagnostics()
    restore = log.install_http_trace()
    session = requests.Session()
    request = requests.Request(
        "GET",
        "https://canvas.bufs.ac.kr/api/test?secret=do-not-log",
        headers={"Cookie": "secret-cookie"},
    ).prepare()
    try:
        session.send(request)
        assert not log.rows
        log.set_enabled(True)
        session.send(request)
        output = repr(log.read())
        assert "HTTP 응답 200" in output
        assert "do-not-log" not in output and "secret-cookie" not in output
    finally:
        restore()
        session.close()
    assert requests.Session.send is original


def test_portable_settings_do_not_disable_browser_security(monkeypatch):
    monkeypatch.setenv("QTWEBENGINE_CHROMIUM_FLAGS", "--lang=ko")
    monkeypatch.delenv("QT_OPENGL", raising=False)
    monkeypatch.delenv("QT_QUICK_BACKEND", raising=False)
    import os

    configure_browser()
    configure_browser()
    flags = os.environ["QTWEBENGINE_CHROMIUM_FLAGS"].split()
    assert flags.count("--disable-gpu") == 1
    assert "--disable-background-timer-throttling" in flags
    assert "--no-sandbox" not in flags
    assert "--disable-web-security" not in flags
    assert os.environ["QT_OPENGL"] == "software"
