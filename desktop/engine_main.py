"""User-scoped stdio sidecar. HTTP transport exists only for local development."""
import argparse,json,os,sys,threading,uuid,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from learning_calendar.bootstrap import configure_runtime
configure_runtime()

def data_folder():return Path(os.environ.get('APPDATA',str(Path.home()/'AppData/Roaming')))/'LutteLaurent'/'Calix'
def main():
    if sys.stdout is not None:sys.stdout.reconfigure(encoding='utf-8',line_buffering=True)
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir');parser.add_argument('--browser',action='store_true');parser.add_argument('--pipe');parser.add_argument('--dev-http',type=int);parser.add_argument('--demo',action='store_true');args=parser.parse_args()
    folder=Path(args.data_dir) if args.data_dir else data_folder()
    if args.browser:
        from learning_calendar.cookies import read_cookies
        from learning_calendar.login_browser import run
        return run(folder/'canvas_session.dpapi',existing=read_cookies(folder/'canvas_session.dpapi'),control_server=args.pipe)
    from PySide6.QtCore import QCoreApplication,QObject,Signal,QTimer,QProcess
    from PySide6.QtNetwork import QLocalServer,QLocalSocket
    from engine_api import EngineAPI
    app=QCoreApplication([]);app.setApplicationName('Calix');app.setOrganizationName('LutteLaurent')
    from learning_calendar.paths import migrate_legacy_data
    if not args.data_dir:migrate_legacy_data(folder)
    api=EngineAPI(folder)
    if args.demo:
        if not args.data_dir:raise ValueError('Demo requires an isolated data directory')
        from learning_calendar.demo import data
        courses,batches=data();api.store.apply_batch(courses,batches)
        if not api.store.timetable():
            for i,course in enumerate(courses[:5]):api.store.add_timetable(course.id,i,'09:00' if i%2 else '13:00','10:30' if i%2 else '14:30','김교수','A201')
    output_lock=threading.Lock()
    def emit(value):
        if args.dev_http:return
        with output_lock:
            sys.stdout.write(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n');sys.stdout.flush()
    class Bridge(QObject):
        incoming=Signal(object)
        def __init__(self):
            super().__init__();self.incoming.connect(self.handle);self.browser=None;self.socket=None;self.server=None;self.buffer=bytearray();self.task=None;self.collecting=False;self.pending_sync=False;self.logged_in=False;self.closing=False
        def notify(self,event,**payload):emit(dict(event=event,**payload))
        def handle(self,request):
            reply=request.pop('_reply',None)
            try:
                if type(request.get('id')) is not int or not isinstance(request.get('params',{}),dict):raise ValueError('요청을 확인하세요.')
                method=request.get('method');p=request.get('params',{})
                if method=='engine.state':result=dict(loggedIn=self.logged_in,busy=bool(self.task or self.collecting))
                elif method=='login':self.login();result=True
                elif method=='logout':self.command('logout');self.logged_in=False;result=True
                elif method=='sync':self.sync();result=True
                elif method=='event.open':
                    from learning_calendar.parsers import safe_url
                    import webbrowser
                    url=api.event(p['key']).url
                    if not safe_url(url):raise ValueError('학교 일정 주소를 확인하세요.')
                    webbrowser.open(url);result=True
                elif method=='app.open':
                    import webbrowser
                    links={'github':'https://github.com/luttechan/Calix','family':'https://luttechan.github.io/lutte_family/','guide':'https://luttechan.github.io/calix/guide/','releases':'https://github.com/luttechan/Calix/releases'}
                    if p.get('page') not in links:raise ValueError('주소를 확인하세요.')
                    webbrowser.open(links[p['page']]);result=True
                elif method=='quit':self.shutdown();result=True
                else:result=api.dispatch(method,p)
                response=dict(id=request['id'],result=result)
            except (KeyError,TypeError,ValueError) as exc:response=dict(id=request.get('id'),error=str(exc) if isinstance(exc,ValueError) else '입력 내용을 확인하세요.')
            except Exception:response=dict(id=request.get('id'),error='요청을 처리하지 못했습니다.')
            if reply:reply(response)
            else:emit(response)
        def command(self,name):
            if self.socket and self.socket.state()==QLocalSocket.LocalSocketState.ConnectedState:
                self.socket.write((json.dumps(dict(command=name))+'\n').encode());self.socket.flush();return True
            return False
        def login(self):
            if self.browser:
                self.command('show');return
            self.server=QLocalServer(self);self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption);name='Calix140-'+uuid.uuid4().hex
            if not self.server.listen(name):raise ValueError('로그인 창을 준비하지 못했습니다.')
            self.server.newConnection.connect(self.connected);self.browser=QProcess(self)
            arguments=[] if getattr(sys,'frozen',False) else [str(Path(__file__).resolve())]
            self.browser.setProgram(sys.executable);self.browser.setArguments(arguments+['--browser','--data-dir',str(folder),'--pipe',name]);self.browser.finished.connect(self.browser_finished);self.browser.start()
        def connected(self):
            self.socket=self.server.nextPendingConnection();self.socket.readyRead.connect(self.browser_read);self.server.close()
        def browser_read(self):
            self.buffer.extend(bytes(self.socket.readAll()))
            if len(self.buffer)>4*1024*1024:self.command('quit');self.buffer.clear();return
            while b'\n' in self.buffer:
                line,_,tail=self.buffer.partition(b'\n');self.buffer=bytearray(tail)
                try:message=json.loads(line)
                except ValueError:continue
                event=message.get('event')
                if event=='authenticated':
                    self.logged_in=True;self.notify('authentication',loggedIn=True)
                    if self.pending_sync:self.pending_sync=False;self.collecting=True;self.command('collect')
                elif event=='logged_out':self.logged_in=False;self.notify('authentication',loggedIn=False)
                elif event=='videos_collected':self.collecting=False;self.start_sync(message.get('snapshot'))
                elif event in ('collection_error','collection_auth_required','error'):
                    self.collecting=False;self.notify('sync-error',message=message.get('message','동기화 실패'))
                elif event=='collection_progress':self.notify('sync-progress',message=message.get('message','일정 확인 중'))
        def browser_finished(self,*args):
            process=self.browser;self.browser=None
            if process:process.deleteLater()
            if self.socket:self.socket.deleteLater();self.socket=None
            if self.server:self.server.close();self.server.deleteLater();self.server=None
            self.buffer.clear()
            if self.closing:self.finish_shutdown()
        def sync(self):
            if self.task or self.collecting:raise ValueError('동기화 중입니다.')
            if not self.browser or not self.logged_in:self.pending_sync=True;self.login();return
            self.collecting=True
            if not self.command('collect'):self.collecting=False;raise ValueError('로그인 연결을 확인하세요.')
            self.notify('sync-progress',message='주차학습 확인 중')
        def start_sync(self,snapshot):
            from learning_calendar.worker import SyncTask
            from learning_calendar.cookies import read_cookies
            self.task=SyncTask(read_cookies(folder/'canvas_session.dpapi'),api.store.path,self,dom_snapshot=snapshot)
            self.task.progress.connect(lambda value:self.notify('sync-progress',message=value));self.task.success.connect(self.synced);self.task.error.connect(lambda value:self.notify('sync-error',message=value));self.task.authentication_required.connect(lambda value:self.notify('sync-error',message=value));self.task.finished.connect(self.sync_finished);self.task.start()
        def synced(self,result):
            api.switch_store(result['path']);self.notify('data-changed');self.notify('sync-progress',message=result.get('sync_summary') or '동기화 완료')
        def sync_finished(self):
            task=self.task;self.task=None
            if task:task.deleteLater()
            if self.closing:self.finish_shutdown()
        def shutdown(self):
            if self.closing:return
            self.closing=True
            if self.task:self.task.cancel()
            if self.browser:self.command('quit');QTimer.singleShot(3000,self,lambda:self.browser.kill() if self.browser else None)
            self.finish_shutdown()
        def finish_shutdown(self):
            if self.task or self.browser:return
            api.close();QTimer.singleShot(0,app.quit)
    bridge=Bridge();http=None
    if args.dev_http:
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        token=os.environ.get('CALIX_DEV_TOKEN','')
        if len(token)<32:raise ValueError('Set a development token of at least 32 characters')
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                length=int(self.headers.get('Content-Length','0'))
                if self.path!='/api' or self.headers.get('X-Calix-Token')!=token or not 0<length<=2*1024*1024:self.send_error(403);return
                try:request=json.loads(self.rfile.read(length))
                except ValueError:self.send_error(400);return
                ready=threading.Event();result=[];request['_reply']=lambda value:(result.append(value),ready.set());bridge.incoming.emit(request)
                if not ready.wait(90):self.send_error(504);return
                data=json.dumps(result[0],ensure_ascii=False).encode();self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
        http=ThreadingHTTPServer(('127.0.0.1',args.dev_http),Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
    else:
        def reader():
            while True:
                line=sys.stdin.buffer.readline(2*1024*1024+1)
                if not line:bridge.incoming.emit(dict(id=0,method='quit',params={}));return
                if len(line)>2*1024*1024:emit(dict(id=None,error='요청이 너무 큽니다.'));return
                try:request=json.loads(line)
                except ValueError:emit(dict(id=None,error='요청 형식을 확인하세요.'));continue
                if not isinstance(request,dict):emit(dict(id=None,error='요청 형식을 확인하세요.'));continue
                bridge.incoming.emit(request)
        threading.Thread(target=reader,daemon=True).start()
    code=app.exec()
    if http:http.shutdown()
    return code
if __name__=='__main__':raise SystemExit(main())
