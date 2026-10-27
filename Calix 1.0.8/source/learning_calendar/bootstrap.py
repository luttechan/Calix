"""Must run before QApplication, in both desktop and login processes."""
import os
import sys

def configure_runtime():
    if sys.platform=='win32':
        # Match the deployed ANV and Lexift text backend. DirectWrite has a
        # different font-selection/rasterization path on this installation.
        os.environ.setdefault('QT_QPA_PLATFORM','windows:fontengine=gdi')
    return os.environ.get('QT_QPA_PLATFORM','')
