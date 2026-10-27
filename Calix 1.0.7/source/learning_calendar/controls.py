"""Shared precise time steppers and a compact, themed calendar picker."""
from PySide6.QtCore import Qt,QDate,QTime,QSize,QLocale,Signal
from PySide6.QtWidgets import QTimeEdit,QSpinBox,QAbstractSpinBox,QToolButton,QPushButton,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QCalendarWidget,QCheckBox,QStyleOptionButton,QStyle
from .design import icon

class CheckToggle(QCheckBox):
    """Native checkbox label with a clear shape-only indicator."""
    def paintEvent(self,event):
        from PySide6.QtGui import QPainter
        from .check_indicator import paint_check
        from .design import colors
        option=QStyleOptionButton();self.initStyleOption(option);painter=QPainter(self)
        rect=self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator,option,self)
        text_option=QStyleOptionButton(option);text_option.rect=self.style().subElementRect(QStyle.SubElement.SE_CheckBoxContents,option,self)
        self.style().drawControl(QStyle.ControlElement.CE_CheckBoxLabel,text_option,painter,self)
        paint_check(painter,rect,self.isChecked(),colors());painter.end()

class TimeInput(QTimeEdit):
    def __init__(self,value=QTime(23,59),parent=None):
        super().__init__(value,parent);self.setObjectName('timeInput');self.setDisplayFormat('HH:mm');self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons);self.setMinimumWidth(115)
        self.lineEdit().setStyleSheet('border:0;padding:0;background:transparent;min-height:0;')
        self.up=QToolButton(self);self.down=QToolButton(self)
        for button,name,label,step in ((self.up,'up','15분 뒤',15),(self.down,'down','15분 앞',-15)):
            button.setObjectName('timeStep');button.setIcon(icon(name));button.setIconSize(QSize(12,12));button.setToolTip(label);button.setAccessibleName(label)
            button.setCursor(Qt.CursorShape.PointingHandCursor);button.setFocusPolicy(Qt.FocusPolicy.NoFocus);button.clicked.connect(lambda checked=False,s=step:self.step_minutes(s))
        self.timeChanged.connect(self._buttons);self._buttons()
    def step_minutes(self,step):
        total=max(0,min(1439,self.time().hour()*60+self.time().minute()+step));self.setTime(QTime(total//60,total%60))
    def _buttons(self,*args):
        total=self.time().hour()*60+self.time().minute();self.up.setEnabled(total<1439);self.down.setEnabled(total>0)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'up'):
            half=max(12,(self.height()-6)//2);self.up.setGeometry(self.width()-29,3,24,half);self.down.setGeometry(self.width()-29,3+half,24,half)
            # Qt 6.12's stylesheet spinbox geometry collapses the native editor
            # to 1 px with NoButtons. Keep its text area explicitly bounded.
            self.lineEdit().setGeometry(11,5,max(1,self.width()-47),max(1,self.height()-10))
    def wheelEvent(self,event):
        if self.hasFocus():super().wheelEvent(event)
        else:event.ignore()

class DateInput(QPushButton):
    changed=Signal(object)
    def __init__(self,value=None,parent=None):
        super().__init__(parent);self.setObjectName('dateInput');self._date=value or QDate.currentDate();self.popup=None
        self.setAccessibleName('기한 날짜');self.setCursor(Qt.CursorShape.PointingHandCursor);self.setDate(self._date);self.clicked.connect(self._open)
    def date(self):return self._date
    def setDate(self,value):self._date=value;self.setText(value.toString('yyyy.MM.dd'));self.changed.emit(value)
    def _open(self):
        if self.popup:self.popup.close();return
        popup=QDialog(self,Qt.WindowType.Popup);self.popup=popup;popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose);popup.destroyed.connect(lambda:setattr(self,'popup',None))
        layout=QVBoxLayout(popup);layout.setContentsMargins(14,12,14,12);layout.setSpacing(10)
        cal=QCalendarWidget();cal.setLocale(QLocale(QLocale.Language.Korean));cal.setFirstDayOfWeek(Qt.DayOfWeek.Sunday);cal.setNavigationBarVisible(False)
        cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader);cal.setSelectedDate(self._date)
        row=QHBoxLayout();month=QLabel();month.setObjectName('section');row.addWidget(month,1)
        for label,action in (('‹',cal.showPreviousMonth),('›',cal.showNextMonth)):
            b=QPushButton(label);b.setFixedSize(30,30);b.setObjectName('zoomButton');b.clicked.connect(action);row.addWidget(b)
        def update(*args):month.setText(f'{cal.yearShown()}년 {cal.monthShown()}월')
        cal.currentPageChanged.connect(update);update();layout.addLayout(row);layout.addWidget(cal)
        def choose(value):self.setDate(value);popup.close()
        cal.clicked.connect(choose);today=QPushButton('오늘');today.clicked.connect(lambda:choose(QDate.currentDate()));layout.addWidget(today)
        popup.resize(310,310);popup.move(self.mapToGlobal(self.rect().bottomLeft()));popup.show()

class CountInput(QSpinBox):
    def __init__(self,parent=None):
        super().__init__(parent);self.setObjectName('countInput');self.setRange(2,52);self.setValue(4);self.setSuffix('회');self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons);self.setMinimumWidth(90)
        self.lineEdit().setStyleSheet('border:0;padding:0;background:transparent;min-height:0;')
        self.up=QToolButton(self);self.down=QToolButton(self)
        for button,name,step in ((self.up,'up',1),(self.down,'down',-1)):
            button.setObjectName('timeStep');button.setIcon(icon(name));button.setIconSize(QSize(12,12));button.setAccessibleName('반복 횟수 '+('증가' if step>0 else '감소'));button.setToolTip(button.accessibleName());button.setFocusPolicy(Qt.FocusPolicy.NoFocus);button.clicked.connect(lambda checked=False,s=step:self.setValue(self.value()+s))
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'up'):
            half=max(12,(self.height()-6)//2);self.up.setGeometry(self.width()-29,3,24,half);self.down.setGeometry(self.width()-29,3+half,24,half)
            self.lineEdit().setGeometry(11,5,max(1,self.width()-47),max(1,self.height()-10))
    def wheelEvent(self,event):
        if self.hasFocus():super().wheelEvent(event)
        else:event.ignore()
