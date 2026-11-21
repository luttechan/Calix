"""Read study counts from the local AnkiConnect add-on."""

import json
from http.client import HTTPConnection, HTTPException

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
COUNTS = {"new": "new_count", "learning": "learn_count", "review": "review_count"}
INVALID_RESPONSE = "AnkiConnect 응답을 확인할 수 없습니다."


class _CountsUnavailable(ValueError):
    pass


def _result(reply):
    if not isinstance(reply, dict) or not {"result", "error"} <= reply.keys():
        raise ValueError(INVALID_RESPONSE)
    error = reply["error"]
    if error is None:
        return reply["result"]
    if isinstance(error, str) and error.strip().rstrip(".").casefold() == "deck counts unavailable":
        raise _CountsUnavailable(INVALID_RESPONSE)
    if error == "valid api key must be provided":
        raise ValueError("AnkiConnect에 API 키가 설정되어 있습니다.")
    raise ValueError("Anki의 프로필과 AnkiConnect 상태를 확인하세요.")


def _request(action, params=None):
    payload = {"action": action, "version": 6}
    if params is not None:
        payload["params"] = params
    connection = HTTPConnection("127.0.0.1", 8765, timeout=3)
    try:
        connection.request(
            "POST", "/",
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            {"Content-Type": "application/json"},
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
    return _result(result)


def _read_stats(deck_names, default_deck):
    try:
        stats = _request("getDeckStats", {"decks": deck_names})
    except _CountsUnavailable:
        # Recent AnkiConnect versions fail the entire call when a deck (usually
        # the empty default deck) has no entry in Anki's scheduler tree.
        if len(deck_names) == 1:
            return {}
        if default_deck in deck_names:
            isolated = [default_deck]
            remainder = [name for name in deck_names if name != default_deck]
        else:
            midpoint = len(deck_names) // 2
            isolated, remainder = deck_names[:midpoint], deck_names[midpoint:]
        stats = _read_stats(isolated, None) | _read_stats(remainder, None)
    if not isinstance(stats, dict):
        raise ValueError(INVALID_RESPONSE)
    return stats


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
    default_deck = next((name for name, deck_id in names.items() if deck_id == 1), None)
    stats = _read_stats(list(names), default_deck)
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
