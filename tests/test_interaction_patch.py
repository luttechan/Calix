from datetime import date
import pytest
from PySide6.QtCore import Qt,QCoreApplication,QEvent,QTime,QPoint,QTimer,QDate
from PySide6.QtWidgets import QApplication,QMenu,QDialog,QAbstractButton,QLineEdit
from PySide6.QtTest import QTest
from learning_calendar.gui import MainWindow
from learning_calendar.models import Course,Event
from learning_calendar.checklist_store import ChecklistStore
from learning_calendar.checklist_view import ROW_ROLE
from learning_calendar.controls import TimeInput,DateInput
from learning_calendar.timetable_view import SessionEditor,TimetableView


@pytest.fixture
def app():return QApplication.instance() or QApplication([])


def pump(app):
    app.processEvents();QTest.qWait(10);QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()


@pytest.fixture
def window(app,tmp_path):
    w=MainWindow(tmp_path);repo=ChecklistStore(w.store)
    repo.add(1,'첫 번째 할 일');repo.add(1,'두 번째 할 일')
    w.show_checklist();w.main_stack._settle();w.show();pump(app)
    yield w
    w.dispose();w.deleteLater();pump(app)


def click_cell(w,column,row=0):
    view=w.checklist;index=view.proxy.index(row,column);view.table.scrollTo(index);QApplication.processEvents()
    QTest.mouseClick(view.table.viewport(),Qt.MouseButton.LeftButton,pos=view.table.visualRect(index).center())
    QApplication.processEvents();return view.popup


@pytest.mark.parametrize('column',[0,1,2,3,4,5,6])
def test_one_click_opens_correct_property(window,app,column):
    popup=click_cell(window,column)
    assert popup is not None and popup.isVisible() and popup.column==column
    assert not popup.mask().isEmpty()
    popup.reject();pump(app);assert window.checklist.popup is None


def test_status_selection_saves_and_closes_all_dropdowns(window,app):
    popup=click_cell(window,5);key=popup.row['id'];pump(app);combo=popup.combo;choice=combo.findData(2)
    combo.view().scrollTo(combo.model().index(choice,0));QTest.mouseClick(combo.view().viewport(),Qt.MouseButton.LeftButton,pos=combo.view().visualRect(combo.model().index(choice,0)).center());pump(app)
    assert window.checklist.popup is None
    assert next(r for r in ChecklistStore(window.store).rows(1) if r['id']==key)['status_id']==2
    assert QApplication.activePopupWidget() is None


def test_escape_cancels_even_with_child_dropdown_open(window,app):
    popup=click_cell(window,5);pump(app);QTest.keyClick(popup.combo,Qt.Key.Key_Escape);pump(app)
    assert window.checklist.popup is None and QApplication.activePopupWidget() is None


def test_outside_click_saves_and_dismisses(window,app):
    popup=click_cell(window,0);popup.input.setText('외부 클릭 저장')
    QTest.mouseClick(window.heading,Qt.MouseButton.LeftButton);pump(app)
    assert window.checklist.popup is None
    assert any(r['title']=='외부 클릭 저장' for r in ChecklistStore(window.store).rows(1))


def test_application_deactivation_closes_editor(window,app):
    popup=click_cell(window,0);popup.input.setText('창 전환 저장')
    QCoreApplication.sendEvent(app,QEvent(QEvent.Type.ApplicationDeactivate));pump(app)
    assert window.checklist.popup is None


@pytest.mark.parametrize('destination',['home','calendar','timetable','diary'])
def test_menu_navigation_closes_calendar_and_checklist_popups(window,app,destination):
    popup=click_cell(window,0);popup.input.setText('이동 전 저장')
    if destination=='home':window.show_home()
    elif destination=='diary':window.show_diary()
    else:window.select_page(0 if destination=='calendar' else 3)
    pump(app);assert window.checklist.popup is None
    e=Event('assignment:1:1',1,'수업','assignment','과제','2026-11-01T23:59:00+09:00',False)
    overlay=window.show_calendar_details(date(2026,11,1),[e],QPoint(200,200));pump(app)
    assert not overlay.mask().isEmpty() and not overlay.mask().contains(QPoint(0,0))
    window.show_checklist();pump(app);assert window._event_popover is None


