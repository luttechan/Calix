from __future__ import annotations
import json
from pathlib import Path

SERVICE = 'Calix'
LEGACY_SERVICE = 'BUFS Learning Calendar'
ACCOUNT_KEY = '__account_id__'
_credential_backend_ready=False


def prepare_credentials():
    global _credential_backend_ready
    if _credential_backend_ready:return
    import sys,keyring
    if sys.platform=='win32':
        from keyring.backends.Windows import WinVaultKeyring
        keyring.set_keyring(WinVaultKeyring())
    _credential_backend_ready=True


def read_settings(path: str | Path) -> dict:
    defaults = {'window_width':1240,'window_height':840,'active_db':'learning.db','theme':'sky','notifications':False,'glass':True,'font_mode':'pretendard','nickname':'','greeting':'{닉네임}님, 오셨군요!','onboarding_complete':False}
    try:
        settings = json.loads(Path(path).read_text(encoding='utf-8'))
        if isinstance(settings,dict):
            for key in ('window_width','window_height'):
                value=settings.get(key)
                if type(value) is int and 240<=value<=16384:defaults[key]=value
            for key in ('notifications','glass','onboarding_complete'):
                if type(settings.get(key)) is bool:defaults[key]=settings[key]
            for key,limit in (('nickname',30),('greeting',120)):
                value=settings.get(key)
                if isinstance(value,str) and 0<len(value.strip())<=limit and not any(ord(c)<32 and c!='\n' for c in value):defaults[key]=value.strip()
            if settings.get('theme') in ('pink','sky','mint','purple','dark'):defaults['theme']=settings['theme']
            if settings.get('font_mode') in ('pretendard','windows'):defaults['font_mode']=settings['font_mode']
            name=settings.get('active_db')
            reserved={'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}
            if (isinstance(name,str) and 3<len(name)<=128 and name.endswith('.db')
                    and name[0].isalnum() and all(c.isascii() and (c.isalnum() or c in '._-') for c in name)
                    and not any(c in name for c in '/\\:<>"|?*') and Path(name).name==name
                    and name.split('.')[0].upper() not in reserved):defaults['active_db']=name
    except (OSError,ValueError):
        pass
    return defaults


def write_settings(path: str | Path, settings: dict):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    safe = {k:v for k,v in settings.items() if k in {'window_width','window_height','active_db','theme','notifications','glass','font_mode','nickname','greeting','onboarding_complete'}}
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(safe,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)


def read_account() -> str:
    prepare_credentials()
    import keyring
    return keyring.get_password(SERVICE, ACCOUNT_KEY) or keyring.get_password(LEGACY_SERVICE, ACCOUNT_KEY) or ''


def store_account(student_id: str, password: str | None = None):
    prepare_credentials()
    import keyring
    old = read_account()
    student_id = student_id.strip()
    if student_id:
        keyring.set_password(SERVICE, ACCOUNT_KEY, student_id)
        if password is not None and password:
            keyring.set_password(SERVICE + '/password', student_id, password)
    else:
        # Remove both generations so a legacy fallback cannot restore a deleted account.
        identifiers={old}
        identifiers.update(keyring.get_password(service,ACCOUNT_KEY) for service in (SERVICE,LEGACY_SERVICE))
        for service in (SERVICE,LEGACY_SERVICE):
            for identifier in filter(None,identifiers):
                for password_service in (service+'/password',service):
                    try:keyring.delete_password(password_service,identifier)
                    except keyring.errors.PasswordDeleteError:pass
            try:keyring.delete_password(service,ACCOUNT_KEY)
            except keyring.errors.PasswordDeleteError:pass


def read_password(student_id: str) -> str:
    prepare_credentials()
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
