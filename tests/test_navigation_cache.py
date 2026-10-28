from datetime import datetime,timedelta
import pytest
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from learning_calendar import gui
from learning_calendar.models import Event,KST
from learning_calendar.snapshot import Snapshot


@pytest.mark.parametrize('status,days',[(1,0),(7,7)])
def test_menu_cache_expires_at_actual_deadline_boundary(tmp_path,monkeypatch,status,days):
    app=QApplication.instance() or QApplication([]);w=gui.MainWindow(tmp_path)
    clock=[datetime(2026,10,28,12,tzinfo=KST)]
    class Clock:
        @staticmethod
        def now(tz=None):return clock[0]
    monkeypatch.setattr(gui,'datetime',Clock)
    event=Event('assignment:1:1',1,'과목','assignment','기한 검사',(clock[0]+timedelta(days=days,seconds=1)).isoformat(),False)
    w.snapshot=Snapshot([event]);w.select_page(2);w.state_select.setCurrentIndex(status);w.refresh()
    assert w.assignment_list.event_model.rowCount()==(1 if status==1 else 0)
    clock[0]+=timedelta(seconds=2);w.refresh()
    assert w.assignment_list.event_model.rowCount()==(0 if status==1 else 1)
    fresh=Snapshot([event]);w.snapshot=fresh;w.select_page(1)
    assert all(entry[0][0] is fresh for entry in w._page_cache.values())
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
