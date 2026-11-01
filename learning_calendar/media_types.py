"""Shared LearningX media rules used by the browser and the Python parser."""

import json
from pathlib import Path

MEDIA_RULES_JSON = (
    Path(__file__).with_name("media_types.json").read_text(encoding="utf-8")
)
MEDIA_RULES = json.loads(MEDIA_RULES_JSON)
VIDEO_KINDS = frozenset(MEDIA_RULES["video"])
NON_VIDEO_KINDS = frozenset(MEDIA_RULES["non_video"])
