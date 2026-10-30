"""Single-click property editing, bound to stable task IDs rather than row positions."""
from datetime import datetime,time
from PySide6.QtCore import Qt,QDate,QTimer,QLocale,Signal
from PySide6.QtWidgets import QLabel,QLineEdit,QPlainTextEdit,QCalendarWidget,QHBoxLayout,QPushButton
from .popup_tools import RoundedPopup
from .controls import TimeInput
from .models import KST,parse_datetime


class FieldPopup(RoundedPopup):
    failed=Signal(str)
    def __init__(self,column,row,choices,save,parent=None):
        super().__init__(parent);self.column=column;self.row=row;self.save_callback=save;self._decided=False;self._committing=False;self.combo=None
        self.setMinimumWidth(320 if column in (1,2,3,4,5) else 280);self.form.setContentsMargins(12,12,12,12);self.form.setSpacing(8);title=QLabel(('할 일','기한','분류','내 역할','담당 교수','상태','비고')[column]);title.setObjectName('fieldLabel');self.form.addWidget(title)
        self.error=QLabel();self.error.setTextFormat(Qt.TextFormat.PlainText);self.error.setObjectName('formError');self.error.setWordWrap(True);self.error.hide()
        if column==1:
            date=parse_datetime(row.get('due_at')) or datetime.now(KST).replace(hour=23,minute=59,second=0,microsecond=0)
            self.date_text=QLineEdit(date.strftime('%Y.%m.%d'));self.date_text.setMaxLength(10);self.date_text.setPlaceholderText('YYYY.MM.DD');self.date_text.setAccessibleName('기한 날짜 입력');self.date_text.setToolTip('날짜 입력 또는 달력에서 선택');self.form.addWidget(self.date_text)
            self.calendar=QCalendarWidget();self.calendar.setLocale(QLocale(QLocale.Language.Korean));self.calendar.setFirstDayOfWeek(Qt.DayOfWeek.Sunday);self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader);self.calendar.setSelectedDate(QDate(date.year,date.month,date.day));self.form.addWidget(self.calendar)
            self.time=TimeInput();from PySide6.QtCore import QTime
            self.time.setTime(QTime(date.hour,date.minute));self.form.addWidget(self.time)
            self.calendar.clicked.connect(lambda day:self.date_text.setText(day.toString('yyyy.MM.dd')))
            self.date_text.editingFinished.connect(self.sync_date)
            self.date_text.returnPressed.connect(self.commit);self.time.lineEdit().returnPressed.connect(self.commit)
            self.focus_input=self.date_text
        elif column in (2,3,4,5):
            from .property_choice import PropertyChoice
            self.combo=PropertyChoice(column!=5);self.combo.setAccessibleName(title.text());self.combo.input.setAccessibleName(title.text());self.combo.options.setAccessibleName(title.text()+' 선택 목록');self.form.addWidget(self.combo)
            if column==5:
                self.combo.set_choices([(state['name'],state['id'],state['color']) for state in choices],row['status_id'])
            else:
                self.combo.set_choices([(value,value,None) for value in choices],str(row.get(('category','role','professor')[column-2]) or ''))
                self.combo.lineEdit().setMaxLength(120 if column==4 else 100)
            self.combo.activated.connect(lambda *_:QTimer.singleShot(0,self,self.commit));self.combo.submitted.connect(self.commit);self.focus_input=self.combo
        else:
            self.input=QPlainTextEdit() if column==6 else QLineEdit();self.input.setAccessibleName(title.text())
            value=str(row.get('note' if column==6 else 'title') or '')
            if column==6:self.input.setPlainText(value);self.input.setMinimumHeight(130)
            else:self.input.setMaxLength(200);self.input.setText(value);self.input.returnPressed.connect(self.commit)
            self.form.addWidget(self.input);self.focus_input=self.input
        self.form.addWidget(self.error);actions=QHBoxLayout()
        if column==1:
            clear=QPushButton('기한 없음');clear.clicked.connect(lambda:self.commit_value(''));actions.addWidget(clear)
        cancel=QPushButton('취소');cancel.setAutoDefault(False);cancel.clicked.connect(self.reject);actions.addStretch();actions.addWidget(cancel)
        save_button=QPushButton('저장');save_button.setObjectName('primary');save_button.setAutoDefault(False);save_button.clicked.connect(self.commit);actions.addWidget(save_button);self.form.addLayout(actions)
        from PySide6.QtGui import QShortcut,QKeySequence
        QShortcut(QKeySequence('Ctrl+Return'),self,activated=self.commit);save_button.setToolTip('저장 (Ctrl+Enter)')
    def showEvent(self,event):
        super().showEvent(event);self.focus_input.setFocus()
        if self.combo and self.combo.count():QTimer.singleShot(0,self,self.combo.showPopup)
        elif isinstance(self.focus_input,QLineEdit):self.focus_input.selectAll()
    def sync_date(self):
        value=self.read_date()
        if value:self.calendar.setSelectedDate(value)
    def read_date(self):
        text=self.date_text.text().strip()
        for fmt in ('yyyy.MM.dd','yyyy-MM-dd','yyyy/MM/dd'):
            value=QDate.fromString(text,fmt)
            if value.isValid():return value
        return None
    def value(self):
        if self.column==1:
            date=self.read_date();clock=self.time.time()
            if not date:raise ValueError('날짜를 YYYY.MM.DD 형식으로 입력하세요.')
            if not clock.isValid():raise ValueError('시간을 00:00~23:59로 입력하세요.')
            return datetime.combine(date.toPython(),time(clock.hour(),clock.minute()),KST).isoformat()
        if self.combo:return self.combo.currentData() if self.column==5 else self.combo.currentText()
        return self.input.toPlainText() if self.column==6 else self.input.text()
    def commit_value(self,value):
        if self._committing or self._decided:return
        self._committing=True
        try:
            if self.save_callback(value):
                self._decided=True
                if self.combo:self.combo.hidePopup()
                self.accept()
            else:self.error.setText('저장 내용을 확인하세요.');self.error.show()
        finally:self._committing=False
    def commit(self):
        try:self.commit_value(self.value())
        except ValueError as exc:self.error.setText(str(exc));self.error.show()
    def reject(self):self._decided=True;super().reject()
    def closeEvent(self,event):
        if not self._decided:
            try:self.save_callback(self.value())
            except ValueError as exc:self.failed.emit(str(exc))
            self._decided=True
        super().closeEvent(event)
