"""Persistent password wrapping with independent UI access scopes."""
from pathlib import Path
import json
import re
import sys
import time
from .diary_crypto import new_material, unlock_material, wrap_key, wipe
from .secure_session import _protect
from . import secure_db

DEFAULT_POLICY = dict(main=False, timetable=False, grades=False, idle_minutes=5)
PIN_LENGTHS = {"pin4": 4, "pin6": 6}
PIN_HEADER = b"Calix Windows PIN\0"


def credential_minimum(password, mode):
    if not isinstance(mode, str):
        raise ValueError("잠금 방식을 확인하세요.")
    if mode in PIN_LENGTHS:
        length = PIN_LENGTHS[mode]
        if sys.platform != "win32":
            raise ValueError("PIN은 Windows에서만 설정할 수 있습니다.")
        if not isinstance(password, str) or not re.fullmatch(r"[0-9]{%d}" % length, password):
            raise ValueError("선택한 자릿수만큼 숫자를 입력하세요.")
        return length
    minimum = 12 if mode == "legacy" else 6
    if mode not in ("legacy", "password") or not isinstance(password, str) or not minimum <= len(password) <= 1024:
        raise ValueError("비밀번호 길이를 확인하세요.")
    return minimum


def protect_material(material, mode):
    return PIN_HEADER + _protect(material) if mode in PIN_LENGTHS else material


def unlock_app_material(material, password):
    if material.startswith(PIN_HEADER):
        try:
            material = _protect(material[len(PIN_HEADER):], decrypt=True)
        except (OSError, RuntimeError):
            raise ValueError("PIN은 백업을 만든 Windows 계정에서 사용하세요.") from None
    return unlock_material(material, password)


