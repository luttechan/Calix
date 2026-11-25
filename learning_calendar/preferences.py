from __future__ import annotations
import json
import re
from pathlib import Path

SERVICE = "Calix"
LEGACY_SERVICE = "BUFS Learning Calendar"
ACCOUNT_KEY = "__account_id__"
DEFAULT_THEME = "aurora"
THEMES = (DEFAULT_THEME, "aurora-dawn", "aurora-dusk", "pink", "sky", "mint", "purple", "dark", "peach", "amber", "olive", "lavender")
PALETTE_COLORS = {"canvas", "surface", "accent", "muted"}
_credential_backend_ready = False


def validate_timetable_colors(value):
    if not isinstance(value, dict):
        raise ValueError("시간표 색상을 확인하세요.")
    presets = value.get("presets")
    active = value.get("active")
    if not isinstance(presets, dict) or len(presets) > 24 or not isinstance(active, str):
        raise ValueError("시간표 색상을 확인하세요.")
    if active not in ("auto", "manual") and active not in presets:
        raise ValueError("시간표 테마를 선택하세요.")
    for name, colors in presets.items():
        if (not isinstance(name, str) or name in ("auto", "manual")
                or not 0 < len(name) <= 32 or name.strip() != name
                or not name.isprintable() or not isinstance(colors, list) or len(colors) != 8
                or any(not isinstance(c, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", c) for c in colors)):
            raise ValueError("시간표 색상을 확인하세요.")
    return {"active": active, "presets": {name: [color.lower() for color in colors] for name, colors in presets.items()}}


def validate_theme_palette(value):
    if not isinstance(value, dict) or value.keys() - PALETTE_COLORS or any(
        not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color)
        for color in value.values()
    ):
        raise ValueError("Use six-digit hex colors.")
    return {name: color.lower() for name, color in value.items()}


def prepare_credentials():
    global _credential_backend_ready
    if _credential_backend_ready:
        return
    import sys, keyring

    if sys.platform == "win32":
        from keyring.backends.Windows import WinVaultKeyring

        keyring.set_keyring(WinVaultKeyring())
    _credential_backend_ready = True


def read_settings(path: str | Path) -> dict:
    from .reminders import DEFAULTS, validate as validate_reminders

    defaults = {
        "reminders": DEFAULTS.copy(),
        "attendance_visible": False,
        "attendance_sync": False,
        "anki_sync": False,
        "window_width": 1240,
        "window_height": 840,
        "active_db": "learning.db",
        "theme": DEFAULT_THEME,
        "theme_palettes": {},
        "timetable_colors": {"active": "manual", "presets": {}},
        "notifications": False,
        "glass": True,
        "reduce_motion": False,
        "developer_mode": False,
        "developer_acknowledged": False,
        "beta_updates": False,
        "font_mode": "pretendard",
        "language": "ko",
        "avatar": "",
        "nickname": "",
        "greeting": "{닉네임}님, 오셨군요!",
        "onboarding_complete": False,
    }
    try:
        settings = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(settings, dict):
            try:
                reminders = validate_reminders(settings.get("reminders", {}))
                unit = settings.get("reminder_urgent_unit")
                if unit == "minutes" or (
                    unit == "hours" and reminders["urgent_minutes"] % 60 == 0
                ):
                    reminders["urgent_unit"] = unit
                defaults["reminders"] = reminders
            except (ValueError, TypeError):
                pass
            for key in ("window_width", "window_height"):
                value = settings.get(key)
                if type(value) is int and 240 <= value <= 16384:
                    defaults[key] = value
            for key in (
                "notifications",
                "glass",
                "reduce_motion",
                "attendance_visible",
                "attendance_sync",
                "anki_sync",
                "onboarding_complete",
                "developer_mode",
                "developer_acknowledged",
                "beta_updates",
            ):
                if type(settings.get(key)) is bool:
                    defaults[key] = settings[key]
            for key, limit in (("nickname", 30), ("greeting", 120)):
                value = settings.get(key)
                if (
                    isinstance(value, str)
                    and 0 < len(value.strip()) <= limit
                    and not any(ord(c) < 32 and c != "\n" for c in value)
                ):
                    defaults[key] = value.strip()
            from .avatar import validate_avatar

            try:
                defaults["avatar"] = validate_avatar(settings.get("avatar", ""))
            except ValueError:
                pass
            if settings.get("theme") in THEMES:
                defaults["theme"] = settings["theme"]
            try:
                defaults["timetable_colors"] = validate_timetable_colors(settings.get("timetable_colors"))
            except ValueError:
                pass
            palettes = settings.get("theme_palettes")
            if isinstance(palettes, dict):
                for name in THEMES:
                    if name in palettes:
                        try:
                            defaults["theme_palettes"][name] = validate_theme_palette(palettes[name])
                        except ValueError:
                            pass
            if settings.get("font_mode") in ("pretendard", "windows"):
                defaults["font_mode"] = settings["font_mode"]
            if settings.get("language") in ("ko", "en", "ja"):
                defaults["language"] = settings["language"]
            name = settings.get("active_db")
            reserved = {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10)),
            }
            if (
                isinstance(name, str)
                and 3 < len(name) <= 128
                and name.endswith(".db")
                and name[0].isalnum()
                and all(c.isascii() and (c.isalnum() or c in "._-") for c in name)
                and not any(c in name for c in '/\\:<>"|?*')
                and Path(name).name == name
                and name.split(".")[0].upper() not in reserved
            ):
                defaults["active_db"] = name
    except (OSError, ValueError):
        pass
    defaults["developer_mode"] = (
        defaults["developer_mode"] and defaults["developer_acknowledged"]
    )
    defaults["beta_updates"] = defaults["developer_mode"] and defaults["beta_updates"]
    return defaults


