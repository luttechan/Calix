import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from learning_calendar import anki
from learning_calendar.preferences import read_settings, write_settings


def test_review_reads_only_local_deck_counts_and_deduplicates_children(monkeypatch):
    requests = []
    replies = [
        {"문학": 1, "문학::소설": 2, "일본어": 3},
        {
            "1": {"new_count": 8, "learn_count": 3, "review_count": 10},
            "2": {"new_count": 6, "learn_count": 3, "review_count": 7},
            "3": {"new_count": 2, "learn_count": 0, "review_count": 4},
        },
    ]

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            requests.append(json.loads(body))
            result = replies[len(requests) - 1]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(dict(result=result, error=None)).encode())

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        worker = Thread(target=server.serve_forever)
        worker.start()
        connect = anki.HTTPConnection

        def loopback(host, port, timeout):
            assert (host, port) == ("127.0.0.1", 8765)
            return connect(host, server.server_port, timeout=timeout)

        monkeypatch.setattr(anki, "HTTPConnection", loopback)
        try:
            result = anki.read_review()
        finally:
            server.shutdown()
            worker.join()

    assert requests == [
        {"action": "deckNamesAndIds", "version": 6},
        {"action": "getDeckStats", "version": 6, "params": {"decks": ["문학", "문학::소설", "일본어"]}},
    ]
    assert result["totals"] == {"new": 10, "learning": 3, "review": 14}
    assert result["decks"][1] == dict(id=2, name="문학::소설", new=6, learning=3, review=7)


def test_invalid_counts_are_rejected(monkeypatch):
    answers = iter([{"기본": 1}, {"1": {"new_count": True, "learn_count": 0, "review_count": 1}}])
    monkeypatch.setattr(anki, "_request", lambda *args: next(answers))
    with pytest.raises(ValueError, match="AnkiConnect"):
        anki.read_review()


def test_defaults_without_scheduler_counts_do_not_abort_other_decks(monkeypatch):
    calls = []
    counts = {"new_count": 4, "learn_count": 3, "review_count": 2}

    def request(action, params=None):
        calls.append((action, params))
        if action == "deckNamesAndIds":
            return {"어휘": 789, "기본": 1}
        if params["decks"] != ["어휘"]:
            return anki._result({"result": None, "error": "Deck counts unavailable."})
        return {"789": counts}

    monkeypatch.setattr(anki, "_request", request)
    assert anki.read_review() == {
        "decks": [{"id": 789, "name": "어휘", "new": 4, "learning": 3, "review": 2}],
        "totals": {"new": 4, "learning": 3, "review": 2},
    }
    assert calls[1:] == [
        ("getDeckStats", {"decks": ["어휘", "기본"]}),
        ("getDeckStats", {"decks": ["기본"]}),
        ("getDeckStats", {"decks": ["어휘"]}),
    ]


def test_preference_defaults_off_and_restores_boolean_only(tmp_path):
    path = tmp_path / "settings.json"
    assert read_settings(path)["anki_sync"] is False
    write_settings(path, {"anki_sync": True})
    assert read_settings(path)["anki_sync"] is True
    write_settings(path, {"anki_sync": "true"})
    assert read_settings(path)["anki_sync"] is False
