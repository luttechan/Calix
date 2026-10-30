import pytest
from PySide6.QtCore import Qt,QCoreApplication,QEvent,QPoint
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from learning_calendar.gui import MainWindow
from learning_calendar.models import Course
from learning_calendar.timetable_view import SessionEditor

@pytest.fixture
def app():return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app,tmp_path):
    w=MainWindow(tmp_path);courses=[Course(1,'법정교육 장애인인식교육'),Course(2,'삶과 철학')]
    w.store.apply_batch(courses,{(c.id,'assignment'):[] for c in courses});w.store.add_timetable(2,0,'09:00','10:30')
    w._sessions=w.store.timetable();w._reload();w.select_page(3);w.main_stack._settle();w.show();app.processEvents();yield w
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

@pytest.mark.parametrize('accept',[False,True])
def test_class_double_click_never_opens_add_dialog_after_edit(window,app,accept):
    calls=[]
    def edit(dialog):calls.append((dialog.windowTitle(),dialog.course.currentData()));return accept
    window._exec_dialog=edit;card=next(iter(window.timetable.surface.blocks.values()))
    QTest.mouseDClick(card,Qt.MouseButton.LeftButton);app.processEvents()
    assert calls==[('수업 편집',2)]
    assert len(window.store.timetable())==1 and window.store.timetable()[0]['course_id']==2

def test_edit_button_and_enter_use_selected_course(window,app):
    calls=[];window._exec_dialog=lambda dialog:calls.append((dialog.windowTitle(),dialog.course.currentData())) or False
    card=next(iter(window.timetable.surface.blocks.values()));window.timetable.select(card.row['id'])
    QTest.mouseClick(window.timetable.edit_button,Qt.MouseButton.LeftButton);QTest.keyClick(card,Qt.Key.Key_Return);app.processEvents()
    assert calls==[('수업 편집',2),('수업 편집',2)]

def test_double_click_on_class_text_is_not_an_empty_slot(window,app):
    calls=[];window._exec_dialog=lambda dialog:calls.append(dialog.windowTitle()) or False
    card=next(iter(window.timetable.surface.blocks.values()))
    QTest.mouseDClick(card.title,Qt.MouseButton.LeftButton);app.processEvents();assert calls==['수업 편집']

def test_empty_slot_still_opens_add_once(window,app):
    calls=[];window._exec_dialog=lambda dialog:calls.append(dialog.windowTitle()) or False
    surface=window.timetable.surface;point=QPoint(surface.AXIS+30,surface.TOP+4*surface.hour_height)
    QTest.mouseDClick(surface,Qt.MouseButton.LeftButton,pos=point);app.processEvents();assert calls==['수업 추가']

@pytest.mark.parametrize('read_only',[False,True])
def test_right_click_and_read_only_never_create_or_edit(window,app,read_only):
    calls=[];window._exec_dialog=lambda dialog:calls.append(dialog.windowTitle()) or False
    view=window.timetable;view.set_read_only(read_only);card=next(iter(view.surface.blocks.values()));surface=view.surface
    QTest.mouseDClick(card,Qt.MouseButton.RightButton);QTest.mouseDClick(surface,Qt.MouseButton.RightButton,pos=QPoint(surface.AXIS+30,surface.TOP+4*surface.hour_height))
    if read_only:
        QTest.mouseDClick(card,Qt.MouseButton.LeftButton);QTest.mouseDClick(surface,Qt.MouseButton.LeftButton,pos=QPoint(surface.AXIS+30,surface.TOP+4*surface.hour_height))
    app.processEvents();assert not calls

def test_forwarded_background_event_over_existing_card_is_ignored(window,app):
    calls=[];window._exec_dialog=lambda dialog:calls.append(dialog.windowTitle()) or False
    surface=window.timetable.surface;card=next(iter(surface.blocks.values()))
    QTest.mouseDClick(surface,Qt.MouseButton.LeftButton,pos=card.geometry().center());app.processEvents();assert not calls

def test_missing_existing_course_never_falls_back_to_first_course(app):
    item=dict(course_id=2,day=0,start_time='09:00',end_time='10:30',professor='',room='',color='#7582E6')
    dialog=SessionEditor([Course(1,'법정교육 장애인인식교육')],item)
    assert dialog.course.currentData() is None and dialog.error.text()
    dialog._save();assert dialog.result()!=dialog.DialogCode.Accepted
    dialog.deleteLater();app.processEvents()
