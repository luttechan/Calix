import json
from pathlib import Path


def test_local_photo_decode_is_allowed_without_broadening_other_policies():
    root = Path(__file__).resolve().parents[1]
    policy = json.loads(
        (root / "desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
    )["app"]["security"]["csp"]
    directives = {
        parts[0]: parts[1:]
        for line in policy.split(";")
        if (parts := line.strip().split())
    }
    assert "blob:" in directives["img-src"] and "data:" in directives["img-src"]
    assert directives["script-src"] == ["'self'"]
    assert directives["connect-src"] == ["'self'", "ipc:", "http://ipc.localhost"]
    assert directives["object-src"] == directives["frame-src"] == ["'none'"]
    assert "*" not in directives["img-src"] and "https:" not in directives["img-src"]
