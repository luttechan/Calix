"""Foreground login shell, validated cookie capture, and LearningX bootstrap."""
from __future__ import annotations
import base64
import json
import logging
import time
from pathlib import Path
from urllib.parse import urlparse,urljoin
from PySide6.QtCore import Qt,QUrl,QTimer,QThread,Signal,Slot,QTemporaryDir,QDir
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QMessageBox,QWidget,QApplication
from .cookies import cookie_record,read_cookies,canvas_session_available,applies_to_canvas,campus_domain

COOKIE_PROBE=b'_bufs_cookie_probe'
LOGIN_URL='https://canvas.bufs.ac.kr/login'

def learningx_entry(tabs):
    for tab in tabs if isinstance(tabs,list) else ():
        if not isinstance(tab,dict) or tab.get('hidden'):continue
        label=str(tab.get('label','')).casefold()
        if not any(word in label for word in ('주차학습','강의콘텐츠','학습콘텐츠','learningx')):continue
        url=urljoin('https://canvas.bufs.ac.kr/',str(tab.get('html_url','')));parsed=urlparse(url)
        if parsed.scheme=='https' and parsed.hostname=='canvas.bufs.ac.kr' and ('/external_tools/' in parsed.path or parsed.path.startswith('/learningx/')):return url
    return None

def allow_login_storage(request):
    # Share necessary storage across the university's SSO domains only.
    origin=request.origin.host().lower();first=request.firstPartyUrl.host().lower()
    if campus_domain(origin) and (not first or campus_domain(first)):return True
    return not request.thirdParty

def has_cookie_warning(text,url=''):
    return ('needs_cookies=1' in url or 'Cookies Required' in text or
            '쿠키 필요' in text or '보안 기본 설정을 조정' in text)

class LoginValidation(QThread):
    checked=Signal(object)
    failed=Signal(str)
    def __init__(self,rows,parent=None):
        super().__init__(parent);self.rows=rows
    def run(self):
        from .sync import CampusClient,AuthenticationRequired
        client=CampusClient(self.rows)
        try:
            identity=client._get('/api/v1/users/self/profile').json()
            if not isinstance(identity,dict) or not identity.get('id'):raise ValueError('학교 계정을 확인하지 못했습니다.')
            cid=None;course_ids=[]
            try:
                courses=client._get('/api/v1/dashboard/dashboard_cards').json()
                if isinstance(courses,list):course_ids=[int(c['id']) for c in courses if isinstance(c,dict) and c.get('id')]
                cid=next(iter(course_ids),None)
            except Exception:pass
            token_valid=False
            if client._learningx_token:
                for candidate in course_ids[:3]:
                    try:client._get(f'/learningx/api/v1/courses/{candidate}/modules');cid=candidate;token_valid=True;break
                    except Exception:continue
            entry=None
            if cid and not token_valid:
                for candidate in course_ids[:4]:
                    try:entry=learningx_entry(client._get(f'/api/v1/courses/{candidate}/tabs').json())
                    except Exception:continue
                    if entry:cid=candidate;break
            self.checked.emit({'course_id':cid,'token_valid':token_valid,'learningx_url':entry})
        except AuthenticationRequired:
            self.failed.emit('로그인이 만료됐습니다. 학교 화면에서 다시 로그인해 주세요.')
        except Exception as exc:
            # A missing TLS file, an offline connection, or a malformed response
            # says nothing about the validity of the user's browser session.
            logging.exception('로그인 확인 실패 (%s)',type(exc).__name__)
            self.failed.emit('연결을 확인하지 못했습니다. 잠시 후 다시 완료를 눌러주세요.')
        finally:client.session.close();self.rows=[]

