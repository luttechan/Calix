import os
import subprocess
import sys
from pathlib import Path

def test_directwrite_is_selected_before_any_qt_import():
    root=Path(__file__).parents[1]
    env=os.environ.copy();env.pop('QT_QPA_PLATFORM',None)
    code=f"import sys;sys.path.insert(0,{str(root)!r});import learning_calendar,os;assert os.environ['QT_QPA_PLATFORM']=='windows:fontengine=directwrite';assert 'PySide6' not in sys.modules"
    result=subprocess.run([sys.executable,'-B','-c',code],env=env,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr

def test_explicit_headless_test_platform_is_preserved(monkeypatch):
    from learning_calendar.bootstrap import configure_runtime
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen')
    assert configure_runtime()=='offscreen'


def test_update_from_previous_process_migrates_legacy_gdi(monkeypatch):
    from learning_calendar.bootstrap import configure_runtime
    monkeypatch.setenv('QT_QPA_PLATFORM','windows:fontengine=gdi')
    assert configure_runtime()=='windows:fontengine=directwrite'
