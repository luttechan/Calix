"""Native holiday manager. Personal choices always override the bundled table."""
import calendar as month_calendar
from PySide6.QtCore import Qt,QDate,QUrl,Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QLineEdit,QPushButton
from .controls import DateInput
from .holidays import SOURCE_URL
from .text_safety import tooltip_text

def label(value,name='muted'):
    item=QLabel(value);item.setObjectName(name);item.setTextFormat(Qt.TextFormat.PlainText);return item

class HolidayDialog(QDialog):
    changed=Signal()
    def __init__(self,calendar,selected,parent=None):
        super().__init__(parent);self.calendar=calendar;self.setWindowTitle('공휴일');self.resize(650,680);self.loading=False
        outer=QVBoxLayout(self);outer.setContentsMargins(24,22,24,22);outer.setSpacing(12)
        head=QHBoxLayout();head.addWidget(label('공휴일','heading'));head.addStretch();self.year=QComboBox();self.year.setAccessibleName('공휴일 연도')
        for year in sorted(set(range(2020,2051))|{selected.year}):self.year.addItem(f'{year}년',year)
        self.year.setCurrentIndex(self.year.findData(selected.year));head.addWidget(self.year);outer.addLayout(head)
        self.hint=label('기본 공휴일에 임시공휴일을 더할 수 있습니다.');self.hint.setWordWrap(True);outer.addWidget(self.hint)
        self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels(['날짜','이름','구분']);self.table.verticalHeader().hide();self.table.setShowGrid(False);self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents);self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch);self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents);self.table.verticalHeader().setDefaultSectionSize(38);self.table.setAccessibleName('공휴일 목록');outer.addWidget(self.table,1)
        fields=QHBoxLayout();self.day=DateInput(QDate(selected.year,selected.month,selected.day));self.day.setAccessibleName('공휴일 날짜');self.day.setMinimumWidth(150);fields.addWidget(self.day)
        self.name=QLineEdit();self.name.setMaxLength(80);self.name.setPlaceholderText('공휴일 이름');self.name.setAccessibleName('공휴일 이름');fields.addWidget(self.name,1);outer.addLayout(fields)
        self.enabled=QPushButton('공휴일로 표시');self.enabled.setObjectName('segment');self.enabled.setCheckable(True);self.enabled.setChecked(True);self.enabled.setAutoDefault(False);self.enabled.setMaximumWidth(180);self.enabled.toggled.connect(self.enabled_text);outer.addWidget(self.enabled)
        self.status=label('직접 설정한 내용은 동기화해도 유지됩니다.');self.status.setWordWrap(True);outer.addWidget(self.status)
        actions=QHBoxLayout();self.new=QPushButton('추가');self.new.clicked.connect(self.new_entry);actions.addWidget(self.new)
        self.reset=QPushButton('기본으로');self.reset.setToolTip('직접 추가한 날짜는 삭제하고 기본 날짜는 원래대로 돌립니다.');self.reset.clicked.connect(self.reset_entry);actions.addWidget(self.reset);actions.addStretch()
        self.save=QPushButton('저장');self.save.setObjectName('primary');self.save.setDefault(True);self.save.clicked.connect(self.save_entry);actions.addWidget(self.save);close=QPushButton('닫기');close.clicked.connect(self.accept);actions.addWidget(close);outer.addLayout(actions)
        for button in (self.new,self.reset,close):button.setAutoDefault(False)
        footer=QHBoxLayout();source=QPushButton('공휴일 자료');source.setObjectName('ghost');source.setAutoDefault(False);source.clicked.connect(lambda:QDesktopServices.openUrl(QUrl(SOURCE_URL)));footer.addWidget(source)
        footer.addStretch();outer.addLayout(footer)
        outer.addWidget(label('기본 공휴일 2020–2050','caption'))
        self.year.currentIndexChanged.connect(self.year_changed);self.table.itemSelectionChanged.connect(self.select);self.day.changed.connect(self.date_changed)
        self.populate();self.date_changed(self.day.date())
    def enabled_text(self,value):self.enabled.setText('공휴일로 표시' if value else '공휴일 표시 안 함')
    def year_changed(self,*args):
        value=self.day.date();year=self.year.currentData();self.day.setDate(QDate(year,value.month(),min(value.day(),month_calendar.monthrange(year,value.month())[1])));self.populate()
    def populate(self,*args):
        self.loading=True;self.rows=self.calendar.entries(self.year.currentData());self.table.setRowCount(len(self.rows))
        for i,row in enumerate(self.rows):
            for j,key in enumerate(('day','name','source')):
                item=QTableWidgetItem(row[key]);item.setToolTip(tooltip_text(row[key]));self.table.setItem(i,j,item)
        self.loading=False
        self.hint.setText('기본 공휴일에 임시공휴일을 더할 수 있습니다.' if self.calendar.has_year(self.year.currentData()) else '이 연도는 기본 자료가 없습니다. 직접 추가할 수 있습니다.')
    def select(self):
        if self.loading or self.table.currentRow()<0:return
        row=self.rows[self.table.currentRow()];self.loading=True;self.day.setDate(QDate.fromString(row['day'],'yyyy-MM-dd'));self.name.setText(row['name']);self.enabled.setChecked(bool(row['enabled']));self.reset.setEnabled(row['custom']);self.loading=False
    def date_changed(self,value):
        if self.loading:return
        day=value.toString('yyyy-MM-dd');custom=self.calendar.overrides.get(day);name=self.calendar.defaults(value.year()).get(day,'')
        self.name.setText(custom['name'] if custom else name);self.enabled.setChecked(bool(custom['enabled']) if custom else True);self.reset.setEnabled(custom is not None)
    def new_entry(self):
        self.table.clearSelection();self.name.clear();self.enabled.setChecked(True);self.name.setFocus()
    def save_entry(self):
        try:self.calendar.save(self.day.date().toString('yyyy-MM-dd'),self.name.text(),self.enabled.isChecked())
        except (ValueError,OSError,__import__('sqlite3').Error) as exc:self.status.setText(str(exc) if isinstance(exc,ValueError) else '저장하지 못했습니다. 다시 시도하세요.');return
        year=self.day.date().year()
        if self.year.findData(year)<0:self.year.addItem(f'{year}년',year)
        self.year.setCurrentIndex(self.year.findData(year));self.populate();self.date_changed(self.day.date());self.status.setText('저장됨');self.changed.emit()
    def reset_entry(self):
        try:self.calendar.reset(self.day.date().toString('yyyy-MM-dd'))
        except (ValueError,OSError,__import__('sqlite3').Error):self.status.setText('변경하지 못했습니다. 다시 시도하세요.');return
        self.populate();self.date_changed(self.day.date());self.status.setText('기본 설정으로 돌아갔습니다.');self.changed.emit()
