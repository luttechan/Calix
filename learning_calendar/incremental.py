"""Account-scoped content fingerprints, never authentication material."""

import json
import re

KEY = "lms_video_fingerprints_v1"


def fingerprints(store):
    try:
        value = json.loads(store.get_meta(KEY) or "{}")
        if not isinstance(value, dict):
            return {}
        return {
            str(k): v
            for k, v in value.items()
            if str(k).isascii()
            and str(k).isdigit()
            and isinstance(v, str)
            and re.fullmatch("[a-f0-9]{64}", v)
        }
    except (ValueError, TypeError):
        return {}


def cache_state(store):
    return dict(owner=store.get_meta("canvas_user_id"), videos=fingerprints(store))
