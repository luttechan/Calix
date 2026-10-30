"""On-demand native file dialogs and the existing verified update installer."""

from pathlib import Path
import json, sys, os, hashlib, subprocess, ctypes


def install(path, digest, parent):
    path = Path(path).resolve()
    import tempfile

    base = Path(tempfile.gettempdir()).resolve()
    if (
        path.name != "Calix-Setup.exe"
        or path.parent.parent != base
        or not path.parent.name.startswith("Calix-update-")
    ):
        return 2
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
            return 2
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, parent)
        if handle:
            try:
                if kernel.WaitForSingleObject(handle, 30000) != 0:
                    return 2
            finally:
                kernel.CloseHandle(handle)
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
            return 2
    subprocess.Popen([str(path)], cwd=path.parent)
    return 0
