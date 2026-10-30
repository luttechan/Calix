"""Windows DPAPI encryption for locally persisted campus session cookies.
Only the current Windows user can decrypt this file; no raw token written to disk.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import sys
from pathlib import Path

if sys.platform == 'win32':
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]

    _crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    _kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    _crypt.CryptProtectData.argtypes = [ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR, ctypes.c_void_p,
                                        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
    _crypt.CryptProtectData.restype = wintypes.BOOL
    _crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
                                          ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
    _crypt.CryptUnprotectData.restype = wintypes.BOOL
    _kernel.LocalFree.argtypes = [ctypes.c_void_p]
    _kernel.LocalFree.restype = ctypes.c_void_p


def _protect(data: bytes, decrypt: bool = False) -> bytes:
    if sys.platform != 'win32':
        raise RuntimeError('세션 보관은 Windows에서만 지원합니다.')
    buf = ctypes.create_string_buffer(data)
    blob = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    out = DATA_BLOB()
    func = _crypt.CryptUnprotectData if decrypt else _crypt.CryptProtectData
    args = (ctypes.byref(blob), None, None, None, None, 0x1, ctypes.byref(out)) if decrypt else (
             ctypes.byref(blob), 'BUFS 학습 달력', None, None, None, 0x1, ctypes.byref(out))
    if not func(*args):
        raise OSError(ctypes.get_last_error(), 'Windows DPAPI 암복호화 실패')
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        _kernel.LocalFree(out.pbData)


def save_session(path: str | Path, raw: bytes):
    if sys.platform != 'win32': return
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    encrypted = _protect(raw)
    tmp = path.with_suffix('.tmp')
    tmp.write_bytes(encrypted)
    tmp.replace(path)


def load_session(path: str | Path) -> bytes | None:
    if sys.platform != 'win32': return None
    try:
        return _protect(Path(path).read_bytes(), decrypt=True)
    except (OSError,ValueError):
        return None
