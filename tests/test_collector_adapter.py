"""Exercise real browser cookie import without contacting the university."""

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_hidden_collector_imports_cookies_before_validation(tmp_path):
    script = tmp_path / "collector_check.py"
    script.write_text(
        "ROOT=" + repr(str(ROOT)) + "\nFOLDER=" + repr(str(tmp_path)) + "\n" + r"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
sys.path[:0] = [ROOT, ROOT + '/desktop']
from PySide6.QtCore import QThread, Signal
import engine_sessions

class OfflineValidation(QThread):
    checked = Signal(object)
    failed = Signal(str)
    def __init__(self, rows): super().__init__()
    def run(self): self.checked.emit(dict(owner='123', courses=[]))
    def cancel(self): pass

engine_sessions.SessionValidation = OfflineValidation
from learning_calendar.cookies import write_cookies, cookie_record
from PySide6.QtNetwork import QNetworkCookie
cookie = QNetworkCookie(b'_session_id', b'synthetic')
cookie.setDomain('canvas.bufs.ac.kr')
cookie.setPath('/')
cookie.setSecure(True)
write_cookies(Path(FOLDER)/'canvas_session.dpapi', [cookie_record(cookie)])
from engine_collector import run
raise SystemExit(run(FOLDER))
""",
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [sys.executable, "-B", str(script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        # Keep the host's input pipe open, as it is during normal collection.
        process.wait(timeout=30)
        stdout, stderr = process.communicate(timeout=2)
        assert process.returncode == 0, stderr.decode("utf-8", "replace")
        events = [json.loads(line) for line in stdout.splitlines()]
        assert any(row.get("event") == "videos_collected" for row in events), events
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
