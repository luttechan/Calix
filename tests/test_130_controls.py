from datetime import date
import pytest
from shiboken6 import isValid
from PySide6.QtCore import Qt,QEvent,QPoint,QCoreApplication
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication,QMessageBox,QSystemTrayIcon,QFrame,QPushButton
from PySide6.QtTest import QTest
from learning_calendar.gui import MainWindow
from learning_calendar.event_popover import EventPopover
from learning_calendar.models import Event
from learning_calendar.checklist_store import ChecklistStore
from learning_calendar.popup_tools import belongs_to,dismiss_on_deactivation

@pytest.fixture
def app():return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app,tmp_path):
    policy=app.quitOnLastWindowClosed();w=MainWindow(tmp_path);w.show();app.processEvents();yield w
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents();app.setQuitOnLastWindowClosed(policy)

def row():return Event('video',1,'수업','movie','영상','2026-11-08T23:59:00+09:00',False)

def test_opening_press_is_not_an_outside_dismissal(window,app):
    point=window.heading.mapToGlobal(QPoint(4,4));popup=window.show_calendar_details(date(2026,11,8),[row()],point)
    event=QMouseEvent(QEvent.Type.MouseButtonPress,QPoint(4,4),point,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
    QCoreApplication.sendEvent(window.heading,event);app.processEvents();assert popup.isVisible()
    QTest.mouseClick(window.heading,Qt.MouseButton.LeftButton,pos=QPoint(25,10));app.processEvents();assert not isValid(popup) or not popup.isVisible()

class NativeDeactivate(QEvent):
    def __init__(self):super().__init__(QEvent.Type.ApplicationDeactivate)
    def spontaneous(self):return True

@pytest.mark.parametrize('active',[True,False])
def test_native_deactivation_waits_for_final_application_focus(app,monkeypatch,active):
    popup=EventPopover(date(2026,11,8),[row()],[],lambda *args:None);popup.show();app.processEvents()
    monkeypatch.setattr(QApplication,'platformName',staticmethod(lambda:'windows'))
    monkeypatch.setattr(QApplication,'applicationState',staticmethod(lambda:Qt.ApplicationState.ApplicationActive if active else Qt.ApplicationState.ApplicationInactive))
    dismiss_on_deactivation(popup,NativeDeactivate());QTest.qWait(130);assert (isValid(popup) and popup.isVisible())==active
    if active:popup.close()
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

def test_native_transient_popup_is_inside_its_owner(app):
    owner=QFrame();owner.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose,False);owner.winId()
    child=QFrame(None,Qt.WindowType.Tool);child.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose,False);child.winId();child.windowHandle().setTransientParent(owner.windowHandle())
    assert child.parent() is None and belongs_to(child,owner)
    child.close();owner.close();child.deleteLater();owner.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

def test_detail_internal_clicks_and_combo_selection_keep_surface(window,app):
    popup=window.show_calendar_details(date(2026,11,8),[row()],window.mapToGlobal(QPoint(200,200)))
    QTest.qWait(120)
    for field in (popup.title,popup.note.viewport()):
        QTest.mouseClick(field,Qt.MouseButton.LeftButton);app.processEvents();assert popup.isVisible()
    popup.type.showPopup();app.processEvents()
    QTest.mouseClick(popup.type.view().viewport(),Qt.MouseButton.LeftButton,pos=popup.type.view().visualRect(popup.type.model().index(0,0)).center())
    app.processEvents();assert popup.isVisible()
    assert popup.grab().toImage().pixelColor(20,20).alpha()==255
    popup.close()

@pytest.mark.parametrize('answer',[QMessageBox.StandardButton.Yes,QMessageBox.StandardButton.Cancel])
def test_row_delete_icon_confirms_and_does_not_open_an_editor(window,app,monkeypatch,answer):
    repo=ChecklistStore(window.store);repo.add(1,'삭제할 할 일');window.show_checklist();window.main_stack._settle();app.processEvents();view=window.checklist;observed=[]
    monkeypatch.setattr(QMessageBox,'question',lambda *args:observed.append(args[2]) or answer)
    index=view.proxy.index(0,7);QTest.mouseClick(view.table.viewport(),Qt.MouseButton.LeftButton,pos=view.table.visualRect(index).center());app.processEvents()
    assert observed==['정말 삭제하시겠습니까?'] and view.popup is None
    assert view.proxy.rowCount()==(0 if answer==QMessageBox.StandardButton.Yes else 1)
    assert not any(button.text()=='휴지통' for button in view.findChildren(QPushButton))
    if answer==QMessageBox.StandardButton.Yes:
        view.refresh();assert view.proxy.rowCount()==0
        view.undo_delete();assert view.proxy.rowCount()==1

def test_close_button_hides_to_tray_and_restore_preserves_window(window,app,monkeypatch):
    monkeypatch.setattr(QSystemTrayIcon,'isSystemTrayAvailable',staticmethod(lambda:True));window.close();app.processEvents()
    assert not window.isVisible() and not window._closed and window._tray.isVisible() and not app.quitOnLastWindowClosed()
    window._restore_from_tray();app.processEvents();assert window.isVisible() and not window._closed
    window.set_notifications(False);assert window._tray.isVisible()

def test_delete_icon_stays_at_right_after_resize(window,app):
    ChecklistStore(window.store).add(1,'할 일');window.show_checklist();window.main_stack._settle()
    for width in (800,1240,1700):
        window.resize(width,800);app.processEvents();window.checklist._fit_columns();view=window.checklist
        rect=view.table.visualRect(view.proxy.index(0,7));assert rect.right()<=view.table.viewport().width() and rect.width()==44

def test_off_day_is_a_colored_full_column_and_restores_classes(window,app):
    from learning_calendar.models import Course
    from learning_calendar.design import colors
    window.store.apply_batch([Course(1,'수업')],{(1,'assignment'):[]});window.store.add_timetable(1,0,'09:00','10:30');window._sessions=window.store.timetable();window._reload();window.select_page(3);window.main_stack._settle();window._set_off_days({0});app.processEvents()
    surface=window.timetable.surface;image=surface.grab().toImage();column=(surface.width()-surface.AXIS)/surface.days
    assert image.pixelColor(round(surface.AXIS+column/2),250).name()==colors()['soft'].lower()
    assert surface.blocks[window._sessions[0]['id']].isHidden() and surface.off_labels[0].isVisible()
    window._set_off_days(set());app.processEvents();assert surface.blocks[window._sessions[0]['id']].isVisible()
