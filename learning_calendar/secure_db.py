"""SQLCipher connections and authenticated files for password-protected profiles."""
from pathlib import Path
import os
import secrets
import threading
from urllib.parse import unquote, urlsplit
from sqlcipher3 import dbapi2 as driver
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

Row = driver.Row
DatabaseError = driver.DatabaseError
IntegrityError = driver.IntegrityError
OperationalError = driver.OperationalError
Error = driver.Error
Connection = driver.Connection
_keys = {}
_mutex = threading.RLock()
MAGIC = b"Calix encrypted file v1\0"


def register(folder, key):
    with _mutex:
        _keys[Path(folder).resolve()] = bytes(key)


def unregister(folder):
    with _mutex:
        _keys.pop(Path(folder).resolve(), None)


def key_for(path):
    path = Path(path).resolve()
    with _mutex:
        return next((key for folder, key in _keys.items() if path.is_relative_to(folder)), None)


def atomic_write(path, raw):
    path = Path(path)
    pending = path.with_name(path.name + ".pending-" + secrets.token_hex(6))
    try:
        with pending.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def seal(raw, key):
    nonce = os.urandom(12)
    return MAGIC + nonce + AESGCM(key).encrypt(nonce, raw, MAGIC)


def open_file(raw, key):
    if not raw.startswith(MAGIC):
        return raw
    if key is None:
        raise ValueError("비밀번호로 잠금을 해제하세요.")
    try:
        return AESGCM(key).decrypt(raw[len(MAGIC):len(MAGIC)+12], raw[len(MAGIC)+12:], MAGIC)
    except Exception:
        raise ValueError("비밀번호 또는 암호화 파일을 확인하세요.") from None


def read_file(path):
    return open_file(Path(path).read_bytes(), key_for(path))


def write_file(path, raw):
    key = key_for(path)
    atomic_write(path, seal(raw, key) if key else raw)


def encrypt_database(path, key):
    path = Path(path)
    if not path.is_file():
        return
    with path.open("rb") as stream:
        plain = stream.read(16) == b"SQLite format 3\0"
    if not plain:
        return
    pending = path.with_name(path.name + ".cipher-" + secrets.token_hex(6))
    source = driver.connect(str(path), timeout=15)
    try:
        source.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        source.execute("PRAGMA journal_mode=DELETE")
        version = source.execute("PRAGMA user_version").fetchone()[0]
        # The key is random binary material, never the user's password.
        source.execute("ATTACH DATABASE ? AS encrypted KEY \"x'" + key.hex() + "'\"", (str(pending),))
        source.execute("SELECT sqlcipher_export('encrypted')")
        source.execute(f"PRAGMA encrypted.user_version={version}")
        source.execute("DETACH DATABASE encrypted")
    finally:
        source.close()
    check = driver.connect(str(pending))
    try:
        check.execute('PRAGMA key = "x\'' + key.hex() + '\'"')
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("암호화 저장소를 검증하지 못했습니다.")
    finally:
        check.close()
    os.replace(pending, path)


def connect(database, *args, **kwargs):
    name = str(database)
    if name == ":memory:":
        return driver.connect(name, *args, **kwargs)
    raw_path = unquote(urlsplit(name).path) if kwargs.get("uri") and name.startswith("file:") else name
    if os.name == "nt" and len(raw_path) > 2 and raw_path[0] == "/" and raw_path[2] == ":":
        raw_path = raw_path[1:]
    path = Path(raw_path)
    key = key_for(path)
    if key and path.exists():
        encrypt_database(path, key)
    db = driver.connect(name, *args, **kwargs)
    try:
        if key:
            db.execute('PRAGMA key = "x\'' + key.hex() + '\'"')
            db.execute("PRAGMA cipher_memory_security=ON")
        db.execute("PRAGMA temp_store=MEMORY")
        return db
    except Exception:
        db.close()
        raise


def attach(db, path, alias):
    if alias not in ("diary_restore", "vault_restore", "holiday_restore"):
        raise ValueError("저장소 이름을 확인하세요.")
    key = key_for(path)
    suffix = ' KEY "x\'' + key.hex() + '\'"' if key else ""
    db.execute(f"ATTACH DATABASE ? AS {alias}" + suffix, (str(path),))