class AppSecurity:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.path = self.folder / "app-lock.json"
        self.material = None
        self.mode = "legacy"
        self.key = None
        self.policy = DEFAULT_POLICY.copy()
        self.root_open = True
        self.scopes = set()
        self.activity = time.monotonic()
        self.failures = 0
        self.retry_at = 0
        if self.path.exists():
            try:
                value = json.loads(self.path.read_bytes())
                if value["version"] != 1:
                    raise ValueError()
                self.material = bytes.fromhex(value["header"])
                self.mode = value.get("credential_mode", "legacy")
                if self.mode not in ("legacy", "password", *PIN_LENGTHS):
                    raise ValueError()
                if self.material.startswith(PIN_HEADER) != (self.mode in PIN_LENGTHS):
                    raise ValueError()
                self.policy = self.validate(value["policy"])
                self.proof = bytes.fromhex(value["proof"])
                self.root_open = False
            except Exception:
                raise ValueError("잠금 설정이 손상되었습니다. 자료를 보존한 뒤 복구하세요.") from None

    @staticmethod
    def validate(value):
        if not isinstance(value, dict):
            raise ValueError("잠금 설정을 확인하세요.")
        result = {}
        for name in ("main", "timetable", "grades"):
            if type(value.get(name)) is not bool:
                raise ValueError("잠금 설정을 확인하세요.")
            result[name] = value[name]
        minutes = value.get("idle_minutes")
        if type(minutes) is not int or not 1 <= minutes <= 1440:
            raise ValueError("잠금 시간은 1~1440분으로 설정하세요.")
        result["idle_minutes"] = minutes
        return result

    def save(self):
        raw_policy = json.dumps(self.policy, sort_keys=True).encode()
        self.proof = secure_db.seal(raw_policy, bytes(self.key))
        secure_db.atomic_write(self.path, json.dumps(dict(
            version=1, header=self.material.hex(), policy=self.policy,
            proof=self.proof.hex(), credential_mode=self.mode,
        )).encode())

    def expired(self):
        if self.material and self.policy["main"] and self.root_open:
            if time.monotonic() - self.activity >= self.policy["idle_minutes"] * 60:
                self.lock("main")
        return not self.root_open

    def state(self):
        self.expired()
        return dict(configured=self.material is not None, locked=not self.root_open,
                    policy=self.policy, unlocked=sorted(self.scopes), credential_mode=self.mode,
                    pin_supported=sys.platform == "win32",
                    retry_after=max(0, int(self.retry_at - time.monotonic()) + 1))

    def authenticate(self, password):
        if time.monotonic() < self.retry_at:
            raise ValueError("잠시 후 다시 시도하세요.")
        try:
            key = unlock_app_material(self.material, password)
        except (ValueError, OSError):
            self.failures += 1
            if self.failures >= 5:
                self.retry_at = time.monotonic() + min(300, 30 * (self.failures - 4))
            raise ValueError("비밀번호를 확인하세요.") from None
        self.failures = 0
        return key

    def initialize(self, password, policy, mode="legacy"):
        if self.material:
            raise ValueError("이미 비밀번호가 설정되어 있습니다.")
        policy = self.validate(policy)
        key, material = new_material(password, minimum=credential_minimum(password, mode))
        try:
            self.material = protect_material(material, mode)
        except Exception:
            wipe(key)
            raise
        self.key, self.mode = key, mode
        self.policy = policy
        try:
            self.save()  # Persist the wrapped key before converting any database.
        except Exception:
            self.close()
            self.material, self.mode, self.policy = None, "legacy", DEFAULT_POLICY.copy()
            raise
        self.activate()

    def activate(self):
        secure_db.register(self.folder, self.key)
        for path in self.folder.rglob("*.db"):
            if path.is_symlink() or not path.resolve().is_relative_to(self.folder.resolve()):
                raise ValueError("암호화할 파일 경로를 확인하세요.")
            secure_db.encrypt_database(path, bytes(self.key))
        for path in self.folder.glob("*.calix"):
            if path.is_symlink() or not path.resolve().is_relative_to(self.folder.resolve()):
                raise ValueError("백업 파일 경로를 확인하세요.")
            raw = path.read_bytes()
            if not raw.startswith(b"Calix password backup v1\0"):
                raw = secure_db.open_file(raw, bytes(self.key))
                header = self.material.hex().encode()
                protected = b"Calix password backup v1\0" + len(header).to_bytes(4, "big") + header + secure_db.seal(raw, bytes(self.key))
                secure_db.atomic_write(path, protected)
        self.root_open = True
        self.activity = time.monotonic()

    def unlock(self, password, scope="main", replacement=None, mode=None):
        if scope not in ("main", "timetable", "grades"):
            raise ValueError("잠금 범위를 확인하세요.")
        key = self.authenticate(password)
        try:
            if secure_db.open_file(self.proof, bytes(key)) != json.dumps(self.policy, sort_keys=True).encode():
                raise ValueError("잠금 설정이 변경되었습니다.")
            if replacement is not None or mode is not None:
                if scope != "main" or self.mode != "legacy" or mode in (None, "legacy"):
                    raise ValueError("잠금 요청을 확인하세요.")
                self.update_credentials(key, self.policy, replacement, mode)
            if self.key is None:
                self.key = bytearray(key)
                self.activate()
            self.root_open = True
            self.activity = time.monotonic()
            if scope != "main":
                self.scopes.add(scope)
        finally:
            wipe(key)

    def update_credentials(self, key, policy, replacement, mode):
        previous = self.material, self.mode, self.policy, self.proof
        if replacement is not None or mode != self.mode:
            minimum = credential_minimum(replacement, mode)
            self.material = protect_material(wrap_key(replacement, key, minimum=minimum), mode)
            self.mode = mode
        self.policy = policy
        try:
            proof = secure_db.seal(json.dumps(policy, sort_keys=True).encode(), bytes(key))
            secure_db.atomic_write(self.path, json.dumps(dict(
                version=1, header=self.material.hex(), policy=policy,
                proof=proof.hex(), credential_mode=self.mode,
            )).encode())
            self.proof = proof
        except Exception:
            self.material, self.mode, self.policy, self.proof = previous
            raise

    def configure(self, password, policy, replacement=None, mode=None):
        if self.expired() or self.key is None:
            raise ValueError("먼저 잠금을 해제하세요.")
        key = self.authenticate(password)
        try:
            policy = self.validate(policy)
            self.update_credentials(key, policy, replacement or None, mode or self.mode)
            self.scopes.clear()
            self.activity = time.monotonic()
        finally:
            wipe(key)

    def lock(self, scope):
        if self.material:
            if scope == "main":
                self.root_open = False
                self.scopes.clear()
            elif scope in ("timetable", "grades"):
                self.scopes.discard(scope)
            else:
                raise ValueError("잠금 범위를 확인하세요.")

    def require(self, method):
        if method.startswith("security.") or method in ("bootstrap", "quit", "engine.state", "data.reset", "update.startup"):
            return
        if method.startswith("grades.") and not self.material:
            raise ValueError("학점 메뉴를 사용하려면 비밀번호를 설정하세요.")
        if self.expired():
            raise ValueError("비밀번호로 잠금을 해제하세요.")
        scope = "timetable" if method.startswith("timetable.") else "grades" if method.startswith("grades.") else None
        if scope and self.material and self.policy[scope] and scope not in self.scopes:
            raise ValueError("비밀번호로 잠금을 해제하세요.")
        if self.material and method.startswith(("developer.", "diagnostics.")):
            if any(self.policy[name] and name not in self.scopes for name in ("timetable", "grades")):
                raise ValueError("보호된 메뉴를 먼저 잠금 해제하세요.")

    def close(self):
        secure_db.unregister(self.folder)
        wipe(self.key)
        self.key = None
