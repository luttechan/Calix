import json
from http.client import HTTPException

import pytest

from learning_calendar import anv


@pytest.mark.parametrize("payload, expected", [
    (
        {"ok": True, "service": "ANV", "auto_sync": {
            "running": True, "last_sync_time": "2026-11-21 14:38:00",
            "last_error": "internal details",
        }},
        {"connected": True, "autoSync": True, "lastSync": "2026-11-21 14:38:00", "syncFailed": True},
    ),
    ({"ok": True, "service": "other"}, {"connected": False}),
    ({"ok": True, "service": "ANV", "auto_sync": []}, {
        "connected": True, "autoSync": False, "lastSync": "", "syncFailed": False,
    }),
    ([], {"connected": False}),
    (None, {"connected": False}),
])
def test_anv_local_status_contract(monkeypatch, payload, expected):
    class Response:
        status = 200

        def read(self, maximum):
            assert maximum == 16385
            return json.dumps(payload).encode()

    class Connection:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("127.0.0.1", 6270, 0.4)

        def request(self, method, route, headers):
            assert (method, route, headers) == ("GET", "/status", {"Accept": "application/json"})

        def getresponse(self):
            if payload is None:
                raise HTTPException()
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(anv.http.client, "HTTPConnection", Connection)
    assert anv.read_anv_status() == expected
