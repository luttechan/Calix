"""Keep the early image until the real window has painted a complete frame."""
from PySide6.QtCore import QObject,QEvent,QTimer


class StartupHandoff(QObject):
    def __init__(self,window,notice):
        super().__init__(window);self.notice=notice;self.painted=False;self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(120);self.timer.timeout.connect(self.finish);window.installEventFilter(self)
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.Paint and not self.painted:self.painted=True;self.timer.start()
        return False
    def finish(self):
        self.timer.stop();self.notice.finish();self.deleteLater()
