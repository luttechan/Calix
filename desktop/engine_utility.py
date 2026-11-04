"""On-demand native file dialogs and the existing verified update installer."""

from pathlib import Path
import json, sys, os, hashlib, subprocess, ctypes


def installer_environment():
    """External installers must not inherit the frozen engine's DLL paths."""
    environment = os.environ.copy()
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        root = Path(bundle).resolve()
        entries = []
        for entry in environment.get("PATH", "").split(os.pathsep):
            if not entry:
                continue
            try:
                if Path(entry.strip('"')).resolve().is_relative_to(root):
                    continue
            except (OSError, ValueError):
                continue
            entries.append(entry)
        environment["PATH"] = os.pathsep.join(entries)
    for key in (
        "PYTHONHOME",
        "PYTHONPATH",
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM_PLUGIN_PATH",
        "QML2_IMPORT_PATH",
        "QML_IMPORT_PATH",
    ):
        environment.pop(key, None)
    return environment


def launch_installer(path):
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype = ctypes.c_int
        if not kernel.SetDllDirectoryW(None):
            raise OSError("Unable to restore Windows DLL search paths")
    subprocess.Popen(
        [str(path), "/P", "/UPDATE", "/R"],
        cwd=path.parent,
        env=installer_environment(),
        close_fds=True,
        creationflags=(
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        ),
    )


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
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, parent)
        if handle:
            try:
                if kernel.WaitForSingleObject(handle, 30000) != 0:
                    return 2
            finally:
                kernel.CloseHandle(handle)
        elif ctypes.get_last_error() not in (0, 87):
            return 2
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
            return 2
    launch_installer(path)
    return 0
