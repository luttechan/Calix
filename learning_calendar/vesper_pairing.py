"""Generate a short-lived QR preview for the Vesper pairing screen."""

import secrets
import time
from urllib.parse import urlencode

LIFETIME_SECONDS = 300


def issue_preview():
    from qrcodegen import QrCode

    expires = int(time.time()) + LIFETIME_SECONDS
    query = urlencode({"v": 1, "token": secrets.token_urlsafe(24), "expires": expires})
    qr = QrCode.encode_text(f"calix-vesper://pair?{query}", QrCode.Ecc.MEDIUM)
    size = qr.get_size()
    return {
        "expiresAt": expires * 1000,
        "rows": ["".join("1" if qr.get_module(x, y) else "0" for x in range(size)) for y in range(size)],
    }
