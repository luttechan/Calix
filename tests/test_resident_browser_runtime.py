"""Actual Chromium context survives authentication, hide/show and logout."""
import json,os,subprocess,sys,time,uuid
from pathlib import Path
import PySide6
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalServer

def test_resident_chromium_keeps_profile_and_exits_cleanly(tmp_path):
    app=QApplication.instance() or QApplication([]);server=QLocalServer();name='bufs-test-'+uuid.uuid4().hex
    assert server.listen(name)
    output=tmp_path/'session.dpapi';state=tmp_path/'state.json';root=Path(__file__).parents[1];deps=Path(PySide6.__file__).parents[1]
    script=r'''
import sys,json,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,DEPS_PATH);sys.path.insert(0,ROOT_PATH)
from PySide6.QtCore import QTimer,QUrl
from PySide6.QtNetwork import QNetworkCookie
from learning_calendar import login,login_browser
from learning_calendar.cookies import cookie_record
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(b'<title>Synthetic SSO</title><p>Local test</p>')
    def do_DELETE(self):
        state['logout_request']=True;Path(STATE_PATH).write_text(json.dumps(state))
        self.send_response(200);self.end_headers()
http=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
login.LOGIN_URL=f'http://127.0.0.1:{http.server_port}/start'
state={'shows':0};old_show=login.CampusLoginDialog.showEvent
def show(self,event):
    old_show(self,event);state['shows']+=1
    if self.profile:state['profile_id']=id(self.profile)
    Path(STATE_PATH).write_text(json.dumps(state))
def loaded(self,ok):
    if not ok or state.get('authenticated'):return
    state['authenticated']=True;state['profile_id']=id(self.profile);state['profile_dir']=self._profile_dir.path()
    cookie=QNetworkCookie(b'_normandy_session',b'synthetic');cookie.setDomain('canvas.bufs.ac.kr');cookie.setPath('/');cookie.setSecure(True)
    row=cookie_record(cookie);self.rows[self._key(row)]=row;self.cookie_store.setCookie(cookie,QUrl('https://canvas.bufs.ac.kr/'))
    self.page.runJavaScript("localStorage.setItem('synthetic-login','present')")
    self.view.url=lambda:QUrl('https://canvas.bufs.ac.kr/')
    self._validated=True;self._pending_accept=True;self._finish_after_validation=True
    Path(STATE_PATH).write_text(json.dumps(state));QTimer.singleShot(100,self._complete)
old_clear=login.CampusLoginDialog._clear_logout_storage
def clear(self):
    def inspected(value):
        state['storage_cleared']=value;Path(STATE_PATH).write_text(json.dumps(state));old_clear(self)
    self.page.runJavaScript("localStorage.getItem('synthetic-login')===null",inspected)
login.CampusLoginDialog._clear_logout_storage=clear
login.CampusLoginDialog.showEvent=show;login.CampusLoginDialog._page_loaded=loaded
try:raise SystemExit(login_browser.run(OUTPUT_PATH,control_server=SERVER_NAME))
finally:http.shutdown()
'''
    for key,value in {'DEPS_PATH':str(deps),'ROOT_PATH':str(root),'STATE_PATH':str(state),'OUTPUT_PATH':str(output),'SERVER_NAME':name}.items():script=script.replace(key,repr(value))
    child=subprocess.Popen([sys.executable,'-B','-c',script],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    socket=None;events=[];buffer=bytearray()
    def pump_until(predicate,timeout=20):
        nonlocal socket,buffer
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline and child.poll() is None:
            app.processEvents()
            if socket is None and server.hasPendingConnections():socket=server.nextPendingConnection()
            if socket:
                buffer.extend(bytes(socket.readAll()))
                while b'\n' in buffer:
                    line,_,tail=buffer.partition(b'\n');buffer=bytearray(tail);events.append(json.loads(line))
            if predicate():return
            time.sleep(.01)
        assert predicate(),(events,child.poll())
    def command(value):socket.write((json.dumps({'command':value})+'\n').encode());socket.flush()
    try:
        pump_until(lambda:any(e['event']=='authenticated' for e in events))
        assert output.is_file();initial=json.loads(state.read_text());profile_id=initial['profile_id'];pid=child.pid
        command('show');pump_until(lambda:json.loads(state.read_text()).get('shows',0)>=2)
        assert json.loads(state.read_text())['profile_id']==profile_id and child.pid==pid
        command('logout');pump_until(lambda:any(e['event']=='logged_out' for e in events))
        assert not output.exists() and child.poll() is None
        logged_out=json.loads(state.read_text());assert logged_out.get('logout_request') and logged_out.get('storage_cleared')
        command('show');pump_until(lambda:json.loads(state.read_text()).get('shows',0)>=3)
        assert json.loads(state.read_text())['profile_id']==profile_id
        command('quit')
        deadline=time.monotonic()+15
        while child.poll() is None and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
        assert child.poll()==0,child.communicate(timeout=1)
        assert not Path(initial['profile_dir']).exists()
    finally:
        if child.poll() is None:child.kill();child.wait()
        if socket:socket.abort();socket.deleteLater()
        server.close();server.deleteLater();app.processEvents()
