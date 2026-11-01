import importlib.util
from pathlib import Path
import json
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('package_current_desktop',ROOT/'desktop/tools/package_desktop.py')
packager=importlib.util.module_from_spec(spec);spec.loader.exec_module(packager)

def prepare(tmp_path):
    files={
        'desktop/package.json':json.dumps(dict(version='1.5.0')),
        'desktop/src-tauri/tauri.conf.json':json.dumps(dict(productName='Calix',version='1.5.0')),
        'desktop/src-tauri/target/release/calix-desktop.exe':'current-ui',
        'desktop/src-tauri/binaries/calix-engine-x86_64-pc-windows-msvc.exe':'current-engine',
        'desktop/src-tauri/engine/_internal/runtime.txt':'current-runtime',
        'desktop/src-tauri/target/release/bundle/nsis/Calix_1.4.21_x64-setup.exe':'old-cached-installer',
        'LICENSE':'license','asset/style/Pretendard-OFL.txt':'font license',
    }
    for name,text in files.items():
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')

def test_cached_installer_from_old_version_is_never_selected(tmp_path,monkeypatch):
    prepare(tmp_path)
    (tmp_path/'desktop/src-tauri/target/release/bundle/nsis/Calix_1.5.0_x64-setup.exe').write_bytes(b'current-installer')
    monkeypatch.setattr(packager,'ROOT',tmp_path)
    packager.main()
    assert (tmp_path/'desktop/.build/packages/Calix-1.5.0-Setup-x64.exe').read_bytes()==b'current-installer'

def test_missing_current_installer_never_falls_back_to_old_version(tmp_path,monkeypatch):
    prepare(tmp_path);monkeypatch.setattr(packager,'ROOT',tmp_path)
    with pytest.raises(AssertionError,match='Current installer missing'):packager.main()
