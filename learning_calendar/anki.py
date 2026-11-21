"""Read study counts from the local AnkiConnect add-on."""

import json
from http.client import HTTPConnection, HTTPException

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
COUNTS = {"new": "new_count", "learning": "learn_count", "review": "review_count"}
INVALID_RESPONSE = "AnkiConnect 응답을 확인할 수 없습니다."


def _request(action, params=None):
    payload = {"action": action, "version": 6}
    if params is not None:
        payload["params"] = params
    connection = HTTPConnection("127.0.0.1", 8765, timeout=2)
    try:
        connection.request(
            "POST", "/", json.dumps(payload), {"Content-Type": "application/json"}
        )
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(INVALID_RESPONSE)
        body = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, HTTPException) as error:
        raise ValueError("Anki를 실행하고 AnkiConnect 설치 상태를 확인하세요.") from error
    finally:
        connection.close()
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError(INVALID_RESPONSE)
    try:
        result = json.loads(body)
    except (ValueError, RecursionError) as error:
        raise ValueError(INVALID_RESPONSE) from error
    if not isinstance(result, dict) or not {"result", "error"} <= result.keys():
        raise ValueError(INVALID_RESPONSE)
    if result["error"] is not None:
        if result["error"] == "valid api key must be provided":
            raise ValueError("AnkiConnect에 API 키가 설정되어 있습니다.")
        raise ValueError("Anki의 프로필과 AnkiConnect 상태를 확인하세요.")
    return result["result"]


def read_review():
    names = _request("deckNamesAndIds")
    if not isinstance(names, dict) or any(
        not isinstance(name, str)
        or not name.strip()
        or len(name) > 4096
        or any(0xD800 <= ord(character) <= 0xDFFF for character in name)
        or type(deck_id) is not int
        or not 0 < deck_id < 2**53
        for name, deck_id in names.items()
    ):
        raise ValueError(INVALID_RESPONSE)
    totals = dict.fromkeys(COUNTS, 0)
    if not names:
        return {"decks": [], "totals": totals}

    # AnkiConnect resolves names internally. Only send names from its current deck list.
    stats = _request("getDeckStats", {"decks": list(names)})
    if not isinstance(stats, dict):
        raise ValueError(INVALID_RESPONSE)
    decks = []
    for name, deck_id in sorted(names.items(), key=lambda item: item[0].casefold()):
        row = stats.get(str(deck_id))
        if row is None:
            continue
        if not isinstance(row, dict):
            raise ValueError(INVALID_RESPONSE)
        counts = {key: row.get(field) for key, field in COUNTS.items()}
        if any(
            type(count) is not int or not 0 <= count < 2**32
            for count in counts.values()
        ):
            raise ValueError(INVALID_RESPONSE)
        decks.append({"id": deck_id, "name": name, **counts})

    # Parent counts already include the cards in their subdecks.
    reported_names = {row["name"] for row in decks}
    for row in decks:
        parts = row["name"].split("::")
        if not any("::".join(parts[:i]) in reported_names for i in range(1, len(parts))):
            for key in totals:
                totals[key] += row[key]
    return {"decks": decks, "totals": totals}
