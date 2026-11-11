"""Opt-in maintenance on the active learning DB; never touches diary databases."""

from learning_calendar import secure_db as sqlite3
import threading
import time
from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import QThread, Signal

ACTIONS = {"integrity", "clear_sync_cache", "optimize"}


def maintain(path, action, cancelled=None):
    if action not in ACTIONS:
        raise ValueError("Unknown maintenance operation.")
    cancelled = cancelled or threading.Event()
    deadline = time.monotonic() + 15

    def check(*_):
        if cancelled.is_set() or time.monotonic() > deadline:
            raise ValueError("Maintenance cancelled or timed out.")

    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Active database unavailable.")
    db = sqlite3.connect(
        path.resolve().as_uri() + "?mode=ro" if action == "integrity" else str(path),
        uri=action == "integrity",
        timeout=1,
    )
    db.set_progress_handler(
        lambda: int(cancelled.is_set() or time.monotonic() > deadline), 1000
    )
    try:
        check()
        checks = [row[0] for row in db.execute("PRAGMA quick_check")]
        foreign_keys = len(db.execute("PRAGMA foreign_key_check").fetchall())
        if checks != ["ok"] or foreign_keys:
            return dict(
                action=action,
                healthy=False,
                issue_count=len([item for item in checks if item != "ok"])
                + foreign_keys,
            )
        report = dict(action=action, healthy=True)
        if action == "integrity":
            return report
        folder = path.resolve().parent
        recovery = folder / "developer-recovery"
        if recovery.is_symlink() or (recovery.exists() and not recovery.is_dir()):
            raise ValueError("Recovery directory unavailable.")
        recovery.mkdir(exist_ok=True)
        if recovery.resolve().parent != folder:
            raise ValueError("Invalid recovery directory.")
        backup = recovery / ("learning-" + uuid4().hex + ".db")
        destination = sqlite3.connect(backup)
        try:
            db.backup(destination, pages=256, progress=check, sleep=0.01)
        finally:
            destination.close()
        report["recovery_file"] = "developer-recovery/" + backup.name
        check()
        if action == "clear_sync_cache":
            from learning_calendar.incremental import KEY

            with db:
                db.execute("DELETE FROM meta WHERE key=?", (KEY,))
                check()
        else:
            with db:
                db.execute("PRAGMA optimize")
                check()
        return report
    finally:
        db.close()


class MaintenanceTask(QThread):
    success = Signal(object)
    error = Signal(str)

    def __init__(self, path, action, parent=None):
        super().__init__(parent)
        self.path, self.action = path, action
        self.cancelled = threading.Event()

    def cancel(self):
        self.cancelled.set()

    def run(self):
        try:
            self.success.emit(maintain(self.path, self.action, self.cancelled))
        except Exception:
            self.error.emit(
                "Maintenance failed or was cancelled. Existing records were retained."
            )
