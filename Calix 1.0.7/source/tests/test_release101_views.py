from datetime import datetime,timedelta
import pytest
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from learning_calendar.gui import MainWindow
from learning_calendar.models import Event,Course,KST
from learning_calendar.snapshot import Snapshot

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app,tmp_path):
    w=MainWindow(tmp_path);now=datetime.now(KST)
    courses=[Course(1,'과목 A'),Course(2,'과목 B')]
    rows=[Event('a-past',1,'과목 A','assignment','지난 보고서',(now-timedelta(days=2)).isoformat(),False),
          Event('a-done',2,'과목 B','assignment','제출한 보고서',(now-timedelta(days=1)).isoformat(),True),
          Event('a-future',1,'과목 A','assignment','새 보고서',(now+timedelta(days=3)).isoformat(),False),
          Event('v-done',1,'과목 A','movie','시청한 영상',(now-timedelta(days=1)).isoformat(),True),
          Event('v-future',2,'과목 B','movie','다음 영상',(now+timedelta(days=4)).isoformat(),False)]
    w.store.apply_batch(courses,{(1,'assignment'):[rows[0],rows[2]],(2,'assignment'):[rows[1]],(1,'movie'):[rows[3]],(2,'movie'):[rows[4]]});w._reload()
    yield w
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

def keys(view):return {e.key for e in view.event_model.rows}

def test_calendar_filters_do_not_hide_imported_assignments_or_movies(window):
    w=window;w.select_page(0);w.course_select.setCurrentIndex(w.course_select.findData(1));w.type_filter.setCurrentIndex(w.type_filter.findData('movie'));w.state_select.setCurrentIndex(6);w.search.setText('달력에만 적용');w.refresh()
    w.select_page(2)
    assert keys(w.assignment_list)=={'a-past','a-done','a-future'}
    assert not w.type_filter.isVisible() and w.state_select.currentIndex()==0 and not w.search.text()
    assert '불러옴 3건' in w.sync_info.text()
    w.select_page(1);assert keys(w.video_list)=={'v-done','v-future'}
    w.select_page(0)
    assert w.course_select.currentData()==1 and w.type_filter.currentData()=='movie' and w.state_select.currentIndex()==6 and w.search.text()=='달력에만 적용'

def test_category_views_remember_only_their_own_search_and_status(window):
    w=window;w.select_page(2);w.search.setText('새 보고서');w.state_select.setCurrentIndex(1);w.refresh();assert keys(w.assignment_list)=={'a-future'}
    w.select_page(1);w.state_select.setCurrentIndex(2);assert keys(w.video_list)=={'v-done'}
    w.select_page(2);assert keys(w.assignment_list)=={'a-future'} and w.search.text()=='새 보고서' and w.state_select.currentIndex()==1
    w.filter_reset.click();assert keys(w.assignment_list)=={'a-past','a-done','a-future'} and not w.filter_reset.isEnabled()

def test_home_shortcuts_override_remembered_calendar_filters(window):
    w=window;w.select_page(0);w.search.setText('숨김');w.type_filter.setCurrentIndex(w.type_filter.findData('movie'));w.state_select.setCurrentIndex(2);w.select_page(2);w.show_home()
    w.open_details('remaining')
    assert w.tabs.currentIndex()==0 and w.state_select.currentIndex()==1 and not w.search.text() and w.type_filter.currentData() is None
    assert {e.key for e in w._filtered}=={'a-future','v-future'}

def test_sync_refreshes_visible_category_and_new_category_on_navigation(window):
    w=window;w.select_page(2);now=datetime.now(KST)
    rows=[Event('a-new',1,'과목 A','assignment','동기화 과제',(now+timedelta(days=1)).isoformat(),False),Event('v-new',1,'과목 A','movie','동기화 영상',(now+timedelta(days=1)).isoformat(),False)]
    result=dict(path=str(w.store.path),snapshot=Snapshot(rows,[Course(1,'과목 A')]),sessions=[],last_sync=now.isoformat(),warnings=[],stats={'new':2,'updated':0})
    w._sync_ok(result);assert keys(w.assignment_list)=={'a-new'}
    w.select_page(1);assert keys(w.video_list)=={'v-new'} and '불러옴 1건' in w.sync_info.text()

def test_empty_filtered_list_explains_hidden_rows_and_reset_restores_them(window):
    w=window;w.select_page(2);w.search.setText('일치하지 않는 검색');w.refresh()
    assert not keys(w.assignment_list) and w.assignment_list.empty_label.text()=='필터에 맞는 과제가 없습니다'
    w.reset_filters();assert len(keys(w.assignment_list))==3

def test_navigation_applies_pending_search_without_waiting_for_timer(window):
    w=window;w.select_page(2);w.search.setText('제출한');w.select_page(2)
    assert keys(w.assignment_list)=={'a-done'} and not w.search_timer.isActive()