def test_calendar_popup_escape_from_note_editor(window,app):
    e=Event('assignment:1:1',1,'수업','assignment','과제','2026-11-01T23:59:00+09:00',False)
    popup=window.show_calendar_details(date(2026,11,1),[e],QPoint(200,200));pump(app)
    QTest.keyClick(popup.note,Qt.Key.Key_Escape);pump(app);assert window._event_popover is None


def test_calendar_and_typed_date_are_saved_in_korean_time(window,app):
    popup=click_cell(window,1);key=popup.row['id'];popup.date_text.setText('2026-12-09');popup.time.lineEdit().setText('930');popup.commit();pump(app)
    assert window.checklist.popup is None
    assert next(r for r in ChecklistStore(window.store).rows(1) if r['id']==key)['due_at']=='2026-12-09T09:30:00+09:00'
    popup=click_cell(window,1);popup.date_text.setText('2026.02.30');popup.commit();assert window.checklist.popup is popup and popup.error.text()
    popup.reject();pump(app)


def test_date_popup_reopen_does_not_lose_new_reference(app):
    field=DateInput();field.show();pump(app);field._open();pump(app);old=field.popup;old.close();field._open();new=field.popup;pump(app)
    assert new is not None and field.popup is new and new.isVisible()
    assert new.screen().availableGeometry().contains(new.geometry()) and not new.mask().contains(QPoint(0,0))
    new.reject();field.close();field.deleteLater();pump(app)


@pytest.mark.parametrize('cursor',[2,3])
def test_backspace_deletes_hour_across_colon(app,cursor):
    field=TimeInput(QTime(9,35));field.show();field.lineEdit().setCursorPosition(cursor);QTest.keyClick(field.lineEdit(),Qt.Key.Key_Backspace)
    assert field.text()=='0:35'
    field.lineEdit().selectAll();QTest.keyClick(field.lineEdit(),Qt.Key.Key_Backspace);assert not field.time().isValid()
    QTest.keyClicks(field.lineEdit(),'0930');field.normalize();assert field.text()=='09:30'
    field.close();field.deleteLater();pump(app)


def test_invalid_time_blocks_timetable_save(app):
    editor=SessionEditor([Course(1,'수업')]);editor.start.lineEdit().setText('99:99');editor._save()
    assert editor.result()!=QDialog.DialogCode.Accepted and '시간' in editor.error.text()
    editor.close();editor.deleteLater();pump(app)


def test_time_axis_double_click_does_not_add_class_and_narrow_content_fits(app):
    view=TimetableView();view.resize(800,650);view.set_days(7)
    rows=[dict(id=i+1,course_id=1,day=i,start_time='09:00',end_time='11:00',professor='담당 교수',room='강의실',color='') for i in range(7)]
    view.set_data(rows,{1:'아주 긴 수업명 / 긴 교수 이름'}, {1:(10,20)});view.show();pump(app)
    created=[];view.surface.create.connect(lambda *args:created.append(args));QTest.mouseDClick(view.surface,Qt.MouseButton.LeftButton,pos=QPoint(10,100));assert not created
    assert view.inspector.isHidden()
    for block in view.surface.blocks.values():
        if not block.time.isHidden():assert '\n' in block.time.text() and block.time.geometry().right()<=block.width()
    view.set_days(5);view.resize(1500,800);pump(app);assert not view.inspector.isHidden()
    view.close();view.deleteLater();pump(app)


def test_filtered_count_uses_visible_rows_and_new_task_is_visible(window,app):
    view=window.checklist;repo=ChecklistStore(window.store);repo.toggle(repo.rows(1)[1],True);view.refresh()
    view.search.setText('첫 번째');view.filter_changed();assert view.count.text()=='1개 / 완료 0개'
    view.add_task();pump(app);assert view.popup is not None and view.proxy.rowCount()==3 and not view.search.text()
    view.popup.reject();pump(app)


