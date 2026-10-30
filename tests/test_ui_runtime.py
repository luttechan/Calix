import gc
import os
import sys
import time
from datetime import datetime, timedelta
import pytest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QWidget, QDialog
from learning_calendar.gui import MainWindow
from learning_calendar.fonts import apply_korean_font, font_path
from learning_calendar.design import apply_palette
from learning_calendar.models import Course, Event, KST
from learning_calendar.snapshot import Snapshot

@pytest.fixture(scope='module')
def app():
    app=QApplication.instance() or QApplication([])
    app.setStyle('Fusion');apply_palette(app);apply_korean_font(app)
    yield app

def drain(app):
    app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

@pytest.fixture
def window(app,tmp_path):
    w=MainWindow(tmp_path);w.show();drain(app)
    yield w
    w.dispose();w.deleteLater();drain(app)

def fill(w,count):
    now=datetime.now(KST)
    courses=[Course(1,'비즈니스 일본어'),Course(2,'통번역 연습')]
    rows=[Event(f'assignment:1:{i}',1,courses[0].name,'assignment',f'{i+1}주차 보고서',
                (now+timedelta(days=i%20-2)).isoformat(),False) for i in range(count)]
    w.snapshot=Snapshot(rows,courses);w._reload_course_filter();w.refresh()

def test_bundled_font_registered_once(app):
    assert font_path().is_file()
    original=app.property('bufsFontId');assert original>=0
    for _ in range(20):assert apply_korean_font(app)==app.property('bufsFontFamily')
    assert app.property('bufsFontId')==original

def test_korean_glyphs_and_navigation_metrics_are_stable(window,app):
    from PySide6.QtGui import QRawFont,QFontMetrics
    font=window.nav[0].font();raw=QRawFont.fromFont(font)
    assert all(raw.supportsCharacter(ord(c)) for c in '달력동영상과제시간표계정크레딧')
    before=QFontMetrics(font).horizontalAdvance('동영상')
    for page in range(4):
        window.select_page(page);drain(app)
        assert window.nav[0].font()==font
        assert QFontMetrics(window.nav[0].font()).horizontalAdvance('동영상')==before

def test_compact_layout_preserves_visible_text(window,app):
    from PySide6.QtGui import QFontMetrics
    window.select_page(0);window.main_stack._settle()
    window.resize(960,540);drain(app)
    assert not window.metrics.isVisible()
    assert window.width()<=960 and window.height()<=540
    for widget in [window.heading,window.month_label,window.day_title]:
        assert QFontMetrics(widget.font()).horizontalAdvance(widget.text())<=widget.contentsRect().width()
    window.status.setText('매우 긴 과목 이름과 동기화 진행 상황 '*8);drain(app)
    assert window.status.toolTip()==window.status.full_text
    assert QFontMetrics(window.status.font()).horizontalAdvance(window.status.text())<=window.status.contentsRect().width()

def test_browser_not_imported_by_calendar(window):
    assert 'PySide6.QtWebEngineCore' not in sys.modules
    assert 'PySide6.QtWebEngineWidgets' not in sys.modules

def test_large_list_does_not_allocate_row_widgets(window,app):
    fill(window,20);window.select_page(2);drain(app)
    baseline=len(window.findChildren(QWidget))
    fill(window,5000);drain(app)
    assert window.assignment_list.model().rowCount()==5000
    assert len(window.findChildren(QWidget))<=baseline+2

def test_idle_refresh_has_no_sql_or_model_reset(window,app):
    fill(window,100);window.select_page(2);drain(app)
    view=window.assignment_list;view.setCurrentIndex(view.model().index(50));view.scrollTo(view.currentIndex());drain(app)
    selected=view.currentIndex().data(Qt.ItemDataRole.UserRole);scroll=view.verticalScrollBar().value()
    queries=[];resets=[];window.store.db.set_trace_callback(queries.append)
    view.model().modelReset.connect(lambda:resets.append(1))
    for _ in range(10):window._tick();drain(app)
    assert not queries and not resets
    assert view.currentIndex().data(Qt.ItemDataRole.UserRole)==selected
    assert view.verticalScrollBar().value()==scroll

def test_credits_destroyed_on_close(window,app):
    before=len(window.findChildren(QDialog))
    for _ in range(20):
        window.credits();drain(app);window._dialogs['credits'].close();drain(app)
    assert len(window.findChildren(QDialog))==before
    assert not window._dialogs

def test_expired_filter_updates_calendar(window,app):
    now=datetime.now(KST)
    e=Event('assignment:1:1',1,'과목','assignment','마감', (now-timedelta(seconds=1)).isoformat(),False)
    window.snapshot=Snapshot([e],[Course(1,'과목')]);window._reload_course_filter()
    window.state_select.setCurrentIndex(3);window._tick()
    assert window._buckets[now.date()]==[e]

def test_demo_can_return_without_network(window):
    fill(window,5);window.preview();assert window.demo
    window.end_preview();assert not window.demo
    assert len(window.snapshot.events)==5

def test_timetable_adjacent_non_half_hour_classes(window,app):
    window.store.apply_batch([Course(1,'수업 A'),Course(2,'수업 B')],{(1,'assignment'):[]})
    window.store.add_timetable(1,0,'09:00','09:20')
    window.store.add_timetable(2,0,'09:20','10:00')
    window._sessions=window.store.timetable();window._reload();window.select_page(3);drain(app)
    blocks=window.timetable.surface.blocks
    first,second=[blocks[r['id']] for r in window._sessions]
    assert first.title.full=='수업 A' and second.title.full=='수업 B'
    assert first.geometry().bottom()<second.geometry().top()

def test_repeated_refresh_widget_and_memory_growth_bounded(window,app):
    import psutil
    fill(window,1000)
    for _ in range(5):
        for page in range(4):window.select_page(page);window.refresh();drain(app)
    gc.collect();before=psutil.Process().memory_info().rss;widgets=len(window.findChildren(QWidget))
    for _ in range(80):
        for page in range(3):window.select_page(page);window.refresh();drain(app)
    gc.collect();drain(app)
    growth=psutil.Process().memory_info().rss-before
    assert len(window.findChildren(QWidget))<=widgets
    assert growth<20*1024*1024, growth
