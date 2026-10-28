"""One Windows identity and a multiresolution icon for every app window."""
from pathlib import Path
import sys
import logging

APP_ID = 'LutteLaurent.Calix'
_native_icons={}


def icon_path():
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
    return root/'asset/icons/calix.ico'


def configure_windows_identity():
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)


def app_icon():
    from PySide6.QtGui import QIcon
    return QIcon(str(icon_path()))


def apply_app_icon(app):
    app.setWindowIcon(app_icon())


def _window_properties(hwnd,values=None):
    """Read/write the window's documented Windows taskbar properties."""
    import ctypes as c
    from ctypes import wintypes as w
    from uuid import UUID
    class GUID(c.Structure):_fields_=[('data',c.c_ubyte*16)]
    def guid(value):return GUID((c.c_ubyte*16).from_buffer_copy(UUID(value).bytes_le))
    class KEY(c.Structure):_fields_=[('fmtid',GUID),('pid',w.DWORD)]
    class VALUE(c.Union):_fields_=[('text',c.c_void_p),('alignment',c.c_longlong*2)]
    class VARIANT(c.Structure):_fields_=[('vt',c.c_ushort),('reserved',c.c_ushort*3),('value',VALUE)]
    iid=guid('886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99');fmt=guid('9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3')
    shell=c.WinDLL('shell32');ole=c.WinDLL('ole32');store=c.c_void_p()
    shell.SHGetPropertyStoreForWindow.argtypes=[w.HWND,c.POINTER(GUID),c.POINTER(c.c_void_p)]
    shell.SHGetPropertyStoreForWindow.restype=c.c_long
    status=shell.SHGetPropertyStoreForWindow(hwnd,c.byref(iid),c.byref(store))
    if status<0:raise OSError(status,'Taskbar property store')
    table=c.cast(store,c.POINTER(c.POINTER(c.c_void_p))).contents
    release=c.WINFUNCTYPE(w.ULONG,c.c_void_p)(table[2])
    set_value=c.WINFUNCTYPE(c.c_long,c.c_void_p,c.POINTER(KEY),c.POINTER(VARIANT))(table[6])
    get_value=c.WINFUNCTYPE(c.c_long,c.c_void_p,c.POINTER(KEY),c.POINTER(VARIANT))(table[5])
    ole.PropVariantClear.argtypes=[c.POINTER(VARIANT)]
    result={}
    try:
        for pid in (2,3,4,5):
            key=KEY(fmt,pid);variant=VARIANT()
            if values is not None:
                text=values.get(pid)
                buffer=c.create_unicode_buffer(text) if text else None
                if buffer:variant.vt=31;variant.value.text=c.cast(buffer,c.c_void_p).value
                status=set_value(store,c.byref(key),c.byref(variant))
                if status<0:raise OSError(status,'Taskbar property')
            else:
                status=get_value(store,c.byref(key),c.byref(variant))
                try:result[pid]=c.wstring_at(variant.value.text) if status>=0 and variant.vt==31 and variant.value.text else ''
                finally:ole.PropVariantClear(c.byref(variant))
    finally:release(store)
    return result


def apply_window_identity(window):
    from PySide6.QtWidgets import QApplication
    if sys.platform!='win32' or QApplication.platformName()!='windows':return
    hwnd=int(window.winId())
    if getattr(window,'_bufs_taskbar_hwnd',None)==hwnd:return
    try:
        import ctypes as c
        from ctypes import wintypes as w
        user=c.WinDLL('user32');user.LoadImageW.argtypes=[w.HINSTANCE,w.LPCWSTR,w.UINT,c.c_int,c.c_int,w.UINT];user.LoadImageW.restype=c.c_void_p
        user.SendMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];user.SendMessageW.restype=w.LPARAM
        path=str(icon_path());window.setWindowIcon(app_icon())
        user.GetDpiForWindow.argtypes=[w.HWND];user.GetDpiForWindow.restype=w.UINT
        scale=(user.GetDpiForWindow(hwnd) or 96)/96
        for kind,base_size in ((0,16),(1,32),(2,16)):
            size=round(base_size*scale)
            key=(path,size)
            if key not in _native_icons:_native_icons[key]=user.LoadImageW(None,path,1,size,size,0x10)
            if not _native_icons[key]:raise OSError('Native icon load failed')
            user.SendMessageW(hwnd,0x80,kind,_native_icons[key])
        command=f'"{sys.executable}"'
        if not getattr(sys,'frozen',False):command+=f' "{Path(__file__).resolve().parents[1]/"main.py"}"'
        _window_properties(hwnd,{2:command,3:path+',0',4:'Calix',5:APP_ID})
        window._bufs_taskbar_hwnd=hwnd
    except Exception:logging.exception('작업표시줄 아이콘 적용 실패')


def clear_window_identity(window):
    hwnd=getattr(window,'_bufs_taskbar_hwnd',None)
    if hwnd:
        try:_window_properties(hwnd,{})
        except OSError:logging.exception('작업표시줄 속성 정리 실패')
        window._bufs_taskbar_hwnd=None


def native_identity_state(window):
    """Inspect the actual HWND, rather than the Qt icon object alone."""
    from PySide6.QtWidgets import QApplication
    if sys.platform!='win32' or QApplication.platformName()!='windows':return {}
    import ctypes as c
    from ctypes import wintypes as w
    user=c.WinDLL('user32');user.SendMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];user.SendMessageW.restype=w.LPARAM
    hwnd=int(window.winId());props=_window_properties(hwnd)
    return {'small_icon':bool(user.SendMessageW(hwnd,0x7F,0,0)),
            'large_icon':bool(user.SendMessageW(hwnd,0x7F,1,0)),
            'window_app_id':props[5],'relaunch_icon':props[3],'relaunch_command':props[2]}
