"""Real Chromium cookie round trip through an SSO-like local form POST."""
import subprocess
import sys
from pathlib import Path
import PySide6

def test_regular_profile_keeps_cookies_through_post_and_cleans_up(tmp_path):
    root=Path(__file__).parents[1];deps=Path(PySide6.__file__).parents[1]
    script=r'''
import sys,threading,tempfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,DEPS);sys.path.insert(0,ROOT)
from learning_calendar.bootstrap import configure_runtime
configure_runtime()
from PySide6.QtCore import QCoreApplication,Qt,QTimer
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
from learning_calendar import login
from learning_calendar.login_browser import run
state={}
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Set-Cookie','sso_seed=synthetic; Path=/; HttpOnly; SameSite=Lax');self.end_headers()
        self.wfile.write(b'<form method="post" action="/finish"><input name="proof" value="synthetic"></form><script>setTimeout(()=>document.forms[0].submit(),50)</script>')
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length',0)))
        state['cookie_returned']='sso_seed=synthetic' in self.headers.get('Cookie','')
        self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(b'<title>SSO test finished</title>')
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
login.LOGIN_URL=f'http://127.0.0.1:{server.server_port}/start'
def loaded(self,ok):
    if ok and self.view.url().path()=='/finish':
        state['regular_profile']=not self.profile.isOffTheRecord()
        state['cookie_policy']=self.profile.persistentCookiesPolicy().name
        state['temp_profile']=self._profile_dir.path()
        QTimer.singleShot(100,self.reject)
login.CampusLoginDialog._page_loaded=loaded
real_show=login.CampusLoginDialog.showEvent
def show(self,event):
    real_show(self,event);QTimer.singleShot(12000,self.reject)
login.CampusLoginDialog.showEvent=show
try:
    result=run(OUTPUT)
    assert result==2 and not Path(OUTPUT).exists()
    assert state.get('regular_profile') and state.get('cookie_policy')=='NoPersistentCookies',state
    assert state.get('cookie_returned'),state
    assert not Path(state['temp_profile']).exists(),'Temporary browser profile was not cleaned'
finally:server.shutdown()
'''
    script=script.replace('DEPS',repr(str(deps))).replace('ROOT',repr(str(root))).replace('OUTPUT',repr(str(tmp_path/'unused.dpapi')))
    completed=subprocess.run([sys.executable,'-B','-c',script],capture_output=True,text=True,timeout=25)
    assert completed.returncode==0,completed.stdout+completed.stderr
