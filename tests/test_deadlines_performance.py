from datetime import datetime,timedelta
import threading,time
from learning_calendar.models import Event,KST
from learning_calendar.snapshot import Snapshot

NOW=datetime(2026,10,26,12,tzinfo=KST)

def fixture_snapshot():
    deltas=[-86400,-1,0,3600,86400,7*86400,7*86400+1,None,3600]
    return Snapshot([Event(str(i),1,'과목','assignment',f'일정 {i}',
        (NOW+timedelta(seconds=d)).isoformat() if d is not None else None,i==8)
        for i,d in enumerate(deltas)])

def test_deadline_boundary_is_shared_by_metrics_and_filters():
    s=fixture_snapshot()
    assert s.deadline_counts(NOW)==(1,3,5)
    assert {e.key for e in s.pending(NOW)}=={'3','4','5','6','7'}
    assert {e.key for e in s.filtered(status=1,now=NOW)}=={'3','4','5','6','7'}
    assert {e.key for e in s.today_pending(NOW)}=={'3'}
    assert {e.key for e in s.filtered(status=6,now=NOW)}=={'3'}
    assert {e.key for e in s.filtered(status=3,now=NOW)}=={'0','1','2'}



def test_parallel_courses_bound_concurrency_and_close_owned_sessions(monkeypatch):
    from learning_calendar.sync import CampusClient
    client=CampusClient([]);lock=threading.Lock();state={'active':0,'peak':0};owned=[];closed=[]
    class Response:
        def json(self):return [{'id':i,'longName':f'과목 {i}'} for i in range(1,9)]
    monkeypatch.setattr(client,'_get',lambda *a,**k:Response())
    def collect(self,course,say):
        with lock:
            owned.append(self.session);state['active']+=1;state['peak']=max(state['peak'],state['active'])
        original=self.session.close
        def close():closed.append(self.session);original()
        self.session.close=close
        try:
            time.sleep(.03)
            return {(course.id,'assignment'):[]},[]
        finally:
            with lock:state['active']-=1
    monkeypatch.setattr(CampusClient,'_fetch_course',collect)
    courses,batches,warnings=client.fetch()
    assert len(courses)==len(batches)==8 and not warnings
    assert 1<state['peak']<=4 and len({id(s) for s in owned})==8
    assert len(closed)==8 and all(s is not client.session for s in owned)
    client.session.close()
