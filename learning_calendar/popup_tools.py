"""Bounded native popups and consistent hover/accessibility labels."""
from PySide6.QtCore import Qt,QPoint,QRectF,QEvent,QTimer
from PySide6.QtGui import QPainterPath,QRegion,QGuiApplication
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFrame,QApplication,QAbstractButton,QWidget,QComboBox,QLineEdit,QPlainTextEdit
from .design import colors


def belongs_to(obj,owner):
    # QWidget.isAncestorOf excludes child windows such as combo popup lists.
    # Their QObject ownership chain still identifies them as internal controls.
    while obj is not None:
        if obj is owner:return True
        obj=obj.parent()
    return False


def dismiss_on_deactivation(widget,event):
    # Headless Qt emits platform focus changes without a real user/window.
    # Explicit events remain testable; desktop focus loss always dismisses.
    if QApplication.platformName()=='offscreen' and event.spontaneous():return
    QTimer.singleShot(0,widget,widget.close)


def round_window(widget,radius=16):
    path=QPainterPath();path.addRoundedRect(QRectF(widget.rect()),radius,radius)
    widget.setMask(QRegion(path.toFillPolygon().toPolygon()))


def place_popup(widget,anchor):
    screen=QGuiApplication.screenAt(anchor.bottomLeft()) or widget.screen();area=screen.availableGeometry();widget.adjustSize()
    widget.resize(min(widget.width(),area.width()-16),min(widget.height(),area.height()-16))
    x=anchor.left();y=anchor.bottom()+6
    if y+widget.height()>area.bottom()-8:y=anchor.top()-widget.height()-6
    widget.move(max(area.left()+8,min(x,area.right()-widget.width()-7)),max(area.top()+8,min(y,area.bottom()-widget.height()-7)))


def add_hints(root):
    for button in root.findChildren(QAbstractButton):
        name=button.accessibleName() or button.text().replace('&','').strip()
        if not name:continue
        if not button.accessibleName():button.setAccessibleName(name)
        hint=button.toolTip()
        if not hint:button.setToolTip(name)
        elif hint.startswith(('Ctrl+','Alt+','Shift+')):button.setToolTip(name+' ('+hint+')')
    for kind in (QLineEdit,QComboBox,QPlainTextEdit):
        for field in root.findChildren(kind):
            name=field.accessibleName() or (field.placeholderText() if isinstance(field,QLineEdit) else '')
            if name and not field.toolTip():field.setToolTip(name)


class RoundedPopup(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent,Qt.WindowType.Popup|Qt.WindowType.FramelessWindowHint)
        self.setObjectName('floatingEditor');self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground);self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose,False)
        c=colors();self.setStyleSheet(f'QDialog#floatingEditor {{background:transparent;}} QFrame#popupBody {{background:{c["surface"]};border:1px solid {c["line"]};border-radius:15px;}}')
        outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0);self.body=QFrame();self.body.setObjectName('popupBody');outer.addWidget(self.body)
        self.form=QVBoxLayout(self.body);self.form.setContentsMargins(16,14,16,14);self.form.setSpacing(10)
        self._watching=False
    def showEvent(self,event):
        super().showEvent(event);round_window(self,15);add_hints(self)
        if not self._watching:QApplication.instance().installEventFilter(self);self._watching=True
    def resizeEvent(self,event):super().resizeEvent(event);round_window(self,15)
    def hideEvent(self,event):
        if self._watching:QApplication.instance().removeEventFilter(self);self._watching=False
        super().hideEvent(event)
    def eventFilter(self,obj,event):
        if not self.isVisible():return False
        if event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Escape:
            active=QApplication.activePopupWidget()
            if belongs_to(obj,self) or active and belongs_to(active,self):self.reject();return True
        if event.type()==QEvent.Type.ApplicationDeactivate:dismiss_on_deactivation(self,event)
        elif event.type()==QEvent.Type.MouseButtonPress and isinstance(obj,QWidget) and not belongs_to(obj,self):self.close()
        return False
    def reject(self):
        for combo in self.findChildren(QComboBox):combo.hidePopup()
        super().reject()
