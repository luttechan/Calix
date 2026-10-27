import threading
import subprocess,sys,time
from pathlib import Path
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from learning_calendar.worker import SyncTask
from learning_calendar.sync import CampusClient,SyncCancelled
from learning_calendar.models import Course,Event
from learning_calendar.storage import Store

def test_cancelled_sync_does_not_wait_for_blocked_network_or_write_database(tmp_path,monkeypatch):
    import learning_calendar.worker as worker
    app=QApplication.instance() or QApplication([])
    started=threading.Event();release=threading.Event();closed=threading.Event()
    class Client:
        def __init__(self,*args):self.session=SimpleNamespace(close=closed.set)
        def _get(self,*args):
            started.set();release.wait(5);return SimpleNamespace(json=lambda:{'id':1})
        def fetch(self,*args):return [],{},[]
    monkeypatch.setattr(worker,'CampusClient',Client)
    path=tmp_path/'learning.db';task=SyncTask([],path);events=[]
    task.success.connect(lambda value:events.append('success'));task.error.connect(lambda value:events.append('error'))
    task.start()
    try:
        assert started.wait(1);task.cancel();assert task.wait(400)
        app.processEvents();assert not events and not path.exists()
    finally:
        release.set();assert closed.wait(1);task.wait(1000);task.deleteLater();app.processEvents()

def test_network_result_is_committed_only_by_the_owned_sync_thread(tmp_path,monkeypatch):
    import learning_calendar.worker as worker
    app=QApplication.instance() or QApplication([])
    class Client:
        movie_auth_required=False
        def __init__(self,*args):self.session=SimpleNamespace(close=lambda:None)
        def _get(self,*args):return SimpleNamespace(json=lambda:{'id':7})
        def fetch(self,*args):return [Course(1,'과목')],{(1,'assignment'):[Event('assignment:1:1',1,'과목','assignment','과제',None,False)]},[]
    monkeypatch.setattr(worker,'CampusClient',Client)
    path=tmp_path/'learning.db';task=SyncTask([],path);results=[];task.success.connect(results.append)
    task.run();assert len(results)==1 and results[0]['snapshot'].events[0].title=='과제'
    store=Store(path)
    try:assert store.get_meta('canvas_user_id')=='7' and len(store.events())==1
    finally:store.close();task.deleteLater();app.processEvents()

def test_parallel_course_cancellation_uses_only_daemon_network_workers(monkeypatch):
    cancel=threading.Event();release=threading.Event();started=threading.Event();done=threading.Event();errors=[]
    client=CampusClient([],cancel)
    monkeypatch.setattr(client,'_get',lambda *args:SimpleNamespace(json=lambda:[{'id':1,'longName':'수업1'},{'id':2,'longName':'수업2'}]))
    def collect(self,course,say):
        assert threading.current_thread().daemon
        started.set();release.wait(5);return {(course.id,'assignment'):[]},[]
    monkeypatch.setattr(CampusClient,'_fetch_course',collect)
    def run():
        try:client.fetch()
        except SyncCancelled:errors.append('cancelled')
        finally:done.set()
    thread=threading.Thread(target=run,daemon=True);thread.start()
    try:
        assert started.wait(1);cancel.set();assert done.wait(.4);assert errors==['cancelled']
    finally:release.set();thread.join(1);client.session.close()

def test_process_exits_while_a_cancelled_network_request_is_still_blocked():
    paths=[str(Path(__file__).parents[1])]+[path for path in sys.path if 'test-deps' in path]
    code=r'''
import sys,threading,tempfile
from pathlib import Path
from types import SimpleNamespace
sys.path[:0]=PATHS
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication,QEvent
from learning_calendar.worker import SyncTask
import learning_calendar.worker as worker
started=threading.Event();blocked=threading.Event()
class Client:
    def __init__(self,*args):self.session=SimpleNamespace(close=lambda:None)
    def _get(self,*args):
        started.set();blocked.wait(60);return SimpleNamespace(json=lambda:{'id':1})
    def fetch(self,*args):return [],{},[]
worker.CampusClient=Client
app=QApplication([])
with tempfile.TemporaryDirectory() as folder:
    task=SyncTask([],Path(folder)/'learning.db');task.start()
    assert started.wait(1)
    task.cancel();assert task.wait(400)
    task.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
print('closed',flush=True)
'''.replace('PATHS',repr(paths))
    started=time.monotonic()
    result=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stdout+result.stderr
    assert result.stdout.strip()=='closed' and time.monotonic()-started<3
