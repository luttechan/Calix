# Windows 10/11. Keep the operating system's ICU/UCRT DLLs out of the bundle.
from pathlib import Path
import os
import ssl
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH)
debug = os.environ.get('CALIX_DEBUG') == '1'
product = 'Calix-Debug' if debug else 'Calix'
# The build runtime's ssl module loads an adjacent certificate policy file
# when creating SSLContext. Preserve that policy in the frozen runtime too.
tls_policy = Path(ssl.__file__).with_name('codex-rejected-cas.pem')
runtime_data = [(str(tls_policy), '.')] if tls_policy.is_file() else []
a = Analysis(
    [str(root / 'main.py')], pathex=[str(root)],
    binaries=[], datas=[(str(root / 'asset'), 'asset')] + collect_data_files('tzdata') + runtime_data,
    hiddenimports=['learning_calendar.login_browser', 'keyring.backends.Windows'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
system_dlls = {'icuuc.dll', 'icuin.dll', 'ucrtbase.dll'}
a.datas=[item for item in a.datas if item[0].replace('\\','/').lower()!='asset/style/malgun.ttf']
a.binaries = [item for item in a.binaries
              if Path(item[0]).name.lower() not in system_dlls
              and not Path(item[0]).name.lower().startswith(('icudt', 'api-ms-win-'))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=product,
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=debug, disable_windowed_traceback=False,
          icon=str(root / 'asset' / 'icons' / 'calix.ico'),version=str(root/'version_info.txt'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=product+'-1.0.7')
