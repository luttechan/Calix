from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (QDialog,QLineEdit,QPushButton,QFormLayout,QHBoxLayout,QVBoxLayout,QLabel,QMessageBox,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QComboBox,QTimeEdit,QPlainTextEdit,QSizePolicy)
from .preferences import read_account, store_account
from .models import Event
DAYS = ['월','화','수','목','금','토','일']


def label(text: str, style: str = '') -> QLabel:
    out = QLabel(text)
    out.setTextFormat(Qt.TextFormat.PlainText)
    if style: out.setObjectName(style)
    out.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    return out

def ellipsis(text: str, max_chars=110):
    return text if len(text) <= max_chars else text[:max_chars-1] + '…'

def when(e: Event):
    return e.due.strftime('%m/%d %H:%M') if e.due else '기한 없음'

class SettingsDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle('계정 설정');self.resize(460,440)
        try:student=read_account()
        except Exception:student=''
        layout=QVBoxLayout(self);layout.setContentsMargins(28,26,28,24);layout.setSpacing(16)
        layout.addWidget(label('계정 연결','heading'));layout.addWidget(label('부산외대 Canvas','muted'))
        layout.addWidget(label('학교 ID','fieldLabel'));self.student=QLineEdit(student);self.student.setPlaceholderText('학번 또는 학교 ID');layout.addWidget(self.student)
        layout.addWidget(label('비밀번호','fieldLabel'));self.password=QLineEdit();self.password.setEchoMode(QLineEdit.EchoMode.Password);self.password.setPlaceholderText('변경할 때만 입력');layout.addWidget(self.password)
        note=label('Windows 자격 증명 관리자에 보관됩니다.','caption');note.setWordWrap(True);layout.addWidget(note)
        self.error=label('','formError');self.error.setWordWrap(True);layout.addWidget(self.error);layout.addStretch()
        actions=QHBoxLayout();actions.addStretch();cancel=QPushButton('취소');cancel.clicked.connect(self.reject);save=QPushButton('저장');save.setObjectName('primary');save.clicked.connect(self.save);actions.addWidget(cancel);actions.addWidget(save);layout.addLayout(actions)
    def save(self):
        student=self.student.text().strip()
        if not student:self.error.setText('학교 ID를 입력하세요.');return
        try:store_account(student,self.password.text() or None)
        except Exception:self.error.setText('계정을 저장하지 못했습니다.');return
        self.accept()

class AliasDialog(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent); self.store=store
        self.setWindowTitle('과목 이름'); self.resize(660,510)
        self.table=QTableWidget(0,2)
        self.table.setHorizontalHeaderLabels(['원래 과목명','표시할 이름'])
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False);self.table.verticalHeader().setDefaultSectionSize(44);self.table.setShowGrid(False);self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setRowCount(len(store.all_course_details()))
        for row,c in enumerate(store.all_course_details()):
            orig=QTableWidgetItem(c['name'])
            orig.setFlags(orig.flags() & ~Qt.ItemFlag.ItemIsEditable)
            orig.setData(Qt.ItemDataRole.UserRole,c['id'])
            self.table.setItem(row,0,orig)
            self.table.setItem(row,1,QTableWidgetItem(c['alias']))
        save=QPushButton('저장');save.setObjectName('primary'); save.clicked.connect(self.save)
        done=QPushButton('닫기');done.clicked.connect(self.reject)
        row=QHBoxLayout();row.addStretch();row.addWidget(done);row.addWidget(save)
        layout=QVBoxLayout(self);layout.setContentsMargins(26,24,26,24);layout.setSpacing(16);layout.addWidget(label('읽기 좋은 과목 이름','heading'));layout.addWidget(label('비워 두면 원래 이름으로 표시됩니다.','muted'))
        layout.addWidget(self.table,1);layout.addLayout(row)

    def save(self):
        for row in range(self.table.rowCount()):
            self.store.set_alias(self.table.item(row,0).data(Qt.ItemDataRole.UserRole),
                                 self.table.item(row,1).text() if self.table.item(row,1) else '')
        self.accept()

from .timetable_view import SessionEditor as SessionDialog

class MemoDialog(QDialog):
    def __init__(self,e,parent=None):
        super().__init__(parent);self.setWindowTitle('일정 메모');self.resize(500,390)
        layout=QVBoxLayout(self);layout.setContentsMargins(26,24,26,24);layout.setSpacing(14)
        title=label(ellipsis(e.title,70),'section');title.setWordWrap(True);layout.addWidget(title)
        layout.addWidget(label(e.course_name+' / '+when(e),'muted'))
        self.edit=QPlainTextEdit(e.note);self.edit.setPlaceholderText('기억할 내용을 남겨보세요.');layout.addWidget(self.edit,1)
        actions=QHBoxLayout();actions.addStretch();cancel=QPushButton('취소');cancel.clicked.connect(self.reject);save=QPushButton('저장');save.setObjectName('primary');save.clicked.connect(self.accept);actions.addWidget(cancel);actions.addWidget(save);layout.addLayout(actions)
