import threading
import requests
import pytest
from datetime import datetime, timedelta
from learning_calendar.sync import CampusClient, SyncCancelled
from learning_calendar.models import Event, KST, deadline_display


def test_cancelled_sync_makes_no_http_requests(monkeypatch):
    cancel=threading.Event()
    client=CampusClient([],cancel)
    cancel.set()
    invoked=[]
    monkeypatch.setattr(client.session, 'get',lambda *args, **kwargs: invoked.append(1))
    with pytest.raises(SyncCancelled):
        client.fetch()
    assert not invoked
    client.session.close()


def test_deadline_displays_full_days_not_rounded_up():
    now=datetime(2026,10,11,10,0,tzinfo=KST)
    due=(now+timedelta(days=2,hours=23)).isoformat()
    e=Event('movie:1:1',1,'과목','movie','영상',due,False)
    assert deadline_display(e,now)==('마감 2일 전','orange')
