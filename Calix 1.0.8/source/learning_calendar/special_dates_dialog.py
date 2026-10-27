"""Optional calendar annotations, independent of public holidays and tasks."""
import sqlite3
from PySide6.QtCore import Qt,QUrl,Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton
from .controls import CheckToggle


class SpecialDatesDialog(QDialog):
    changed=Signal()
    def __init__(self,calendar,parent=None):
        super().__init__(parent);self.calendar=calendar;self.setWindowTitle('특수 일정 등록');self.setMinimumWidth(390)
        outer=QVBoxLayout(self);outer.setContentsMargins(24,22,24,22);outer.setSpacing(16)
        heading=QLabel('특수 일정 등록');heading.setObjectName('heading');outer.addWidget(heading)
        self.catholic=CheckToggle('가톨릭 일정');self.catholic.setChecked(calendar.catholic_enabled);self.catholic.setAccessibleName('가톨릭 일정');self.catholic.setToolTip('성인 축일과 선택 기념일 포함 / 2020–2027년');self.catholic.toggled.connect(self.toggle_catholic);outer.addWidget(self.catholic)
        self.mystery=CheckToggle('???');self.mystery.setChecked(calendar.birthday_enabled);self.mystery.setAccessibleName('???');self.mystery.toggled.connect(self.toggle_birthday);outer.addWidget(self.mystery)
        self.status=QLabel('선택한 일정은 달력에 표시됩니다.');self.status.setObjectName('muted');self.status.setTextFormat(Qt.TextFormat.PlainText);self.status.setWordWrap(True);outer.addWidget(self.status)
        actions=QHBoxLayout();source=QPushButton('전례력');source.setObjectName('ghost');source.setAutoDefault(False);source.clicked.connect(self.open_source);actions.addWidget(source);actions.addStretch()
        close=QPushButton('닫기');close.setDefault(True);close.clicked.connect(self.accept);actions.addWidget(close);outer.addLayout(actions)
    def toggle_catholic(self,enabled):self.save_option(self.catholic,self.calendar.set_catholic,'catholic_enabled',enabled)
    def toggle_birthday(self,enabled):self.save_option(self.mystery,self.calendar.set_birthday,'birthday_enabled',enabled)
    def save_option(self,widget,save,attribute,enabled):
        try:save(enabled)
        except (OSError,sqlite3.Error):
            widget.blockSignals(True);widget.setChecked(getattr(self.calendar,attribute));widget.blockSignals(False);self.status.setText('저장하지 못했습니다. 다시 시도하세요.');return
        self.status.setText('저장됨');self.changed.emit()
    def open_source(self):QDesktopServices.openUrl(QUrl('https://missa.cbck.or.kr/Liturgy'))
