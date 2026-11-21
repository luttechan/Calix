"""Read the local ANV resident service without changing its settings."""

import http.client
import json
import re


def read_anv_status() -> dict:
    connection = http.client.HTTPConnection("127.0.0.1", 6270, timeout=0.4)
    try:
        connection.request("GET", "/status", headers={"Accept": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            return {"connected": False}
        raw = response.read(16385)
        if len(raw) > 16384:
            return {"connected": False}
        payload = json.loads(raw)
    except (OSError, http.client.HTTPException, ValueError, RecursionError):
        return {"connected": False}
    finally:
        connection.close()

    if not isinstance(payload, dict) or (
        payload.get("ok") is not True or payload.get("service") != "ANV"
    ):
        return {"connected": False}
    sync = payload.get("auto_sync")
    if not isinstance(sync, dict):
        sync = {}
    last_sync = sync.get("last_sync_time")
    if not isinstance(last_sync, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}", last_sync
    ):
        last_sync = ""
    return {
        "connected": True,
        "autoSync": sync.get("running") is True,
        "lastSync": last_sync,
        "syncFailed": bool(sync.get("last_error")),
    }
