"""Must run before QApplication, in both desktop and login processes."""
import os
import sys

def configure_runtime():
    if sys.platform=='win32':
        # Native Windows text shaping and fractional-DPI font handling.
        # An installer launched by Calix 1.1 inherits its old GDI default.
        # Preserve alternate/headless platforms, but migrate that legacy value.
        if os.environ.get('QT_QPA_PLATFORM') in (None,'windows:fontengine=gdi'):
            os.environ['QT_QPA_PLATFORM']='windows:fontengine=directwrite'
    return os.environ.get('QT_QPA_PLATFORM','')
