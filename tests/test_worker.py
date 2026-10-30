from pathlib import Path
from learning_calendar.worker import SyncTask
from learning_calendar.models import Course,Event
from learning_calendar.storage import Store

class FakeClient:
    identity=1
    batches={}
    warnings=[]
    def __init__(self,*args):self.session=self
    def close(self):pass
    def _get(self,path):return self
    def json(self):return {'id':self.identity}
    def fetch(self,progress):return [Course(1,'과목')],self.batches,self.warnings

def test_all_failed_does_not_advance_sync(monkeypatch,tmp_path):
    monkeypatch.setattr('learning_calendar.worker.CampusClient',FakeClient)
    monkeypatch.setattr(FakeClient,'batches',{})
    path=tmp_path/'learning.db';store=Store(path);store.set_meta('last_sync','old');store.close()
    task=SyncTask([],path);errors=[];task.error.connect(errors.append);task.run()
    assert errors
    store=Store(path);assert store.get_meta('last_sync')=='old';store.close()

def test_different_canvas_account_uses_separate_db(monkeypatch,tmp_path):
    monkeypatch.setattr('learning_calendar.worker.CampusClient',FakeClient)
    monkeypatch.setattr(FakeClient,'identity',2)
    monkeypatch.setattr(FakeClient,'batches',{(1,'assignment'):[Event('assignment:1:1',1,'과목','assignment','과제',None,False)]})
    path=tmp_path/'learning.db';store=Store(path);store.set_meta('canvas_user_id','1');store.close()
    results=[];task=SyncTask([],path);task.success.connect(results.append);task.run()
    assert len(results)==1 and Path(results[0]['path']).name=='learning-user-2.db'
    store=Store(path);assert store.get_meta('canvas_user_id')=='1';assert not store.events();store.close()

def test_unchanged_batch_does_not_rewrite_event(tmp_path):
    store=Store(tmp_path/'db')
    e=Event('assignment:1:1',1,'과목','assignment','과제',None,False)
    store.apply_batch([Course(1,'과목')],{(1,'assignment'):[e]})
    first=store.db.execute('select updated_at from events').fetchone()[0]
    statements=[];store.db.set_trace_callback(statements.append)
    stats=store.apply_batch([Course(1,'과목')],{(1,'assignment'):[e]})
    assert stats['unchanged']==1
    assert not any('INSERT INTO events' in s for s in statements)
    assert store.db.execute('select updated_at from events').fetchone()[0]==first
    store.close()

def test_switching_back_reuses_original_account_database(monkeypatch,tmp_path):
    monkeypatch.setattr('learning_calendar.worker.CampusClient',FakeClient)
    monkeypatch.setattr(FakeClient,'identity',1)
    monkeypatch.setattr(FakeClient,'batches',{(1,'assignment'):[]})
    original=Store(tmp_path/'learning.db');original.set_meta('canvas_user_id','1');original.close()
    second=Store(tmp_path/'learning-user-2.db');second.set_meta('canvas_user_id','2');second.close()
    results=[];task=SyncTask([],tmp_path/'learning-user-2.db');task.success.connect(results.append);task.run()
    assert Path(results[0]['path']).name=='learning.db'
