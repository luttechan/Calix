"""Persistent password wrapping with independent UI access scopes."""
from pathlib import Path
import json
import time
from .diary_crypto import new_material, unlock_material, wrap_key, wipe
from . import secure_db

DEFAULT_POLICY = dict(main=False, timetable=False, grades=False, idle_minutes=5)


class AppSecurity:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.path = self.folder / "app-lock.json"
        self.material = None
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
            proof=self.proof.hex(),
        )).encode())

    def expired(self):
        if self.material and self.policy["main"] and self.root_open:
            if time.monotonic() - self.activity >= self.policy["idle_minutes"] * 60:
                self.lock("main")
        return not self.root_open

    def state(self):
        self.expired()
        return dict(configured=self.material is not None, locked=not self.root_open,
                    policy=self.policy, unlocked=sorted(self.scopes),
                    retry_after=max(0, int(self.retry_at - time.monotonic()) + 1))

    def authenticate(self, password):
        if time.monotonic() < self.retry_at:
            raise ValueError("잠시 후 다시 시도하세요.")
        try:
            key = unlock_material(self.material, password)
        except ValueError:
            self.failures += 1
            if self.failures >= 5:
                self.retry_at = time.monotonic() + min(300, 30 * (self.failures - 4))
            raise ValueError("비밀번호를 확인하세요.") from None
        self.failures = 0
        return key

    def initialize(self, password, policy):
        if self.material:
            raise ValueError("이미 비밀번호가 설정되어 있습니다.")
        policy = self.validate(policy)
        self.key, self.material = new_material(password)
        self.policy = policy
        self.save()  # Persist the wrapped key before converting any database.
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

    def unlock(self, password, scope="main"):
        if scope not in ("main", "timetable", "grades"):
            raise ValueError("잠금 범위를 확인하세요.")
        key = self.authenticate(password)
        try:
            if secure_db.open_file(self.proof, bytes(key)) != json.dumps(self.policy, sort_keys=True).encode():
                raise ValueError("잠금 설정이 변경되었습니다.")
            if self.key is None:
                self.key = bytearray(key)
                self.activate()
            self.root_open = True
            self.activity = time.monotonic()
            if scope != "main":
                self.scopes.add(scope)
        finally:
            wipe(key)

    def configure(self, password, policy, replacement=None):
        if self.expired() or self.key is None:
            raise ValueError("먼저 잠금을 해제하세요.")
        key = self.authenticate(password)
        try:
            policy = self.validate(policy)
            if replacement:
                self.material = wrap_key(replacement, key)
            self.policy = policy
            self.save()
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
        if method.startswith("security.") or method in ("bootstrap", "quit", "engine.state", "data.reset"):
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
