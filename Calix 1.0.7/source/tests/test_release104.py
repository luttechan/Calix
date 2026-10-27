import json,os,subprocess,sys
from pathlib import Path
import pytest
from PySide6.QtCore import QEvent,QCoreApplication,Qt
from PySide6.QtWidgets import QApplication,QLabel
from PySide6.QtTest import QTest
from learning_calendar.gui import MainWindow

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

def test_metric_buttons_measure_caption_and_count_on_both_category_pages(app,tmp_path):
    w=MainWindow(tmp_path);w.resize(1000,720);w.show();app.processEvents()
    for page in (1,2):
        w.select_page(page);w.main_stack._settle();app.processEvents()
        for button,value in zip(w.metric_buttons,('0','123','123456')):
            labels=button.findChildren(QLabel);labels[1].setText(value);button.updateGeometry()
        app.processEvents()
        for button in w.metric_buttons:
            assert button.width()>=94 and button.height()>=36
            for label in button.findChildren(QLabel):
                assert label.width()>=label.fontMetrics().horizontalAdvance(label.text())
                assert button.rect().contains(label.geometry())
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

def test_startup_handoff_waits_for_first_main_window_paint(app):
    from learning_calendar.startup_handoff import StartupHandoff
    class Notice:
        count=0
        def finish(self):self.count+=1
    notice=Notice();w=QLabel('준비된 메인 화면');handoff=StartupHandoff(w,notice)
    QTest.qWait(160);assert notice.count==0
    w.show();app.processEvents();assert notice.count==0 and handoff.painted
    QTest.qWait(180);assert notice.count==1
    w.repaint();QTest.qWait(140);assert notice.count==1
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

def test_diagnostic_or_login_process_does_not_create_a_startup_window(monkeypatch):
    from learning_calendar.startup_notice import start_notice
    monkeypatch.delenv('QT_QPA_PLATFORM',raising=False)
    for flag in ('--login','--connection-check','--smoke-test','--help','-h'):
        notice=start_notice([flag]);assert notice.thread is None and not notice.active
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen');assert start_notice([]).thread is None

@pytest.mark.skipif(sys.platform!='win32',reason='native Windows startup window')
def test_native_startup_is_topmost_before_qt_ignores_close_and_cleans_up():
    root=Path(__file__).parents[1];env=os.environ.copy();env.pop('QT_QPA_PLATFORM',None)
    code=r'''
import sys,time,json,ctypes as c
from ctypes import wintypes as w
sys.path.insert(0,ROOT)
from learning_calendar.startup_notice import start_notice
user=c.WinDLL('user32');kernel=c.WinDLL('kernel32');kernel.GetCurrentProcess.restype=w.HANDLE
user.GetGuiResources.argtypes=[w.HANDLE,w.DWORD];user.GetGuiResources.restype=w.DWORD
before=user.GetGuiResources(kernel.GetCurrentProcess(),0)
notice=start_notice([])
try:
    assert notice.ready.wait(2) and notice.active and not notice.error,notice.error
    initial=notice.native_state();assert initial['visible'] and initial['topmost'],initial
    assert 'PySide6' not in sys.modules and notice.painted_at is not None
    notice._post(notice.hwnd,0x0010,0,0);time.sleep(.12);assert notice.native_state()['visible']
    notice.fail();time.sleep(.12);assert notice.native_state()['visible']
    notice._post(notice.hwnd,0x0111,100,0);assert notice.closed.wait(2)
finally:notice.finish()
after=user.GetGuiResources(kernel.GetCurrentProcess(),0)
assert not notice.thread.is_alive() and notice.hwnd==0,(before,after,notice.error)
# Windows can initialize its stock theme caches over multiple windows. Warm
# those caches, then compare complete open/error/close cycles for growth.
counts=[]
for _ in range(8):
    again=start_notice([])
    try:
        assert again.ready.wait(2) and not again.error,again.error
        again.fail();time.sleep(.12);again._post(again.hwnd,0x0111,100,0);assert again.closed.wait(2)
    finally:again.finish()
    counts.append(user.GetGuiResources(kernel.GetCurrentProcess(),0))
baseline=counts[2]
assert max(counts[3:])<=baseline+1,(before,after,counts)
print(json.dumps({'topmost':initial['topmost'],'before_qt':True,'held_until_ready':True,'failure_remains_visible':True,'gdi_resources_released':True}))
'''.replace('ROOT',repr(str(root)))
    result=subprocess.run([sys.executable,'-B','-c',code],env=env,capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
    assert all(json.loads(result.stdout).values())

def test_startup_images_are_bundled_and_logo_is_preserved(app):
    from PySide6.QtGui import QImage
    root=Path(__file__).parents[1];png=QImage(str(root/'asset/startup.png'));bmp=QImage(str(root/'asset/startup.bmp'))
    assert png.size()==bmp.size() and png.width()==1280 and png.height()==720 and png==bmp
    assert (root/'asset/icons/calix.svg').is_file()
