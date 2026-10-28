"""Keep QtQml's native dependencies without collecting unused QML plugins."""
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports,binaries,datas=add_qt6_dependencies(__file__)
