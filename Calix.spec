# Windows 10/11. Keep the operating system's ICU/UCRT DLLs out of the bundle.
from pathlib import Path
import os
import ssl
import sys
import _ssl,_hashlib,pefile
from importlib.metadata import distribution
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH)
sys.path.insert(0,str(root/'tools'))
from bundle_policy import RUNTIME_ASSETS,keep_entry,keep_tls_library
debug = os.environ.get('CALIX_DEBUG') == '1'
product = 'Calix-Debug' if debug else 'Calix'
# The build runtime's ssl module loads an adjacent certificate policy file
# when creating SSLContext. Preserve that policy in the frozen runtime too.
tls_policy = Path(ssl.__file__).with_name('codex-rejected-cas.pem')
runtime_data = [(str(tls_policy), '.')] if tls_policy.is_file() else []
asset_data=[(str(root/path),str(Path(path).parent)) for path in RUNTIME_ASSETS]
license_data=[]
for name in ('PySide6','PySide6_Essentials','PySide6_Addons','PySide6_WebEngine','shiboken6','requests','cryptography','keyring'):
    package=distribution(name)
    for item in package.files or ():
        if 'licenses' in item.parts or item.name.lower().startswith(('license','copying')):
            path=Path(package.locate_file(item))
            if path.is_file():license_data.append((str(path),f'licenses/{name}'))
a = Analysis(
    [str(root / 'main.py')], pathex=[str(root)],
    binaries=[], datas=asset_data + collect_data_files('tzdata') + runtime_data + license_data,
    hiddenimports=['learning_calendar.login_browser', 'keyring.backends.Windows'],
    hookspath=[str(root/'tools/pyinstaller_hooks')], hooksconfig={}, runtime_hooks=[], excludes=['PySide6.QtTest'], noarchive=False,
)
system_dlls = {'icuuc.dll', 'icuin.dll', 'ucrtbase.dll'}
python_tls=set()
for module in (_ssl,_hashlib):
    pe=pefile.PE(module.__file__,fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
    python_tls.update(item.dll.decode('ascii').lower() for item in pe.DIRECTORY_ENTRY_IMPORT)
    pe.close()
a.datas=[item for item in a.datas if keep_entry(item[0])]
a.binaries = [item for item in a.binaries
              if keep_entry(item[0]) and keep_tls_library(item[0],python_tls) and Path(item[0]).name.lower() not in system_dlls
              and not Path(item[0]).name.lower().startswith(('icudt', 'api-ms-win-'))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=product,
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=debug, disable_windowed_traceback=False,
          icon=str(root / 'asset' / 'icons' / 'calix.ico'),version=str(root/'version_info.txt'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=product+' 1.2.0-r2')
