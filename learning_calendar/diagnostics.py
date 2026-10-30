"""Offline packaging smoke test, also used by maintainers after a build."""
import json
import sys
import os
from pathlib import Path
from functools import lru_cache
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from .design import VERSION

def finish_smoke(window,output):
    result={'version':VERSION,'font_loaded':QApplication.instance().property('bufsFontId')>=0,
            'events':len(window._current_snapshot().events),
            'webengine_loaded':'PySide6.QtWebEngineCore' in sys.modules}
    from PySide6.QtGui import QRawFont
    result['font_family']=QApplication.font().family()
    result['font_has_hangul']=QRawFont.fromFont(QApplication.font()).supportsCharacter(ord('한'))
    result['qt_platform']=QApplication.platformName()
    result['configured_text_backend']=os.environ.get('QT_QPA_PLATFORM','')
    import ssl
    context=ssl.create_default_context()
    result['tls_context_ready']=context.verify_mode==ssl.CERT_REQUIRED and context.check_hostname
    result['tls_library']=ssl.OPENSSL_VERSION
    from cryptography.hazmat.backends.openssl.backend import backend
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    result['crypto_library']=backend.openssl_version_text()
    cipher=AESGCM(bytes(32));nonce=bytes([1])*12;sample=b'Calix synthetic check'
    result['crypto_roundtrip']=cipher.decrypt(nonce,cipher.encrypt(nonce,sample,b'Calix/check'),b'Calix/check')==sample
    result['app_icon_sizes']=[s.width() for s in window.windowIcon().availableSizes()]
    from .app_identity import native_identity_state
    result['native_taskbar']=native_identity_state(window)
    for page in range(4):window.select_page(page)
    window.select_page(0);window.state_select.setCurrentIndex(6);window.type_filter.setCurrentIndex(window.type_filter.findData('movie'));window.search.setText('synthetic-no-match');window.refresh()
    window.select_page(2)
    result['assignment_list_matches_snapshot']=window.assignment_list.event_model.rowCount()==sum(e.kind=='assignment' for e in window._current_snapshot().events)
    window.select_page(1)
    result['movie_list_matches_snapshot']=window.video_list.event_model.rowCount()==sum(e.kind=='movie' for e in window._current_snapshot().events)
    window.select_page(0)
    result['calendar_filters_isolated']=window.search.text()=='synthetic-no-match' and window.state_select.currentIndex()==6 and window.type_filter.currentData()=='movie'
    from .special_dates_dialog import SpecialDatesDialog
    special=SpecialDatesDialog(window.holiday_calendar,window);special.changed.connect(window.refresh);special.mystery.setChecked(True)
    from datetime import date
    window.select_page(0);window.select_day(date(2026,6,27));window.main_stack._settle();window.calendar._layout_badges()
    result['special_birthday_available']=window.day_feast.text()=='클로네 생일' and window.holiday_calendar.special_dates(2027).get(date(2027,6,27))=='클로네 생일'
    result['special_options_labels']=special.catholic.text()=='가톨릭 일정' and special.mystery.text()=='???'
    special.close();special.deleteLater()
    from datetime import date
    from .models import Course,Event
    from .snapshot import Snapshot
    rows=[Event('overlay1',1,'검사','movie','영상 1','2026-11-29T14:59:59Z',False),Event('overlay2',1,'검사','movie','영상 2','2026-11-29T14:59:59Z',False)]
    window.demo_snapshot=Snapshot(rows,[Course(1,'검사')]);window._reload_course_filter();window.reset_filters();window.select_day(date(2026,11,29));window.main_stack._settle();window.calendar._layout_badges()
    badge=next(b for b in window.calendar.badges if b.property('calendarDate')=='2026-11-29')
    native_index=window.calendar.view.indexAt(badge.geometry().center())
    result['calendar_nov29_overlay_matches']=badge.isVisible() and badge.movie.isVisible() and '영상 2건' in badge.accessibleName() and window.calendar.view.model().data(native_index)==29 and native_index.row()==6
    visible=[child for child in badge.children() if hasattr(child,'isVisible') and child.isVisible()]
    result['compact_calendar_chips']=8<=badge.height()<=24 and all(badge.rect().contains(child.geometry()) for child in visible) and all(a.geometry().right()<b.geometry().left() for a,b in zip(visible,visible[1:]))
    result['calendar_full_width_default']=not window.day_panel.isVisible()
    from .design import glass_enabled
    result['glass_enabled']=glass_enabled()
    field=window.centralWidget()._field
    result['glass_background_bytes']=field.sizeInBytes() if field is not None else 0
    window.show_home();window.main_stack._settle()
    result['home_available']=window.home.hero is not None
    result['timetable_available']=window._timetable_built
    from .credits import CreditsDialog
    credits=CreditsDialog(window);result['credits_available']=True;credits.close();credits.deleteLater()
    window.show_diary();window.main_stack._settle();window.diary.new_entry();window.diary.body.setPlainText('packaged synthetic diary');window.diary.flush()
    result['diary_available']=bool(window.diary.normal.summaries())
    from .diary_crypto import new_material,unlock_material,wipe
    key,header=new_material('packaged-synthetic-passphrase');again=unlock_material(header,'packaged-synthetic-passphrase')
    result['vault_crypto_ready']=key==again;wipe(key);wipe(again)
    # Import the login module only after recording the normal startup state.
    from . import login_browser
    from PySide6.QtWebEngineWidgets import QWebEngineView
    result['login_available']=QWebEngineView is not None
    Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    window.dispose()


