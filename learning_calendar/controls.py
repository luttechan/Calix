"""Shared precise time steppers and a compact, themed calendar picker."""
from PySide6.QtCore import Qt,QDate,QTime,QSize,QLocale,Signal,QEvent,QRegularExpression,QRect
from PySide6.QtWidgets import QTimeEdit,QSpinBox,QAbstractSpinBox,QToolButton,QPushButton,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QCalendarWidget,QCheckBox,QStyleOptionButton,QStyle,QFrame,QLineEdit
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

class TimeInput(QFrame):
    timeChanged=Signal(QTime)
    def __init__(self,value=QTime(23,59),parent=None):
        super().__init__(parent);self.setObjectName('timeInput');self.setMinimumSize(115,38)
        from PySide6.QtGui import QRegularExpressionValidator
        self.editor=QLineEdit(self);self.editor.setValidator(QRegularExpressionValidator(QRegularExpression('[0-9:]{0,5}'),self.editor));self.editor.setMaxLength(5)
        self.editor.setStyleSheet('border:0;padding:0;background:transparent;min-height:0;');self.editor.setPlaceholderText('HH:MM');self.editor.setAccessibleName('시간 입력');self.editor.setToolTip('시간 입력 (예: 09:30)');self.editor.installEventFilter(self);self.setFocusProxy(self.editor)
        self._last=QTime(23,59);self.editor.textChanged.connect(self._changed);self.editor.editingFinished.connect(self.normalize)
        self.up=QToolButton(self);self.down=QToolButton(self)
        for button,name,label,step in ((self.up,'up','15분 뒤',15),(self.down,'down','15분 앞',-15)):
            button.setObjectName('timeStep');button.setIcon(icon(name));button.setIconSize(QSize(12,12));button.setToolTip(label);button.setAccessibleName(label)
            button.setCursor(Qt.CursorShape.PointingHandCursor);button.setFocusPolicy(Qt.FocusPolicy.NoFocus);button.clicked.connect(lambda checked=False,s=step:self.step_minutes(s))
        self.setTime(value)
    def lineEdit(self):return self.editor
    def text(self):return self.editor.text()
    def setDisplayFormat(self,value):pass
    def setButtonSymbols(self,value):pass
    def time(self):
        raw=self.editor.text().strip()
        if ':' in raw:
            parts=raw.split(':')
            if len(parts)!=2 or any(not p.isdigit() or len(p)>2 for p in parts):return QTime()
            hour,minute=map(int,parts)
        elif raw.isdigit() and len(raw)<=4:
            hour,minute=(int(raw),0) if len(raw)<=2 else (int(raw[:-2]),int(raw[-2:]))
        else:return QTime()
        return QTime(hour,minute) if 0<=hour<24 and 0<=minute<60 else QTime()
    def setTime(self,value):
        if not isinstance(value,QTime) or not value.isValid():return
        self.editor.setText(value.toString('HH:mm'));self._changed()
    def normalize(self):
        value=self.time()
        if value.isValid():self.setTime(value)
    def _changed(self,*args):
        value=self.time();self.setProperty('invalid',not value.isValid())
        self.style().unpolish(self);self.style().polish(self)
        if value.isValid() and value!=self._last:self._last=QTime(value);self.timeChanged.emit(value)
        self._buttons()
    def eventFilter(self,obj,event):
        if obj is self.editor and event.type()==QEvent.Type.KeyPress and not self.editor.hasSelectedText():
            cursor=self.editor.cursorPosition();value=self.editor.text()
            if event.key()==Qt.Key.Key_Backspace and cursor>1 and value[cursor-1:cursor]==':':
                self.editor.setSelection(cursor-2,1);self.editor.del_();return True
            if event.key()==Qt.Key.Key_Delete and value[cursor:cursor+1]==':' and cursor+1<len(value):
                self.editor.setSelection(cursor+1,1);self.editor.del_();return True
        if obj is self.editor and event.type()==QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Up,Qt.Key.Key_Down):self.step_minutes(15 if event.key()==Qt.Key.Key_Up else -15);return True
        return super().eventFilter(obj,event)
    def step_minutes(self,step):
        value=self.time() if self.time().isValid() else self._last
        total=max(0,min(1439,value.hour()*60+value.minute()+step));self.setTime(QTime(total//60,total%60))
    def _buttons(self,*args):
        if not hasattr(self,'up'):return
        value=self.time() if self.time().isValid() else self._last;total=value.hour()*60+value.minute();self.up.setEnabled(total<1439);self.down.setEnabled(total>0)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'up'):
            half=max(12,(self.height()-6)//2);self.up.setGeometry(self.width()-29,3,24,half);self.down.setGeometry(self.width()-29,3+half,24,half)
            # Qt 6.12's stylesheet spinbox geometry collapses the native editor
            # to 1 px with NoButtons. Keep its text area explicitly bounded.
            self.lineEdit().setGeometry(11,5,max(1,self.width()-47),max(1,self.height()-10))
    def wheelEvent(self,event):
        if self.editor.hasFocus():self.step_minutes(15 if event.angleDelta().y()>0 else -15);event.accept()
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
        from .popup_tools import RoundedPopup,place_popup
        popup=RoundedPopup(self);self.popup=popup;token=id(popup)
        def clear(*args):
            if self.popup is not None and id(self.popup)==token:self.popup=None
        popup.finished.connect(clear);popup.destroyed.connect(clear)
        layout=popup.form
        cal=QCalendarWidget();cal.setLocale(QLocale(QLocale.Language.Korean));cal.setFirstDayOfWeek(Qt.DayOfWeek.Sunday);cal.setNavigationBarVisible(False)
        cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader);cal.setSelectedDate(self._date)
        row=QHBoxLayout();month=QLabel();month.setObjectName('section');row.addWidget(month,1)
        for label,action in (('‹',cal.showPreviousMonth),('›',cal.showNextMonth)):
            b=QPushButton(label);b.setFixedSize(30,30);b.setObjectName('zoomButton');b.setAccessibleName('이전 달' if label=='‹' else '다음 달');b.setToolTip(b.accessibleName());b.clicked.connect(action);row.addWidget(b)
        def update(*args):month.setText(f'{cal.yearShown()}년 {cal.monthShown()}월')
        cal.currentPageChanged.connect(update);update();layout.addLayout(row);layout.addWidget(cal)
        def choose(value):self.setDate(value);popup.close()
        cal.clicked.connect(choose);today=QPushButton('오늘');today.clicked.connect(lambda:choose(QDate.currentDate()));layout.addWidget(today)
        from .popup_tools import add_hints
        add_hints(popup);popup.setMinimumWidth(310);place_popup(popup,QRect(self.mapToGlobal(self.rect().topLeft()),self.size()));popup.show()

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
