from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QCheckBox,QComboBox
from .design import THEMES,THEME_NAMES
from .controls import CheckToggle as QCheckBox

class AppearanceDialog(QDialog):
    chosen=Signal(str)
    notifications_changed=Signal(bool)
    glass_changed=Signal(bool)
    font_changed=Signal(str)
    def __init__(self,current,parent=None):
        super().__init__(parent);self.setWindowTitle('화면 테마');self.resize(480,390)
        layout=QVBoxLayout(self);layout.setContentsMargins(26,24,26,24);layout.setSpacing(18)
        title=QLabel('나에게 맞는 분위기');title.setObjectName('heading');layout.addWidget(title)
        note=QLabel('시간표의 수업 색상은 따로 유지됩니다.');note.setObjectName('muted');layout.addWidget(note)
        grid=QGridLayout();grid.setSpacing(12);self.buttons={}
        for i,(key,name) in enumerate(THEME_NAMES.items()):
            c=THEMES[key];button=QPushButton(('✓  ' if key==current else '')+name);button.setMinimumHeight(64);button.setAccessibleName(name+' 테마')
            button.setStyleSheet(f'QPushButton {{background:{c["soft"]};color:{c["ink"]};border:2px solid {c["accent"] if key==current else c["line"]};border-radius:14px;font-weight:600;}}')
            button.clicked.connect(lambda checked=False,k=key:self.pick(k));grid.addWidget(button,i//2,i%2,1,2 if i==4 else 1);self.buttons[key]=button
        layout.addLayout(grid)
        fonts=QHBoxLayout();fonts.addWidget(QLabel('글꼴'));self.font_choice=QComboBox();self.font_choice.addItem('Pretendard','pretendard');self.font_choice.addItem('Windows 기본','windows')
        self.font_choice.setCurrentIndex(max(0,self.font_choice.findData(parent.settings.get('font_mode','pretendard') if parent else 'pretendard')))
        self.font_choice.currentIndexChanged.connect(lambda:self.font_changed.emit(self.font_choice.currentData()));fonts.addWidget(self.font_choice,1);layout.addLayout(fonts)
        glass=QCheckBox('글래스 효과');glass.setChecked(bool(not parent or parent.settings.get('glass',True)));glass.toggled.connect(self.glass_changed);layout.addWidget(glass)
        notify=QCheckBox('앱 실행 중 마감 15분 전 알림');notify.setChecked(bool(parent and parent.settings.get('notifications',False)));notify.toggled.connect(self.notifications_changed);layout.addWidget(notify)
        row=QHBoxLayout();row.addStretch();close=QPushButton('닫기');close.clicked.connect(self.accept);row.addWidget(close);layout.addLayout(row)
    def pick(self,key):self.chosen.emit(key);self.accept()
