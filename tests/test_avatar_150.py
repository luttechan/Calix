import base64
import json
import struct
import sys
import zlib
from pathlib import Path
import pytest
from learning_calendar.avatar import validate_avatar
from learning_calendar.preferences import read_settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from engine_api import EngineAPI


def png(width=1, height=1):
    def chunk(kind, payload):
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    raw = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\x90\x40\x70\xff"))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def test_user_photo_and_name_survive_restart(tmp_path):
    photo = png()
    api = EngineAPI(tmp_path)
    assert api.bootstrap()["preferences"]["avatar"] == ""
    api.dispatch(
        "profile.save",
        dict(nickname="사용자", greeting="{닉네임}님, 오셨군요!", avatar=photo),
    )
    api.close()
    api = EngineAPI(tmp_path)
    assert api.bootstrap()["preferences"]["avatar"] == photo
    assert api.bootstrap()["preferences"]["nickname"] == "사용자"
    api.dispatch("profile.save", dict(avatar=""))
    assert api.bootstrap()["preferences"]["avatar"] == ""
    api.close()


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/photo.png",
        "data:image/svg+xml;base64,PHN2Zz4=",
        png(10000, 10000),
        png()[:-4] + "AAAA",
        "x" * 400001,
    ],
    ids=["remote-url","svg","huge-dimensions","bad-checksum","too-large"],
)
def test_unsafe_or_unbounded_image_is_rejected(value):
    with pytest.raises(ValueError):
        validate_avatar(value)


def test_invalid_saved_photo_does_not_break_settings(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(dict(nickname="사용자", avatar="file:///C:/photo.png")),
        encoding="utf-8",
    )
    settings = read_settings(path)
    assert settings["nickname"] == "사용자" and settings["avatar"] == ""
