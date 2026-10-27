from PySide6.QtCore import Qt,QEvent,QCoreApplication
from PySide6.QtWidgets import QApplication,QWidget,QDialog,QVBoxLayout,QLineEdit
from PySide6.QtTest import QTest
from learning_calendar.ready_dialogs import ReadyDialogs,NAMES
from learning_calendar.gui import MainWindow
from learning_calendar.fonts import apply_korean_font
from learning_calendar import dialogs


def collect(app):
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()


def test_prepared_dialogs_are_single_use_and_bounded():
    app=QApplication.instance() or QApplication([]);root=QWidget();root.settings={'glass':True};root.theme_key='sky';created=[]
    def factory(name):
        dialog=QDialog(root);dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True)
        dialog.field=QLineEdit();QVBoxLayout(dialog).addWidget(dialog.field);created.append(dialog);return dialog
    ready=ReadyDialogs(factory,root);ready.prime();assert len(ready.cache)==len(NAMES)
    used=ready.take('settings');used.field.setText('synthetic private draft')
    ready.prepare('settings');fresh=ready.take('settings')
    assert fresh is not used and fresh.field.text()==''
    assert len(ready.cache)==len(NAMES)-1
    used.deleteLater();fresh.deleteLater();ready.shutdown();root.deleteLater();collect(app)


def test_stale_rebuilds_and_shutdown_cannot_recreate_dialogs():
    app=QApplication.instance() or QApplication([]);root=QWidget();root.settings={};root.theme_key='sky';calls=[]
    def factory(name):calls.append(name);dialog=QDialog(root);dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);return dialog
    ready=ReadyDialogs(factory,root);ready.prime();ready.invalidate();ready.invalidate();ready.shutdown()
    previous=len(calls);QTest.qWait(300)
    assert not ready.cache and len(calls)==previous
    root.deleteLater();collect(app)


def test_isolated_startup_prepares_menus_without_reading_real_account(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([]);apply_korean_font(app)
    def forbidden():raise AssertionError('diagnostics must not read real saved accounts')
    monkeypatch.setattr(dialogs,'read_account',forbidden)
    window=MainWindow(tmp_path);window.prepare_navigation()
    assert window.main_stack.currentIndex()==0 and window.diary.vault is None
    assert set(window._ready_dialogs.cache)==set(NAMES)
    assert all(not dialog.isVisible() for dialog in window._ready_dialogs.cache.values())
    assert window._ready_dialogs.cache['settings'].student.text()==''
    settings=window._take_ready_dialog('settings');settings.password.setText('synthetic private password');settings.reject()
    assert settings.password.text()==''
    settings.deleteLater();window.dispose();window.deleteLater();collect(app)