def check_connection(output):
    """Anonymous HTTPS probe; never reads, saves, or sends account cookies."""
    import requests
    result={}
    try:
        with requests.Session() as session:
            response=session.get('https://canvas.bufs.ac.kr/api/v1/users/self/profile',
                                 timeout=(5,12),allow_redirects=False)
        result={'tls_ready':True,'http_status':response.status_code}
    except Exception as exc:
        result={'tls_ready':False,'error_type':type(exc).__name__}
    Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    return 0 if result['tls_ready'] else 1


from PySide6.QtCore import QObject,QEvent

@lru_cache(maxsize=1)
def _memory_api():
    import ctypes as c
    from ctypes import wintypes as w
    class COUNTERS(c.Structure):
        _fields_=[('cb',w.DWORD),('PageFaultCount',w.DWORD)]+[(name,c.c_size_t) for name in
            ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
             'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage')]
    kernel=c.WinDLL('kernel32');kernel.GetCurrentProcess.restype=w.HANDLE
    psapi=c.WinDLL('psapi');psapi.GetProcessMemoryInfo.argtypes=[w.HANDLE,c.POINTER(COUNTERS),w.DWORD]
    # ctypes caches POINTER(Structure) types. Recreating the class on every
    # sample permanently retains a new type and its metadata in that cache.
    return COUNTERS,psapi.GetProcessMemoryInfo,kernel.GetCurrentProcess()


def memory_usage():
    if sys.platform!='win32':return {}
    import ctypes as c
    counters_type,read,process=_memory_api();counters=counters_type();counters.cb=c.sizeof(counters)
    if not read(process,c.byref(counters),counters.cb):return {}
    return {'working_set_mb':round(counters.WorkingSetSize/1048576,2),'peak_working_set_mb':round(counters.PeakWorkingSetSize/1048576,2),
            'private_commit_mb':round(counters.PrivateUsage/1048576,2)}


def process_age_ms():
    if sys.platform!='win32':return None
    import ctypes as c,time
    from ctypes import wintypes as w
    kernel=c.WinDLL('kernel32',use_last_error=True);kernel.GetCurrentProcess.restype=w.HANDLE
    kernel.GetProcessTimes.argtypes=[w.HANDLE]+[c.POINTER(w.FILETIME)]*4
    kernel.GetProcessTimes.restype=w.BOOL
    times=[w.FILETIME() for _ in range(4)]
    if not kernel.GetProcessTimes(kernel.GetCurrentProcess(),*[c.byref(value) for value in times]):return None
    created=((times[0].dwHighDateTime<<32)|times[0].dwLowDateTime)/10_000_000-11644473600
    return round(max(0,(time.time()-created)*1000),2)


class StartupProbe(QObject):
    def __init__(self,window,output,started,notice=None):
        super().__init__(window);self.window=window;self.output=output;self.started=started;self.recorded=False;self.notice=notice;self.image_at_first_paint=None
        window.installEventFilter(self)
    def eventFilter(self,obj,event):
        if obj is self.window and event.type()==QEvent.Type.Paint and not self.recorded:
            if self.notice:self.image_at_first_paint=self.notice.native_state()
            self.recorded=True;QTimer.singleShot(0,self.finish)
        return False
    def finish(self):
        import time
        from .app_identity import native_identity_state
        result={'version':VERSION,'first_frame_process_ms':round((time.perf_counter()-self.started)*1000,1),
                'memory':memory_usage(),'native_taskbar':native_identity_state(self.window),
                'webengine_loaded':'PySide6.QtWebEngineCore' in sys.modules}
        result['snapshot_events']=len(self.window.snapshot.events);result['home_ready']=self.window.main_stack.currentIndex()==0 and self.window.home.remaining_table.event_model.rowCount()==len(self.window.snapshot.pending())
        result['calendar_deferred']=getattr(self.window,'_calendar',None) is None
        if self.notice:
            result['startup_image']=self.notice.native_state()
            result['startup_image_at_first_paint']=self.image_at_first_paint
            result['startup_image_process_ms']=round((self.notice.painted_at-self.started)*1000,1) if self.notice.painted_at is not None else None
        Path(self.output).write_text(json.dumps(result,indent=2),encoding='utf-8');self.window.dispose()
