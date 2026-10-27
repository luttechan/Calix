from __future__ import annotations
import json
from pathlib import Path

SERVICE = 'Calix'
LEGACY_SERVICE = 'BUFS Learning Calendar'
ACCOUNT_KEY = '__account_id__'


def read_settings(path: str | Path) -> dict:
    defaults = {'window_width':1240,'window_height':840,'active_db':'learning.db','theme':'sky','notifications':False,'glass':True}
    try:
        settings = json.loads(Path(path).read_text(encoding='utf-8'))
        if isinstance(settings,dict):
            defaults.update({k:v for k,v in settings.items() if k in defaults})
    except (OSError,ValueError):
        pass
    return defaults


def write_settings(path: str | Path, settings: dict):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    safe = {k:v for k,v in settings.items() if k in {'window_width','window_height','active_db','theme','notifications','glass'}}
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(safe,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)


def read_account() -> str:
    import keyring
    return keyring.get_password(SERVICE, ACCOUNT_KEY) or keyring.get_password(LEGACY_SERVICE, ACCOUNT_KEY) or ''


def store_account(student_id: str, password: str | None = None):
    import keyring
    old = read_account()
    student_id = student_id.strip()
    if student_id:
        keyring.set_password(SERVICE, ACCOUNT_KEY, student_id)
        if password is not None and password:
            keyring.set_password(SERVICE + '/password', student_id, password)
    else:
        if old:
            try: keyring.delete_password(SERVICE, ACCOUNT_KEY)
            except keyring.errors.PasswordDeleteError: pass


def read_password(student_id: str) -> str:
    import keyring
    return keyring.get_password(SERVICE + '/password', student_id) or keyring.get_password(LEGACY_SERVICE + '/password',student_id) or ''


def migrate_legacy_account(path: str | Path):
    """Move v0.2 plaintext ID into Credential Manager and scrub legacy settings."""
    path = Path(path)
    try:
        settings = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return
    if not isinstance(settings, dict) or 'student_id' not in settings:
        return
    legacy = str(settings.get('student_id') or '').strip()
    try:
        if legacy:
            store_account(legacy)
            import keyring
            oldpw = keyring.get_password(SERVICE, legacy)
            if oldpw:
                keyring.set_password(SERVICE + '/password', legacy, oldpw)
                try: keyring.delete_password(SERVICE, legacy)
                except keyring.errors.PasswordDeleteError: pass
    finally:
        # Always scrub the previous plaintext account field even if keyring fails.
        write_settings(path, settings)
