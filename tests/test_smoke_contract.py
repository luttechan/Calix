import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_source_entry_identifies_react_and_never_launches_legacy_qt():
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--check"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["legacyQt"] is False
    assert data["entry"] == "desktop/src/main.tsx"
    assert data["native"] == "pnpm tauri dev"


def test_missing_native_toolchain_does_not_fall_back_to_old_application(monkeypatch):
    spec = importlib.util.spec_from_file_location("source_launcher", ROOT / "main.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    monkeypatch.setattr(launcher.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="Rust"):
        launcher.native_command()
