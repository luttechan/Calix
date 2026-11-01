"""Bounded PNG profile images. No paths, remote URLs, or executable image formats."""

import base64
import binascii
import struct
import zlib

PREFIX = "data:image/png;base64,"


def validate_avatar(value):
    if value == "":
        return ""
    if (
        not isinstance(value, str)
        or not value.startswith(PREFIX)
        or len(value) > 400000
    ):
        raise ValueError("프로필 사진을 확인하세요.")
    try:
        raw = base64.b64decode(value[len(PREFIX) :], validate=True)
        if len(raw) > 300000 or raw[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError
        offset = 8
        first = True
        pixels = False
        ended = False
        while offset < len(raw):
            length = struct.unpack(">I", raw[offset : offset + 4])[0]
            kind = raw[offset + 4 : offset + 8]
            end = offset + 8 + length
            if end + 4 > len(raw) or length > 300000:
                raise ValueError
            if (
                zlib.crc32(raw[offset + 4 : end]) & 0xFFFFFFFF
                != struct.unpack(">I", raw[end : end + 4])[0]
            ):
                raise ValueError
            if first:
                if kind != b"IHDR" or length != 13:
                    raise ValueError
                width, height = struct.unpack(">II", raw[offset + 8 : offset + 16])
                if not 0 < width <= 256 or not 0 < height <= 256:
                    raise ValueError
                first = False
            if kind == b"IDAT":
                pixels = True
            offset = end + 4
            if kind == b"IEND":
                if length or offset != len(raw):
                    raise ValueError
                ended = True
                break
        if not ended or not pixels:
            raise ValueError
    except (ValueError, binascii.Error, struct.error):
        raise ValueError("프로필 사진을 확인하세요.") from None
    return value