def write_settings(path: str | Path, settings: dict):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = {
        k: v
        for k, v in settings.items()
        if k
        in {
            "window_width",
            "window_height",
            "active_db",
            "theme",
            "theme_palettes",
            "timetable_colors",
            "notifications",
            "reminders",
            "attendance_visible",
            "attendance_sync",
            "anki_sync",
            "glass",
            "reduce_motion",
            "developer_mode",
            "developer_acknowledged",
            "beta_updates",
            "font_mode",
            "language",
            "nickname",
            "greeting",
            "onboarding_complete",
            "avatar",
        }
    }
    reminders = safe.get("reminders")
    if isinstance(reminders, dict) and "urgent_unit" in reminders:
        safe["reminder_urgent_unit"] = reminders["urgent_unit"]
        safe["reminders"] = {key: value for key, value in reminders.items() if key != "urgent_unit"}
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def read_account() -> str:
    prepare_credentials()
    import keyring

    return (
        keyring.get_password(SERVICE, ACCOUNT_KEY)
        or keyring.get_password(LEGACY_SERVICE, ACCOUNT_KEY)
        or ""
    )


def store_account(student_id: str, password: str | None = None):
    prepare_credentials()
    import keyring

    old = read_account()
    student_id = student_id.strip()
    if student_id:
        keyring.set_password(SERVICE, ACCOUNT_KEY, student_id)
        if password is not None and password:
            keyring.set_password(SERVICE + "/password", student_id, password)
    else:
        # Remove both generations so a legacy fallback cannot restore a deleted account.
        identifiers = {old}
        identifiers.update(
            keyring.get_password(service, ACCOUNT_KEY)
            for service in (SERVICE, LEGACY_SERVICE)
        )
        for service in (SERVICE, LEGACY_SERVICE):
            for identifier in filter(None, identifiers):
                for password_service in (service + "/password", service):
                    try:
                        keyring.delete_password(password_service, identifier)
                    except keyring.errors.PasswordDeleteError:
                        pass
            try:
                keyring.delete_password(service, ACCOUNT_KEY)
            except keyring.errors.PasswordDeleteError:
                pass


def read_password(student_id: str) -> str:
    prepare_credentials()
    import keyring

    return (
        keyring.get_password(SERVICE + "/password", student_id)
        or keyring.get_password(LEGACY_SERVICE + "/password", student_id)
        or ""
    )


def migrate_legacy_account(path: str | Path):
    """Move v0.2 plaintext ID into Credential Manager and scrub legacy settings."""
    path = Path(path)
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(settings, dict) or "student_id" not in settings:
        return
    legacy = str(settings.get("student_id") or "").strip()
    try:
        if legacy:
            store_account(legacy)
            import keyring

            oldpw = keyring.get_password(SERVICE, legacy)
            if oldpw:
                keyring.set_password(SERVICE + "/password", legacy, oldpw)
                try:
                    keyring.delete_password(SERVICE, legacy)
                except keyring.errors.PasswordDeleteError:
                    pass
    finally:
        # Always scrub the previous plaintext account field even if keyring fails.
        write_settings(path, settings)
