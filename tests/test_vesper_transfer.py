import base64
from http.client import HTTPConnection
import json
from time import sleep
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import pytest

from learning_calendar.models import Course, Event
from learning_calendar.storage import Store
from learning_calendar.vesper_records import import_school
from learning_calendar.vesper_transfer import Transfer, addresses


def test_school_merge_keeps_deadlines_and_unlisted_courses(tmp_path):
    store = Store(tmp_path / "schedule.db")
    course = Course(42, "Course")
    old = Event("assignment:42:4", 42, "Course", "assignment", "Known", None, True)
    unchanged = Event("assignment:42:5", 42, "Course", "assignment", "Keep", "2026-12-01T09:00:00Z", True)
    store.apply_batch([course], {(42, "assignment"): [old, unchanged]})
    dated = "2026-12-03T09:00:00Z"
    with store.db:
        import_school(store, [
            {"id": "canvas:42:assignment:4", "title": "Mirror", "due": dated, "done": False},
            {"id": "canvas:42:assignment:6", "title": "New", "due": dated, "done": True, "url": "/courses/42/assignments/6"},
            {"id": "canvas:43:assignment:7", "title": "Unlisted", "due": dated, "done": False, "url": "/courses/43/assignments/7"},
        ])
    result = {event.key: event for event in store.events()}
    assert set(result) == {"assignment:42:4", "assignment:42:5", "assignment:42:6"}
    assert result["assignment:42:4"].due_at == dated and result["assignment:42:4"].completed
    assert result["assignment:42:5"].due_at == unchanged.due_at
    store.close()


def test_private_listener_waits_for_approval_and_closes_after_save():
    hosts = addresses()
    if not hosts:
        pytest.skip("No private IPv4 interface available")
    try:
        connection = Transfer(hosts[0], "a" * 32)
    except OSError:
        pytest.skip("The test environment blocks private network listeners")
    receipt = "e" * 32
    try:
        uri = urlsplit(connection.code()["uri"])
        fields = parse_qs(uri.query)
        assert fields["v"] == ["3"]
        key = AESGCM(base64.urlsafe_b64decode(fields["key"][0] + "="))

        def send(route, body):
            from secrets import token_bytes

            nonce = token_bytes(12)
            encrypted = nonce + key.encrypt(nonce, json.dumps(body).encode(), f"calix-vesper-v3:{route}".encode())
            client = HTTPConnection(hosts[0], int(fields["port"][0]), timeout=4)
            try:
                client.request("POST", "/" + route, encrypted, {"Content-Type": "application/octet-stream"})
                response = client.getresponse()
                assert response.status == 200
                data = response.read()
                return json.loads(key.decrypt(data[:12], data[12:], b"calix-vesper-v3:reply"))
            finally:
                client.close()

        assert send("offer", {"receipt": receipt, "name": "Fixture", "changes": {}})["phase"] == "approval"
        assert "snapshot" not in send("result", {"receipt": receipt})
        assert connection.status() == {"phase": "approval", "name": "Fixture", "code": "EEEEEE"}
        connection.approve(lambda _: {"conflicts": [], "records": {}})
        assert send("result", {"receipt": receipt})["snapshot"]["records"] == {}
        assert send("received", {"receipt": receipt})["phase"] == "received"
        for _ in range(20):
            if connection.status()["phase"] == "closed":
                break
            sleep(.01)
        assert connection.status() == {"phase": "closed"}
    finally:
        connection.close()
