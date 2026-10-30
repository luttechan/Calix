"""Offline validation of the packaged login browser; no school credentials."""
from pathlib import Path
import json,tempfile,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer


def check_browser(output):
    from PySide6.QtCore import Qt,QTimer,QUrl
    from PySide6.QtWidgets import QDialog
    from PySide6.QtNetwork import QSslSocket
    from . import login
    from .login_browser import run
    state={}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Set-Cookie','calix_probe=synthetic; Path=/; HttpOnly; SameSite=Lax');self.end_headers()
            self.wfile.write(b'<form method="post" action="/finish"><input name="proof" value="synthetic"></form><script>setTimeout(()=>document.forms[0].submit(),50)</script>')
        def do_POST(self):
            size=int(self.headers.get('Content-Length','0'))
            if size>4096:self.send_error(413);return
            state['form_post']=self.rfile.read(size)==b'proof=synthetic'
            state['cookie_returned']='calix_probe=synthetic' in self.headers.get('Cookie','')
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers()
            self.wfile.write(b'<title>Calix browser check</title><p>Rendered by Chromium</p>')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    original=(login.LOGIN_URL,login.CampusLoginDialog.__init__,login.CampusLoginDialog.showEvent,login.CampusLoginDialog._page_loaded)
    def initialize(self,*args,**kwargs):
        original[1](self,*args,**kwargs);self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True)
    def shown(self,event):
        QDialog.showEvent(self,event)
        if not self._browser_started:
            self._browser_started=True;QTimer.singleShot(0,self._initialize_browser)
            QTimer.singleShot(12000,self.reject)
    def loaded(self,ok):
        if not ok or self.view.url().path()!='/finish':return
        state['regular_profile']=not self.profile.isOffTheRecord()
        state['memory_cookies']=self.profile.persistentCookiesPolicy().name=='NoPersistentCookies'
        state['profile_path']=self._profile_dir.path()
        state['qt_tls_ready']=QSslSocket.supportsSsl();state['qt_tls_backend']=QSslSocket.activeBackend()
        def inspected(title):
            state['javascript']=title=='Calix browser check'
            # Exercise the frozen DOM reader without accessing the school.
            document='''<div id="root" data-canvas_course_id="1" data-user_id="1" data-term="2026년 2학기"><div class="xn-module-builder"><div class="xnmb-module-title">1주차</div><div class="xnmb-module_item-wrapper"><i class="xnmb-module_item-icon mp4"></i><div class="xnmb-module_item-meta_data-wrapper"><a class="xnmb-module_item-left-title link" href="/courses/1/modules/items/101">Video</a><span class="xnlal-attendance-list-item-meta_data-lecture_periods-unlock_at">9월 1일 오전 00:00</span><span class="xnlal-attendance-list-item-meta_data-lecture_periods-due_at">9월 7일 오후 11:59</span></div><i class="xnmb-module_item-completed completed"></i></div></div></div>'''
            from .dom_videos import SNAPSHOT_SCRIPT,parse_screen
            from .models import Course
            self.page.setHtml(document,QUrl('https://canvas.bufs.ac.kr/courses/1/external_tools/1'))
            def collected(value):
                if self._cancelled or state.get('rendered_dom'):return
                try:
                    snapshot=json.loads(value) if isinstance(value,str) else value
                    if not isinstance(snapshot,dict) or snapshot.get('state')!='ready':return
                    rows=parse_screen(Course(1,'Course'),snapshot)
                    state['rendered_dom']=len(rows)==1 and rows.complete and rows[0].completed and rows[0].start_at=='2026-09-01T00:00:00+09:00' and rows[0].due_at=='2026-09-07T23:59:00+09:00'
                    QTimer.singleShot(0,self.reject)
                except (ValueError,TypeError):pass
            def poll():
                if self._cancelled or state.get('rendered_dom'):return
                self.page.runJavaScript(SNAPSHOT_SCRIPT,collected);QTimer.singleShot(100,poll)
            QTimer.singleShot(100,poll)
        self.page.runJavaScript('document.title',inspected)
    try:
        login.LOGIN_URL=f'http://127.0.0.1:{server.server_port}/start'
        login.CampusLoginDialog.__init__=initialize;login.CampusLoginDialog.showEvent=shown;login.CampusLoginDialog._page_loaded=loaded
        with tempfile.TemporaryDirectory(prefix='calix-browser-check-') as folder:
            run(Path(folder)/'unused.dpapi')
        state['profile_removed']=bool(state.get('profile_path')) and not Path(state['profile_path']).exists()
        state.pop('profile_path',None)
        state['passed']=all(state.get(key) for key in ('form_post','cookie_returned','regular_profile','memory_cookies','javascript','rendered_dom','profile_removed','qt_tls_ready'))
    except Exception as exc:
        state.update(passed=False,error_type=type(exc).__name__)
    finally:
        login.LOGIN_URL,login.CampusLoginDialog.__init__,login.CampusLoginDialog.showEvent,login.CampusLoginDialog._page_loaded=original
        server.shutdown();server.server_close();thread.join(2)
    Path(output).write_text(json.dumps(state,indent=2),encoding='utf-8')
    return 0 if state.get('passed') else 1
