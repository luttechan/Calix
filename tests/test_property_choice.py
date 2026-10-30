import os,sys,json,subprocess
import pytest
from PySide6.QtCore import Qt,QCoreApplication,QEvent,QPoint
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from learning_calendar.checklist_popup import FieldPopup


@pytest.fixture
def app():return QApplication.instance() or QApplication([])

def pump(app):
    QTest.qWait(30);app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

def row():return dict(id='test',category='컴퓨터 구조',role='자료 조사',professor='김교수',status_id=2)

@pytest.mark.parametrize('column',[2,3,4])
def test_existing_property_stays_open_until_explicit_action(app,column):
    saved=[];popup=FieldPopup(column,row(),['검토','김교수','자료 조사','컴퓨터 구조'],lambda value:saved.append(value) or True)
    popup.show();pump(app)
    assert popup.isVisible() and not saved and popup.combo.view().isVisible()
    assert QApplication.activePopupWidget() is popup
    popup.reject();pump(app);assert not saved

def test_freeform_typing_filters_without_selecting_or_saving(app):
    saved=[];popup=FieldPopup(3,row(),['검토','자료 조사','발표'],lambda value:saved.append(value) or True)
    popup.show();pump(app);field=popup.combo.input;field.selectAll();QTest.keyClicks(field,'Research')
    assert popup.isVisible() and not saved and popup.combo.count()==0 and popup.combo.currentText()=='Research'
    QTest.keyClick(field,Qt.Key.Key_Return);pump(app);assert saved==['Research']

def test_keyboard_navigation_commits_only_on_enter(app):
    saved=[];popup=FieldPopup(3,row(),['검토','발표','자료 조사'],lambda value:saved.append(value) or True)
    popup.show();pump(app);field=popup.combo.input
    QTest.keyClick(field,Qt.Key.Key_Down);QTest.keyClick(field,Qt.Key.Key_Down)
    assert popup.isVisible() and not saved and popup.combo.currentText()=='자료 조사'
    QTest.keyClick(field,Qt.Key.Key_Return);pump(app);assert saved==['발표']

def test_filtered_mouse_selection_saves_selected_text(app):
    saved=[];popup=FieldPopup(4,row(),['김교수','이교수','박교수'],lambda value:saved.append(value) or True)
    popup.show();pump(app);combo=popup.combo;combo.input.setText('이');combo.input.textEdited.emit('이')
    assert combo.count()==1 and not saved
    index=combo.model().index(0,0);QTest.mouseClick(combo.view().viewport(),Qt.MouseButton.LeftButton,pos=combo.view().visualRect(index).center());pump(app)
    assert saved==['이교수'] and QApplication.activePopupWidget() is None

def test_escape_after_filtering_preserves_old_property(app):
    saved=[];popup=FieldPopup(3,row(),['검토','자료 조사'],lambda value:saved.append(value) or True);popup.show();pump(app)
    popup.combo.input.selectAll();QTest.keyClicks(popup.combo.input,'changed');QTest.keyClick(popup.combo.input,Qt.Key.Key_Escape);pump(app);assert not saved

def test_korean_ime_composition_does_not_save_or_close(app):
    from PySide6.QtGui import QInputMethodEvent
    saved=[];popup=FieldPopup(4,row(),['김교수','이교수'],lambda value:saved.append(value) or True);popup.show();pump(app);field=popup.combo.input
    field.selectAll();QCoreApplication.sendEvent(field,QInputMethodEvent('새 담당',[]));pump(app)
    assert popup.isVisible() and not saved
    event=QInputMethodEvent();event.setCommitString('새 담당');QCoreApplication.sendEvent(field,event);pump(app)
    assert popup.isVisible() and not saved and field.text()=='새 담당'
    QTest.keyClick(field,Qt.Key.Key_Return);pump(app);assert saved==['새 담당']

def test_long_options_and_empty_list_have_bounded_geometry(app):
    popup=FieldPopup(2,row(),['긴 과목 이름 '*40]+[f'과목 {i}' for i in range(50)],lambda _:True);popup.show();pump(app)
    assert popup.combo.view().height()<=224 and popup.width()<800
    popup.reject();pump(app)

@pytest.mark.skipif(sys.platform!='win32',reason='Windows native release path')
def test_filled_cells_remain_open_on_real_windows_platform(tmp_path):
    script=r'''
import os,sys,json
sys.path[:0]=json.loads(os.environ['CALIX_TEST_PATHS'])
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from learning_calendar.gui import MainWindow
from learning_calendar.checklist_store import ChecklistStore
app=QApplication([]);w=MainWindow(Path(sys.argv[1]));w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
repo=ChecklistStore(w.store);repo.add(1,'검사 할 일');row=repo.rows(1)[0]
for field,value in [('category','컴퓨터 구조'),('role','자료 조사'),('professor','김교수')]:repo.save(row,field,value)
w.show_checklist();w.main_stack._settle();w.show();QTest.qWait(30)
for column in (2,3,4,5):
    view=w.checklist;index=view.proxy.index(0,column);view.table.scrollTo(index);app.processEvents()
    QTest.mouseClick(view.table.viewport(),Qt.MouseButton.LeftButton,pos=view.table.visualRect(index).center());QTest.qWait(150)
    popup=view.popup;assert popup and popup.isVisible(),column
    assert QApplication.activePopupWidget() is popup
    popup.reject();QTest.qWait(30)
w.dispose();print('NATIVE_FILLED_PROPERTIES_OK')
'''
    env=os.environ.copy();env['QT_QPA_PLATFORM']='windows:fontengine=directwrite';env['CALIX_TEST_PATHS']=json.dumps(sys.path)
    result=subprocess.run([sys.executable,'-B','-c',script,str(tmp_path/'native')],env=env,capture_output=True,text=True,timeout=35)
    assert result.returncode==0,result.stderr[-1500:]
    assert 'NATIVE_FILLED_PROPERTIES_OK' in result.stdout

@pytest.mark.parametrize('size',[(320,260),(740,500),(1150,800)])
def test_calendar_date_and_badges_share_keyline_without_overlap(app,size):
    from datetime import date
    from learning_calendar.calendar_view import MonthCanvas
    from learning_calendar.models import Event
    day=date(2026,11,4);event=Event('assignment:1:1',1,'수업','assignment','할 일','2026-11-04T23:59:00+09:00',False)
    calendar=MonthCanvas();calendar.resize(*size);calendar.set_month(day.replace(day=1),day,{day:[event]});calendar.show();pump(app);calendar._layout_badges()
    index=next(i for i,badge in enumerate(calendar.badges) if badge.property('calendarDate')==day.isoformat());badge=calendar.badges[index];number=calendar.date_labels[index]
    rect=calendar.view.visualRect(calendar.view.model().index(index//7+1,index%7))
    assert badge.isVisible() and badge.x()==number.x()
    assert number.geometry().bottom()<badge.geometry().top()
    assert rect.contains(number.geometry()) and rect.contains(badge.geometry())
    calendar.close();calendar.deleteLater();pump(app)