class CampusLoginDialog(QDialog):
    session_ready=Signal(object)
    session_changed=Signal(object)
    dismissed=Signal()
    logged_out=Signal()
    def __init__(self,existing=None,ready_file=None,parent=None,resident=False):
        super().__init__(parent)
        self.setWindowTitle('Calix 로그인');self.resize(1040,760)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,True)
        self.existing=existing;self.ready_file=ready_file;self.rows={};self.session_rows=[]
        self.resident=resident;self.authenticated=False;self._shutting_down=False;self._logout_pending=False
        self._auto_validation_pending=False;self._token_check_pending=False;self._bootstrap_active=False
        self.view=None;self.page=None;self.profile=None;self._validator=None;self._profile_dir=None
        self._cancelled=False;self._pending_accept=False;self._validated=False;self._finish_after_validation=False;self._last_cookie=time.monotonic()
        self._routed=set();self._student_id='';self._password='';self._browser_started=False
        self._cookie_storage_ready=False;self._warning_recovered=False;self._recover_after_validation=False;self._restarting=False;self._page_generation=0
        self.message=QLabel('로그인 창을 준비하고 있어요…');self.message.setObjectName('section');self.message.setWordWrap(True)
        self.browser_host=QWidget();self.browser_layout=QVBoxLayout(self.browser_host);self.browser_layout.setContentsMargins(0,0,0,0)
        loading=QLabel('학교 로그인');loading.setAlignment(Qt.AlignmentFlag.AlignCenter);loading.setObjectName('muted');self.loading=loading;self.browser_layout.addWidget(loading)
        self.fill_btn=QPushButton('저장된 계정 입력');self.fill_btn.setEnabled(False);self.fill_btn.clicked.connect(self.fill_form)
        self.retry_btn=QPushButton('새로고침');self.retry_btn.setEnabled(False);self.retry_btn.clicked.connect(self._restart_login)
        self.done_btn=QPushButton('로그인 완료');self.done_btn.setObjectName('primary');self.done_btn.setEnabled(False);self.done_btn.clicked.connect(self.accept_after_cookie_capture)
        cancel=QPushButton('닫기' if resident else '취소');cancel.clicked.connect(self.reject)
        row=QHBoxLayout();row.addWidget(self.fill_btn);row.addWidget(self.retry_btn);row.addStretch();row.addWidget(cancel);row.addWidget(self.done_btn)
        layout=QVBoxLayout(self);layout.setContentsMargins(20,18,20,18);layout.setSpacing(14)
        layout.addWidget(self.message);layout.addWidget(self.browser_host,1);layout.addLayout(row)
        self.capture_timer=QTimer(self);self.capture_timer.setInterval(100);self.capture_timer.timeout.connect(self._capture_ready)
        self.bootstrap_timer=QTimer(self);self.bootstrap_timer.setInterval(200);self.bootstrap_timer.timeout.connect(self._bootstrap_tick)
        self.snapshot_timer=QTimer(self);self.snapshot_timer.setSingleShot(True);self.snapshot_timer.setInterval(400);self.snapshot_timer.timeout.connect(self._publish_snapshot)

    def showEvent(self,event):
        super().showEvent(event);self.raise_();self.activateWindow()
        from .app_identity import apply_window_identity
        apply_window_identity(self)
        if self.ready_file:
            try:Path(self.ready_file).write_text('ready',encoding='ascii')
            except OSError:pass
        if not self._browser_started:
            self._browser_started=True;QTimer.singleShot(30,self._initialize_browser)
            QTimer.singleShot(150,self._bring_forward)

    def _bring_forward(self):
        if not self.isVisible():return
        self.raise_();self.activateWindow()
        if __import__('sys').platform=='win32':
            import ctypes
            ctypes.windll.user32.SetForegroundWindow(int(self.winId()))

    def _initialize_browser(self):
        if self._cancelled:return
        try:
            from PySide6.QtWebEngineCore import QWebEngineProfile,QWebEnginePage,QWebEngineUrlRequestInterceptor,QWebEngineSettings
            from PySide6.QtWebEngineWidgets import QWebEngineView
            from PySide6.QtNetwork import QNetworkCookie
            class TokenInterceptor(QWebEngineUrlRequestInterceptor):
                captured=Signal(str)
                def interceptRequest(self,info):
                    url=info.requestUrl()
                    if url.scheme()!='https' or url.host()!='canvas.bufs.ac.kr' or not url.path().startswith('/learningx/'):return
                    for key,value in info.httpHeaders().items():
                        if bytes(key).lower()==b'authorization':
                            header=bytes(value).decode('latin1')
                            if header.lower().startswith('bearer '):self.captured.emit(header[7:].strip())
            # Canvas SSO must use a regular browser context, not Chromium's
            # private/off-the-record cookie and storage policies.
            self._profile_dir=QTemporaryDir(QDir.tempPath()+'/Calix-login-XXXXXX')
            if not self._profile_dir.isValid():raise RuntimeError('로그인 임시 저장소 생성 실패')
            self.profile=QWebEngineProfile('Calix-campus-login',self)
            self.profile.setPersistentStoragePath(self._profile_dir.path()+'/storage')
            self.profile.setCachePath(self._profile_dir.path()+'/cache')
            self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
            self.profile.setHttpCacheMaximumSize(16*1024*1024)
            self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
            self.profile.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled,True)
            self.profile.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled,True)
            self.interceptor=TokenInterceptor(self.profile);self.interceptor.captured.connect(self._capture_token)
            self.profile.setUrlRequestInterceptor(self.interceptor)
            self.cookie_store=self.profile.cookieStore()
            self.cookie_store.setCookieFilter(allow_login_storage)
            self.cookie_store.cookieAdded.connect(self._cookie_added);self.cookie_store.cookieRemoved.connect(self._cookie_removed)
            self.view=QWebEngineView(self.browser_host);self.page=QWebEnginePage(self.profile,self.view);self.view.setPage(self.page)
            self.browser_layout.removeWidget(self.loading);self.loading.deleteLater();self.browser_layout.addWidget(self.view)
            self.view.loadFinished.connect(self._page_loaded)
            self.page.newWindowRequested.connect(self._open_login_window)
            # Only explicitly supplied sessions are reused. A normal login starts
            # clean and never reinjects an old CSRF token into a new SSO exchange.
            if self.existing:
                for rec in read_cookies(self.existing):
                    if rec['name']=='_csrf_token':continue
                    self.rows[self._key(rec)]=rec
                    for cookie in QNetworkCookie.parseCookies(base64.b64decode(rec['raw'])):
                        origin=QUrl('https://'+rec['domain'].lstrip('.')+'/')
                        if not rec['domain'].startswith('.'):cookie.setDomain('')
                        self.cookie_store.setCookie(cookie,origin)
            self.message.setText('로그인 쿠키를 준비하고 있어요…')
            probe=QNetworkCookie(COOKIE_PROBE,b'1');probe.setPath('/');probe.setSecure(True);probe.setHttpOnly(True)
            self.cookie_store.setCookie(probe,QUrl('https://canvas.bufs.ac.kr/'))
            QTimer.singleShot(5000,self._cookie_storage_timeout)
        except Exception as exc:
            self.message.setText('로그인 창을 열지 못했습니다. 앱을 다시 실행해 주세요.')
            __import__('logging').exception('로그인 브라우저 초기화 실패')

    @staticmethod
    def _key(rec):return (rec['domain'].lstrip('.').lower(),rec['name'],rec['path'])

    def _cookie_added(self,cookie):
        if bytes(cookie.name())==COOKIE_PROBE:
            self._cookie_storage_ready=True
            self.cookie_store.deleteCookie(cookie,QUrl('https://canvas.bufs.ac.kr/'))
            return
        rec=cookie_record(cookie)
        if rec:
            self.rows[self._key(rec)]=rec;self._last_cookie=time.monotonic()
            if self.authenticated:self.snapshot_timer.start()

    def _cookie_removed(self,cookie):
        if bytes(cookie.name())==COOKIE_PROBE:
            if self._cookie_storage_ready:QTimer.singleShot(0,self._navigate_login_entry)
            return
        name=bytes(cookie.name()).decode('utf-8','replace')
        self.rows.pop((cookie.domain().lstrip('.').lower(),name,cookie.path() or '/'),None)
        self._last_cookie=time.monotonic()
        if self.authenticated:self.snapshot_timer.start()

    def _navigate_login_entry(self):
        if self._cancelled or not self.view:return
        self.message.setText('학교 로그인 후 완료를 눌러주세요.')
        self.done_btn.setEnabled(True);self.fill_btn.setEnabled(True);self.retry_btn.setEnabled(True)
        self.view.setUrl(QUrl('https://canvas.bufs.ac.kr/' if self.existing and canvas_session_available(self.rows.values()) else LOGIN_URL))

    def _cookie_storage_timeout(self):
        if self._cancelled or self._cookie_storage_ready:return
        self.message.setText('쿠키 저장소를 준비하지 못했습니다. 새로고침을 눌러주세요.')
        self.retry_btn.setEnabled(True)

    def _open_login_window(self,request):
        url=request.requestedUrl()
        if url.scheme()=='https' and campus_domain(url.host()):request.openIn(self.page)

    def _restart_login(self,checked=False):
        if not self.view or self._validator or self._restarting:return
        self._restarting=True;self._validated=False;self._pending_accept=False
        self.authenticated=False;self._bootstrap_active=False;self._routed.clear()
        self.bootstrap_timer.stop();self.capture_timer.stop();self.rows.clear()
        self.done_btn.setText('로그인 완료');self.done_btn.setEnabled(False)
        self.retry_btn.setEnabled(False);self.message.setText('새 로그인 세션을 준비하고 있어요…')
        self._last_cookie=time.monotonic();self._reset_deadline=time.monotonic()+2
        self.cookie_store.deleteAllCookies()
        self._wait_for_cookie_reset()

    def _wait_for_cookie_reset(self):
        if self._cancelled or not self._restarting:return
        if time.monotonic()-self._last_cookie<.15 and time.monotonic()<self._reset_deadline:
            QTimer.singleShot(80,self._wait_for_cookie_reset);return
        self.rows.clear();self._restarting=False;self._navigate_login_entry()

    @Slot(str)
    def _capture_token(self,token):
        if not token:return
        from PySide6.QtNetwork import QNetworkCookie
        cookie=QNetworkCookie(b'xn_api_token',token.encode('utf-8'));cookie.setDomain('canvas.bufs.ac.kr')
        cookie.setPath('/');cookie.setSecure(True);cookie.setHttpOnly(True)
        self._cookie_added(cookie)
        if self._pending_accept and self._validated and not self._token_check_pending:
            self._token_check_pending=True;QTimer.singleShot(180,self._check_movie_token)

    def _check_movie_token(self):
        self._token_check_pending=False
        if self._pending_accept and self._validated and not self._validator:self.accept_after_cookie_capture()

    def _has_token(self):
        return any(r['name']=='xn_api_token' and r['value'] and applies_to_canvas(r['domain']) for r in self.rows.values())

    def accept_after_cookie_capture(self):
        if self.authenticated:
            self.hide();return
        if self.view is None or self._validator or self.capture_timer.isActive():return
        self.done_btn.setEnabled(False);self.message.setText('로그인 상태를 확인하고 있어요…')
        self._capture_deadline=time.monotonic()+3;self._last_cookie=time.monotonic()
        self.cookie_store.loadAllCookies();self.capture_timer.start()

    def _capture_ready(self):
        now=time.monotonic();available=canvas_session_available(self.rows.values())
        if available and now-self._last_cookie>=.18:
            self.capture_timer.stop();task=LoginValidation(list(self.rows.values()),self);self._validator=task
            task.checked.connect(self._checked);task.failed.connect(self._validation_failed);task.finished.connect(self._validation_finished);task.start()
        elif now>=self._capture_deadline:
            self.capture_timer.stop();self._validation_failed('학교 로그인 후 다시 완료를 눌러주세요.')

    @Slot(object)
    def _checked(self,result):
        if self._cancelled or self._logout_pending:return
        self._validated=True;self._pending_accept=True
        if result['token_valid']:self._bootstrap_active=False;self._finish_after_validation=True;self._complete();return
        for key in list(self.rows):
            if key[1]=='xn_api_token':self.rows.pop(key,None)
        cid=result.get('course_id')
        if not cid:self._finish_after_validation=True;self._complete();return
        self.message.setText('주차학습을 자동으로 연결하고 있어요…')
        self.done_btn.setText('연결 중');self.done_btn.setEnabled(False)
        if not self._bootstrap_active:
            self._bootstrap_active=True;self._bootstrap_deadline=time.monotonic()+30;self._link_check_at=0.
            self.bootstrap_timer.start()
            self.view.setUrl(QUrl(result.get('learningx_url') or f'https://canvas.bufs.ac.kr/courses/{int(cid)}'))

    def _page_loaded(self,ok):
        if not self.page or self._cancelled:return
        self._page_generation+=1;generation=self._page_generation
        url=self.view.url().toString()
        if self.view.url().host()=='canvas.bufs.ac.kr' and not self._warning_recovered:
            def inspect(text):
                if self._cancelled or generation!=self._page_generation:return
                if has_cookie_warning(str(text or ''),url):
                    logging.warning('Canvas cookie warning: regular_profile=%s, storage_ready=%s, canvas_session_present=%s, csrf_present=%s',
                        not self.profile.isOffTheRecord() if self.profile else None,
                        self._cookie_storage_ready,canvas_session_available(self.rows.values()),
                        any(row.get('name')=='_csrf_token' for row in self.rows.values()))
                    self._warning_recovered=True
                    if self._validator:self._recover_after_validation=True
                    else:self._restart_login()
            self.page.runJavaScript("document.body ? document.body.innerText : ''",inspect)
        if self._pending_accept and self._validated:
            QTimer.singleShot(80,self._find_learningx_link)
        elif not self.authenticated and not self._auto_validation_pending and ok and self.view.url().host()=='canvas.bufs.ac.kr' and not self.view.url().path().startswith(('/login','/logout','/learningx/login')) and canvas_session_available(self.rows.values()):
            self._auto_validation_pending=True;QTimer.singleShot(250,self._auto_validate)

    def _auto_validate(self):
        self._auto_validation_pending=False
        if not self._cancelled and not self._logout_pending and not self.authenticated and not self._validator and not self._pending_accept:self.accept_after_cookie_capture()

    def _find_learningx_link(self):
        if not self._pending_accept or not self.page:return
        script='''(()=>{const links=[...document.querySelectorAll('a[href]')];return links.filter(a=>/주차학습|강의콘텐츠|학습콘텐츠|LearningX/i.test(a.textContent)).map(a=>a.href).concat([...document.querySelectorAll('iframe[src]')].map(f=>f.src));})()'''
        def follow(links):
            if not self._pending_accept or not isinstance(links,list):return
            for link in links:
                parsed=urlparse(str(link))
                if parsed.scheme=='https' and parsed.hostname=='canvas.bufs.ac.kr' and ('/external_tools/' in parsed.path or parsed.path.startswith('/learningx/')) and link not in self._routed:
                    self._routed.add(link);self.view.setUrl(QUrl(link));break
        self.page.runJavaScript(script,follow)

    def _bootstrap_tick(self):
        now=time.monotonic()
        if now>=self._bootstrap_deadline:
            self._finish_after_validation=True;self._bootstrap_active=False;self._complete();return
        if self._has_token() and not self._validator:self._check_movie_token()
        elif now>=self._link_check_at:
            self._link_check_at=now+.5;self._find_learningx_link()

    @Slot(str)
    def _validation_failed(self,message):
        if self._cancelled or self._logout_pending:return
        self.message.setText(message);self.done_btn.setEnabled(True)
        self._pending_accept=False;self._validated=False;self._bootstrap_active=False;self.bootstrap_timer.stop()
        if self.resident:
            if '만료' in message:self._recover_after_validation=True
            self.show();self._bring_forward()

    def _validation_finished(self):
        task=self._validator;self._validator=None
        if task:task.deleteLater()
        if self._logout_pending:self._finish_logout()
        elif self._cancelled:super().reject()
        elif self._recover_after_validation:
            self._recover_after_validation=False;self._restart_login()
        elif self._pending_accept and self._validated and self._finish_after_validation:self._complete()

    def _complete(self):
        if not self._validated or self._cancelled:return
        if self._validator and self._validator.isRunning():return
        self.capture_timer.stop();self.bootstrap_timer.stop()
        self.session_rows=list(self.rows.values());self._pending_accept=False
        if self.resident:
            self.authenticated=True;self._bootstrap_active=False;self.message.setText('로그인 상태를 유지하고 있어요.')
            self.done_btn.setText('닫기');self.done_btn.setEnabled(True);self.hide();self.session_ready.emit(self.session_rows)
        else:super().accept()

    def _publish_snapshot(self):
        if self.authenticated and not self._logout_pending:self.session_changed.emit(list(self.rows.values()))

    def request_authentication(self):
        self._cancelled=False;self._finish_after_validation=False
        if self.authenticated:self.authenticated=False;self._validated=False;self._pending_accept=False
        if self.view and canvas_session_available(self.rows.values()):self.accept_after_cookie_capture()
        else:self.show();self._bring_forward()

    def request_logout(self):
        self._logout_pending=True;self.authenticated=False;self.snapshot_timer.stop()
        self.capture_timer.stop();self.bootstrap_timer.stop();self._pending_accept=False;self._validated=False
        if self._validator:return
        self._finish_logout()

    def _finish_logout(self):
        self.session_rows=[];self._finish_after_validation=False
        if self.page and self.view and self.view.url().host()=='canvas.bufs.ac.kr':
            # Canvas documents DELETE /logout. Finish locally even when offline.
            script="""(()=>{try{localStorage.clear();sessionStorage.clear();}catch(e){}let c=document.cookie.split('; ').find(x=>x.startsWith('_csrf_token='));let token=c?decodeURIComponent(c.slice(12)):'';fetch('/logout',{method:'DELETE',credentials:'same-origin',headers:{'X-CSRF-Token':token}}).catch(()=>{}).finally(()=>window.__bufsLogoutFinished=true);})()"""
            self.page.runJavaScript(script)
            QTimer.singleShot(1200,self._clear_logout_storage)
        else:self._clear_logout_storage()

    def _clear_logout_storage(self):
        if self._shutting_down:return
        self._logout_pending=False;self.rows.clear()
        if self.profile:self.profile.clearHttpCache()
        self.existing=None;self._routed.clear();self._bootstrap_active=False;self._cancelled=False
        if self.view and getattr(self,'cookie_store',None):self._restart_login()
        else:self.message.setText('로그아웃했습니다.')
        self.hide();self.logged_out.emit()

    def fill_form(self):
        if self.view is None:return
        location=urlparse(self.view.url().toString())
        if location.scheme!='https' or location.hostname not in {'canvas.bufs.ac.kr','eclass.bufs.ac.kr'}:return
        from .preferences import read_account,read_password
        try:self._student_id=read_account();self._password=read_password(self._student_id) if self._student_id else ''
        except Exception:self._student_id=self._password=''
        if not self._student_id or not self._password:
            self.message.setText('계정을 직접 입력하거나 설정에서 저장해주세요.');return
        code='''(()=>{const u=%s,p=%s;const fields=[...document.querySelectorAll('input')];const write=(el,v)=>{if(!el)return false;Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));return true;};return [write(fields.find(x=>x.type==='text'||x.type==='email'),u),write(fields.find(x=>x.type==='password'),p)];})()'''%(json.dumps(self._student_id),json.dumps(self._password))
        self.page.runJavaScript(code);self._password=''

    def reject(self):
        if self.resident and not self._shutting_down:
            self.hide();self.dismissed.emit();return
        self._cancelled=True;self.capture_timer.stop();self.bootstrap_timer.stop()
        if self._validator and self._validator.isRunning():self.hide();return
        super().reject()

    def dispose(self):
        from .app_identity import clear_window_identity
        clear_window_identity(self)
        self.capture_timer.stop();self.bootstrap_timer.stop();self._password='';self._student_id=''
        self.snapshot_timer.stop()
        if self.view:self.view.stop();self.view.deleteLater();self.view=None
        self.page=None
