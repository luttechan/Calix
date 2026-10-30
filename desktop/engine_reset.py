"""Reset only Calix-owned data after explicit confirmation in EngineAPI."""

from pathlib import Path
import logging
import re
import tempfile
import shutil


def reset_data(api):
    folder = api.folder.resolve()
    names = {
        "learning.db",
        "journals.db",
        "private-diary.db",
        "holidays.db",
        api.store.path.name,
        "settings.json",
        "canvas_session.dpapi",
    }
    owned = []
    for path in folder.iterdir():
        base = re.sub(r"-(wal|shm|journal)$", "", path.name)
        if (
            base in names
            or re.fullmatch(r"learning-user-[0-9]+\.db", base)
            or re.fullmatch(r"recovery-[0-9-]+\.calix", path.name)
        ):
            if (
                path.is_symlink()
                or not path.is_file()
                or path.resolve().parent != folder
            ):
                raise ValueError("자료 경로를 확인하세요.")
            owned.append(path)
    staging = Path(tempfile.mkdtemp(prefix=".calix-reset-", dir=folder))
    moved = []
    api.close()
    try:
        for path in owned:
            if not path.exists():
                continue
            target = staging / path.name
            path.replace(target)
            moved.append((path, target))
    except OSError:
        for path, target in reversed(moved):
            target.replace(path)
        staging.rmdir()
        api.__init__(folder)
        raise ValueError("초기화하지 못했습니다. 자료를 사용하는 다른 창을 닫으세요.")
    try:
        api.__init__(folder)
    except Exception:
        for path in folder.iterdir():
            if path.is_file() and (
                path.name in names
                or re.sub(r"-(wal|shm|journal)$", "", path.name) in names
            ):
                path.unlink()
        for path, target in reversed(moved):
            target.replace(path)
        staging.rmdir()
        api.__init__(folder)
        raise
    assert staging.resolve().parent == folder and staging.name.startswith(
        ".calix-reset-"
    )
    try:
        shutil.rmtree(staging)
    except OSError:
        logging.error("Reset completed but retired data could not be removed")
        raise ValueError(
            "DB는 초기화됐지만 일부 이전 자료를 삭제하지 못했습니다. 앱을 종료한 뒤 다시 확인하세요."
        )
