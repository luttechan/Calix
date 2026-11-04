import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
import engine_utility


def test_external_installer_environment_drops_only_frozen_runtime_paths(
    tmp_path, monkeypatch
):
    bundle = tmp_path / "_internal"
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    clean = tmp_path / "Windows" / "System32"
    monkeypatch.setenv(
        "PATH", os.pathsep.join((str(bundle), str(bundle / "PySide6"), str(clean)))
    )
    monkeypatch.setenv("QT_PLUGIN_PATH", str(bundle / "plugins"))
    monkeypatch.setenv("PYTHONPATH", str(bundle))
    environment = engine_utility.installer_environment()
    assert environment["PATH"] == str(clean)
    assert "QT_PLUGIN_PATH" not in environment and "PYTHONPATH" not in environment
    assert "QT_PLUGIN_PATH" in os.environ


def test_update_launch_uses_preserving_update_mode_and_resets_dll_search(
    tmp_path, monkeypatch
):
    calls = []

    class Function:
        def __call__(self, value):
            calls.append(("dll", value))
            return 1

    class Kernel:
        SetDllDirectoryW = Function()

    monkeypatch.setattr(engine_utility.ctypes, "WinDLL", lambda *a, **k: Kernel())
    monkeypatch.setattr(
        engine_utility.subprocess,
        "Popen",
        lambda args, **kwargs: calls.append(("spawn", args, kwargs)),
    )
    path = tmp_path / "한글 폴더" / "Calix-Setup.exe"
    engine_utility.launch_installer(path)
    assert calls[0] == ("dll", None)
    assert calls[1][1] == [str(path), "/P", "/UPDATE", "/R"]
    assert calls[1][2]["cwd"] == path.parent and calls[1][2]["close_fds"] is True
