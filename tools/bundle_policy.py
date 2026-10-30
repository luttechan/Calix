"""Release inputs for the native Widgets application and its login browser."""
from pathlib import PurePosixPath

RUNTIME_ASSETS=(
    'asset/startup.bmp','asset/profile-avatar.png','asset/icons/calix.ico',
    'asset/icons/github.png','asset/icons/github-dark.png',
    'asset/icons/paypal.png','asset/icons/paypal-dark.png',
    'asset/calendar/kr_public_holidays.json','asset/calendar/catholic_feasts.json',
    'asset/calendar/HOLIDAYS-MIT.txt','asset/style/Pretendard-OFL.txt',
    *(f'asset/style/CalixSans-{style}.ttf' for style in ('Regular','Medium','SemiBold','Bold','Italic','BoldItalic')),
)


def keep_entry(name):
    path=PurePosixPath(name.replace('\\','/').lower());parts=path.parts;base=path.name
    if 'qml' in parts or 'qmltooling' in parts:return False
    if '.debug.' in base or base=='qtwebengineprocessd.exe':return False
    if base.startswith('qtwebengine_devtools_resources'):return False
    # Qt uses Windows Schannel. Python's TLS files are selected by PE imports.
    if base=='qopensslbackend.dll':return False
    if 'translations' in parts:
        if 'qtwebengine_locales' in parts:return base in {'ko.pak','en-us.pak'}
        return base in {'qt_ko.qm','qtbase_ko.qm','qtwebengine_ko.qm'}
    return True


def keep_tls_library(name,required):
    base=PurePosixPath(name.replace('\\','/').lower()).name
    return not (base.startswith(('libcrypto-','libssl-')) and base.endswith('.dll')) or base in required