def test_transient_menus_are_released_and_hints_present(window,app):
    view=window.checklist;pos=view.table.visualRect(view.proxy.index(0,0)).center()
    for _ in range(3):
        QTimer.singleShot(0,view,lambda:QApplication.activePopupWidget().close() if QApplication.activePopupWidget() else None)
        view.context_menu(pos);pump(app)
    assert not view.findChildren(QMenu)
    for button in [window.checklist_nav,window.home_nav,window.sync_btn,view.add_button,view.trash_button]:assert button.toolTip() and button.accessibleName()


def test_completion_and_previous_status_are_atomic_on_disk_failure(window):
    import sqlite3
    repo=ChecklistStore(window.store);row=repo.rows(1)[0];repo.save(row,'status_id',2);row=repo.rows(1)[0]
    repo.db.execute("CREATE TRIGGER reject_previous_status BEFORE UPDATE OF previous_status ON checklist_tasks BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
    with pytest.raises(sqlite3.IntegrityError):repo.toggle(row,True)
    assert next(r for r in repo.rows(1) if r['id']==row['id'])['status_id']==2


def test_old_calendar_editor_cannot_write_after_account_switch(window,app,tmp_path):
    from learning_calendar.storage import Store
    e=Event('assignment:1:1',1,'수업','assignment','과제','2026-11-01T23:59:00+09:00',False)
    window.store.apply_batch([Course(1,'수업')],{(1,'assignment'):[e]});window._reload()
    popup=window.show_calendar_details(date(2026,11,1),[e],QPoint(200,200));pump(app);old=window.store
    replacement=Store(tmp_path/'other.db');replacement.apply_batch([Course(1,'수업')],{(1,'assignment'):[e]});window.store=replacement
    try:
        with pytest.raises(ValueError):popup.save_callback(e,'다른 계정에 쓸 수 없음',None,'오래된 메모')
        assert replacement.events()[0].note=='' and replacement.events()[0].title=='과제'
    finally:window.store=old;replacement.close()


def test_failed_date_close_preserves_old_value_and_reports_problem(window,app):
    popup=click_cell(window,1);key=popup.row['id'];popup.date_text.setText('2026.02.30');window.show_home();pump(app)
    assert window.checklist.popup is None and '날짜' in window.checklist.message.text()
    assert next(r for r in ChecklistStore(window.store).rows(1) if r['id']==key)['due_at'] is None


def test_repeated_popup_cycles_leave_no_hidden_editors(window,app):
    from learning_calendar.checklist_popup import FieldPopup
    for i in range(30):
        popup=click_cell(window,5 if i%2 else 0)
        if popup.combo:QTest.keyClick(popup.combo,Qt.Key.Key_Escape)
        else:popup.reject()
        pump(app)
    assert window.checklist.popup is None and not window.checklist.findChildren(FieldPopup) and QApplication.activePopupWidget() is None


def test_sorting_while_editing_keeps_stable_task_identity(window,app):
    popup=click_cell(window,0);key=popup.row['id'];popup.input.setText('정렬 후에도 같은 할 일')
    window.checklist.table.sortByColumn(0,Qt.SortOrder.DescendingOrder);popup.commit();pump(app)
    rows=ChecklistStore(window.store).rows(1)
    assert next(r for r in rows if r['id']==key)['title']=='정렬 후에도 같은 할 일'
    assert sum(r['title']=='정렬 후에도 같은 할 일' for r in rows)==1


def test_checklist_switching_account_cancels_old_editor(window,app,tmp_path):
    from learning_calendar.storage import Store
    popup=click_cell(window,0);key=popup.row['id'];popup.input.setText('다른 계정에는 저장 금지')
    replacement=Store(tmp_path/'checklist-other.db');repo=ChecklistStore(replacement);repo.add(1,'다른 계정 할 일')
    try:
        window.checklist.set_data(replacement,[],[],[]);pump(app)
        assert window.checklist.popup is None
        assert next(r for r in ChecklistStore(window.store).rows(1) if r['id']==key)['title']!='다른 계정에는 저장 금지'
        assert repo.rows(1)[0]['title']=='다른 계정 할 일'
    finally:window.checklist.set_data(window.store,[],[],[]);replacement.close()
