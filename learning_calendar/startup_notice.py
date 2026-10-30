"""Early, responsive Windows startup image. No Qt import on this path."""
from pathlib import Path
import os
import sys
import threading
import time


class StartupNotice:
    def __init__(self):
        self.ready=threading.Event();self.closed=threading.Event();self.finishing=threading.Event();self.failed=threading.Event()
        self.hwnd=0;self.error='';self.thread=None;self._post=None;self.painted_at=None
    @property
    def active(self):return self.thread is not None and not self.closed.is_set()
    def start(self):
        if self.thread is not None:return self
        self.thread=threading.Thread(target=self._run_guarded,name='Calix startup image',daemon=True);self.thread.start();self.ready.wait(.4);return self
    def finish(self):
        self.finishing.set()
        if self.hwnd and self._post:self._post(self.hwnd,0x8001,0,0)
        if self.thread and self.thread is not threading.current_thread():self.thread.join(.5)
    def fail(self):
        self.failed.set()
        if self.hwnd and self._post:self._post(self.hwnd,0x8002,0,0)
    def wait_closed(self):
        if self.thread:self.closed.wait()
    def native_state(self):
        result=dict(visible=False,topmost=False,closed=self.closed.is_set(),error=self.error)
        if not self.hwnd or sys.platform!='win32':return result
        import ctypes as c
        from ctypes import wintypes as w
        user=c.WinDLL('user32');user.IsWindowVisible.argtypes=[w.HWND];user.IsWindowVisible.restype=w.BOOL
        get_style=user.GetWindowLongPtrW;get_style.argtypes=[w.HWND,c.c_int];get_style.restype=c.c_ssize_t
        result.update(visible=bool(user.IsWindowVisible(self.hwnd)),topmost=bool(get_style(self.hwnd,-20)&8));return result
    def _run_guarded(self):
        try:self._run()
        except BaseException as exc:self.error=repr(exc);self.ready.set();self.closed.set()
    def _run(self):
        import ctypes as c
        from ctypes import wintypes as w
        user=c.WinDLL('user32',use_last_error=True);gdi=c.WinDLL('gdi32',use_last_error=True);kernel=c.WinDLL('kernel32',use_last_error=True)
        proc_type=c.WINFUNCTYPE(c.c_ssize_t,w.HWND,w.UINT,w.WPARAM,w.LPARAM)
        class CLASS(c.Structure):
            _fields_=[('style',w.UINT),('proc',proc_type),('cls_extra',c.c_int),('wnd_extra',c.c_int),('instance',w.HINSTANCE),('icon',w.HICON),('cursor',w.HANDLE),('brush',w.HBRUSH),('menu',w.LPCWSTR),('name',w.LPCWSTR)]
        class PAINT(c.Structure):
            _fields_=[('hdc',w.HDC),('erase',w.BOOL),('rect',w.RECT),('restore',w.BOOL),('inc_update',w.BOOL),('reserved',c.c_byte*32)]
        class MONITOR(c.Structure):_fields_=[('size',w.DWORD),('monitor',w.RECT),('work',w.RECT),('flags',w.DWORD)]
        def bind(lib,name,args,result):
            fn=getattr(lib,name);fn.argtypes=args;fn.restype=result;return fn
        create=bind(user,'CreateWindowExW',[w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,c.c_int,c.c_int,c.c_int,c.c_int,w.HWND,w.HMENU,w.HINSTANCE,c.c_void_p],w.HWND)
        default=bind(user,'DefWindowProcW',[w.HWND,w.UINT,w.WPARAM,w.LPARAM],c.c_ssize_t)
        register=bind(user,'RegisterClassW',[c.POINTER(CLASS)],w.ATOM);unregister=bind(user,'UnregisterClassW',[w.LPCWSTR,w.HINSTANCE],w.BOOL)
        load=bind(user,'LoadImageW',[w.HINSTANCE,w.LPCWSTR,w.UINT,c.c_int,c.c_int,w.UINT],w.HANDLE)
        show=bind(user,'ShowWindow',[w.HWND,c.c_int],w.BOOL);update=bind(user,'UpdateWindow',[w.HWND],w.BOOL)
        destroy=bind(user,'DestroyWindow',[w.HWND],w.BOOL);self._post=bind(user,'PostMessageW',[w.HWND,w.UINT,w.WPARAM,w.LPARAM],w.BOOL)
        begin=bind(user,'BeginPaint',[w.HWND,c.POINTER(PAINT)],w.HDC);end=bind(user,'EndPaint',[w.HWND,c.POINTER(PAINT)],w.BOOL)
        invalid=bind(user,'InvalidateRect',[w.HWND,c.POINTER(w.RECT),w.BOOL],w.BOOL)
        set_timer=bind(user,'SetTimer',[w.HWND,c.c_size_t,w.UINT,c.c_void_p],c.c_size_t);kill_timer=bind(user,'KillTimer',[w.HWND,c.c_size_t],w.BOOL)
        get_message=bind(user,'GetMessageW',[c.POINTER(w.MSG),w.HWND,w.UINT,w.UINT],w.BOOL)
        dispatch=bind(user,'DispatchMessageW',[c.POINTER(w.MSG)],c.c_ssize_t);translate=bind(user,'TranslateMessage',[c.POINTER(w.MSG)],w.BOOL)
        instance=bind(kernel,'GetModuleHandleW',[w.LPCWSTR],w.HMODULE)(None)
        dc_create=bind(gdi,'CreateCompatibleDC',[w.HDC],w.HDC);dc_delete=bind(gdi,'DeleteDC',[w.HDC],w.BOOL)
        select=bind(gdi,'SelectObject',[w.HDC,w.HANDLE],w.HANDLE);delete=bind(gdi,'DeleteObject',[w.HANDLE],w.BOOL)
        stretch=bind(gdi,'StretchBlt',[w.HDC,c.c_int,c.c_int,c.c_int,c.c_int,w.HDC,c.c_int,c.c_int,c.c_int,c.c_int,w.DWORD],w.BOOL)
        mode=bind(gdi,'SetStretchBltMode',[w.HDC,c.c_int],c.c_int)
        brush=bind(gdi,'CreateSolidBrush',[w.DWORD],w.HBRUSH);ellipse=bind(gdi,'Ellipse',[w.HDC,c.c_int,c.c_int,c.c_int,c.c_int],w.BOOL)
        fill=bind(user,'FillRect',[w.HDC,c.POINTER(w.RECT),w.HBRUSH],c.c_int)
        text=bind(user,'DrawTextW',[w.HDC,w.LPCWSTR,c.c_int,c.POINTER(w.RECT),w.UINT],c.c_int)
        font_create=bind(gdi,'CreateFontW',[c.c_int]*5+[w.DWORD]*8+[w.LPCWSTR],w.HFONT)
        set_text=bind(gdi,'SetTextColor',[w.HDC,w.DWORD],w.DWORD);set_bg=bind(gdi,'SetBkMode',[w.HDC,c.c_int],c.c_int)
        bitmap=memory=old_bitmap=error_font=error_brush=0;brushes=[];class_name=f'Calix.Startup.{os.getpid()}.{id(self)}';registered=False;frame=0
        root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]));asset=root/'asset/startup.bmp'
        try:
            if hasattr(user,'SetThreadDpiAwarenessContext'):bind(user,'SetThreadDpiAwarenessContext',[c.c_void_p],c.c_void_p)(c.c_void_p(-4))
            point=w.POINT();bind(user,'GetCursorPos',[c.POINTER(w.POINT)],w.BOOL)(c.byref(point))
            monitor=bind(user,'MonitorFromPoint',[w.POINT,w.DWORD],w.HANDLE)(point,2);info=MONITOR();info.size=c.sizeof(info)
            if not bind(user,'GetMonitorInfoW',[w.HANDLE,c.POINTER(MONITOR)],w.BOOL)(monitor,c.byref(info)):raise c.WinError(c.get_last_error())
            dpi=bind(user,'GetDpiForSystem',[],w.UINT)() if hasattr(user,'GetDpiForSystem') else 96
            scale=min(max(1.,dpi/96),(info.work.right-info.work.left-32)/640,(info.work.bottom-info.work.top-32)/360)
            width=max(1,round(640*scale));height=max(1,round(360*scale));x=(info.work.left+info.work.right-width)//2;y=(info.work.top+info.work.bottom-height)//2
            bitmap=load(None,str(asset),0,0,0,0x2010)
            if not bitmap:raise c.WinError(c.get_last_error())
            import struct
            with asset.open('rb') as source:header=source.read(26)
            source_width,source_height=struct.unpack_from('<ii',header,18);source_height=abs(source_height)
            memory=dc_create(None);old_bitmap=select(memory,bitmap)
            def rgb(r,g,b):return r|(g<<8)|(b<<16)
            for value in (0,1,2,3,4,5,6,7):brushes.append(brush(rgb(175-value*12,187-value*12,219-value*9)))
            error_brush=brush(rgb(243,246,252));error_font=font_create(-round(16*scale),0,0,0,500,0,0,0,1,0,0,5,0,'Malgun Gothic')
            null_pen=bind(gdi,'GetStockObject',[c.c_int],w.HANDLE)(8)
            def paint(hwnd):
                ps=PAINT();hdc=begin(hwnd,c.byref(ps))
                try:
                    mode(hdc,4);stretch(hdc,0,0,width,height,memory,0,0,source_width,source_height,0x00CC0020)
                    if self.failed.is_set():
                        rect=w.RECT(round(45*scale),round(206*scale),round(595*scale),round(324*scale));fill(hdc,c.byref(rect),error_brush)
                        old_font=select(hdc,error_font);set_bg(hdc,1);set_text(hdc,rgb(50,65,92));rect.bottom=round(278*scale)
                        text(hdc,'시작하지 못했습니다.\n닫고 다시 실행해 주세요.',-1,c.byref(rect),0x11);select(hdc,old_font)
                    else:
                        old_pen=select(hdc,null_pen)
                        for i in range(3):
                            old_brush=select(hdc,brushes[(frame//3+i*2)%len(brushes)]);cx=round((304+i*16)*scale);cy=round(295*scale);r=max(2,round(3*scale));ellipse(hdc,cx-r,cy-r,cx+r,cy+r);select(hdc,old_brush)
                        select(hdc,old_pen)
                finally:end(hwnd,c.byref(ps))
            @proc_type
            def proc(hwnd,msg,wp,lp):
                nonlocal frame
                try:
                    if msg==0x000F:paint(hwnd);return 0
                    if msg==0x0014:return 1
                    if msg==0x0113:
                        frame+=1;rect=w.RECT(round(292*scale),round(285*scale),round(348*scale),round(306*scale));invalid(hwnd,c.byref(rect),False);return 0
                    if msg==0x8001:destroy(hwnd);return 0
                    if msg==0x8002:
                        kill_timer(hwnd,1);create(0,'BUTTON','닫기',0x50000001,round(270*scale),round(282*scale),round(100*scale),round(32*scale),hwnd,w.HMENU(100),instance,None);invalid(hwnd,None,False);return 0
                    if msg==0x0111 and wp&0xFFFF==100:destroy(hwnd);return 0
                    if msg==0x0010:
                        if self.failed.is_set() or self.finishing.is_set():destroy(hwnd)
                        return 0
                    if msg==0x0002:user.PostQuitMessage(0);return 0
                except Exception as exc:self.error=repr(exc)
                return default(hwnd,msg,wp,lp)
            cls=CLASS();cls.style=0x20000;cls.proc=proc;cls.instance=instance;cls.name=class_name
            registered=bool(register(c.byref(cls)))
            if not registered:raise c.WinError(c.get_last_error())
            self.hwnd=create(0x88,class_name,'Calix 시작하는 중',0x80000000,x,y,width,height,None,None,instance,None)
            if not self.hwnd:raise c.WinError(c.get_last_error())
            region=bind(gdi,'CreateRoundRectRgn',[c.c_int]*6,w.HRGN)(0,0,width+1,height+1,round(26*scale),round(26*scale))
            if region and not bind(user,'SetWindowRgn',[w.HWND,w.HRGN,w.BOOL],c.c_int)(self.hwnd,region,True):delete(region)
            set_timer(self.hwnd,1,40,None);show(self.hwnd,4);update(self.hwnd);self.painted_at=time.perf_counter();self.ready.set()
            if self.finishing.is_set():self._post(self.hwnd,0x8001,0,0)
            elif self.failed.is_set():self._post(self.hwnd,0x8002,0,0)
            message=w.MSG()
            while get_message(c.byref(message),None,0,0)>0:translate(c.byref(message));dispatch(c.byref(message))
        except Exception as exc:self.error=repr(exc)
        finally:
            if self.hwnd:kill_timer(self.hwnd,1);destroy(self.hwnd);self.hwnd=0
            if old_bitmap and memory:select(memory,old_bitmap)
            if memory:dc_delete(memory)
            for obj in (bitmap,error_font,error_brush,*brushes):
                if obj:delete(obj)
            if registered:unregister(class_name,instance)
            self.ready.set();self.closed.set()


def start_notice(argv):
    notice=StartupNotice()
    if sys.platform!='win32' or os.environ.get('QT_QPA_PLATFORM','').startswith(('offscreen','minimal')) or any(flag in argv for flag in ('--login','--browser-check','--connection-check','--smoke-test','--memory-check','--navigation-check','--help','-h')):return notice
    return notice.start()
