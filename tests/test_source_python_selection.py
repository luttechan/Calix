import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture
def launcher():
    path = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("runtime_launcher", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_project_environment_is_selected_without_a_relaunch_loop(launcher, tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    directory = "Scripts/python.exe" if launcher.os.name == "nt" else "bin/python"
    candidate = tmp_path / ".venv" / directory
    assert launcher.project_python() is None
    candidate.parent.mkdir(parents=True)
    candidate.touch()
    assert launcher.project_python() == str(candidate)
    monkeypatch.setattr(sys, "executable", str(candidate))
    assert launcher.project_python() is None


def test_source_relaunch_preserves_arguments_and_exit_status(launcher, monkeypatch, tmp_path):
    selected = str(tmp_path / "python.exe")
    monkeypatch.setattr(launcher, "configure_tool_paths", lambda: None)
    monkeypatch.setattr(launcher, "project_python", lambda: selected)
    arguments = ["main.py", "--preview", "--no-browser", "--data-dir", "data with spaces"]
    monkeypatch.setattr(sys, "argv", arguments)
    calls = []
    def call(args, **kwargs):
        calls.append((args, kwargs))
        return 7
    monkeypatch.setattr(launcher.subprocess, "call", call)
    assert launcher.main() == 7
    assert calls == [([selected, str(launcher.ROOT / "main.py"), *arguments[1:]], {"cwd": launcher.ROOT})]


def test_outdated_native_runtime_stops_before_building(launcher, monkeypatch):
    monkeypatch.setattr(launcher.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 1, '{"python":"3.14.6"}', ""))
    with pytest.raises(RuntimeError, match="3.14.10"):
        launcher.check_build_python()
