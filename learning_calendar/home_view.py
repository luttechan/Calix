"""Animated welcome screen and reversible native page transitions."""
import math
from datetime import datetime
from PySide6.QtCore import (Qt,QTimer,QPoint,QRect,QPointF,QRectF,QElapsedTimer,Property,QPropertyAnimation,
    QVariantAnimation,QEasingCurve,Signal)
from PySide6.QtGui import QColor,QFont,QFontMetrics,QLinearGradient,QPainter,QPen
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QAbstractButton,QStackedWidget,QSizePolicy,QFrame,QScrollArea,QBoxLayout,QComboBox)
from .design import colors
from .models import KST
from .event_view import EventList
from .schedule_preview import SchedulePreview

class AnimatedStack(QStackedWidget):
    """Move the incoming native page; never rasterize the widget tree."""
    def __init__(self,parent=None):
        super().__init__(parent);self._group=None;self._overlay=None

    def _settle(self):
        group,self._group=self._group,None
        if group:
            group.stop();group.deleteLater()
        page=self.currentWidget()
        if page:page.setGeometry(self.contentsRect())

    def slide_to(self,index):
        if index==self.currentIndex():return
        self._settle()
        forward=index>self.currentIndex();super().setCurrentIndex(index)
        page=self.currentWidget();page.setGeometry(self.contentsRect())
        if not self.isVisible():return
        target=self.contentsRect().topLeft()
        page.move(target+QPoint(0,6 if forward else -6))
        group=QPropertyAnimation(page,b'pos',self);self._group=group
        group.setDuration(120);group.setStartValue(page.pos());group.setEndValue(target)
        group.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.finished.connect(self._settle);group.start()

    def resizeEvent(self,event):
        self._settle();super().resizeEvent(event)

class AmbientOrbit(QWidget):
    """Decoration only. Its date card uses real, untransformed Qt labels."""
    def __init__(self,parent=None):
        super().__init__(parent);self.phase=0.;self.setFixedWidth(170);self.setMinimumHeight(112)
        self.card=QFrame(self);self.card.setObjectName('orbCard');self.card.setFixedSize(78,92)
        layout=QVBoxLayout(self.card);layout.setContentsMargins(8,12,8,10);layout.setSpacing(4)
        caption=QLabel('오늘');caption.setObjectName('eyebrow');caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.day=QLabel(str(datetime.now(KST).day));self.day.setObjectName('orbitDate');self.day.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(caption);layout.addWidget(self.day,1)
        self.elapsed=QElapsedTimer()
        self.clock=QTimer(self);self.clock.setTimerType(Qt.TimerType.PreciseTimer);self.clock.setInterval(16);self.clock.timeout.connect(self._advance)
    def showEvent(self,event):super().showEvent(event);self.elapsed.start();self.clock.start();self._advance()
    def hideEvent(self,event):self.clock.stop();super().hideEvent(event)
    def _advance(self):
        if not self.isVisible() or self.window().isMinimized():return
        self.phase+=min(self.elapsed.restart()/1000.,.1)*.55;self.update()
    def resizeEvent(self,event):
        super().resizeEvent(event);self.card.move((self.width()-78)//2,(self.height()-92)//2)
    def paintEvent(self,event):
        c=colors();p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx=self.width()/2;cy=self.height()/2
        for i in range(3):
            radius=52+i*11+math.sin(self.phase+i)*3
            tint=QColor(c['accent']);tint.setAlpha(35+i*15);p.setPen(QPen(tint,1.2));p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx-radius,cy-radius,radius*2,radius*2))
        for i in range(5):
            angle=self.phase*(.5 if i%2 else -.4)+i*math.tau/5
            x=cx+math.cos(angle)*62;y=cy+math.sin(angle)*62
            tint=QColor(c['accent']);tint.setAlpha(120);p.setPen(Qt.PenStyle.NoPen);p.setBrush(tint);p.drawEllipse(QRectF(x-3,y-3,6,6))
        p.end()

class WelcomeHero(QFrame):
    def __init__(self,parent=None):
        super().__init__(parent);self.setObjectName('welcomeHero');self.setMinimumHeight(156)
        outer=QHBoxLayout(self);outer.setContentsMargins(24,18,22,18);outer.setSpacing(16)
        text=QVBoxLayout();text.setSpacing(10)
        now=datetime.now(KST);days='월화수목금토일'
        self.dateline=QLabel(f'{now.month}월 {now.day}일 {days[now.weekday()]}요일');self.dateline.setObjectName('muted')
        self.greeting=QLabel('오셨군요!');self.greeting.setObjectName('homeGreeting');self.greeting.setTextFormat(Qt.TextFormat.PlainText)
        self.hint=QLabel('오늘의 일정부터 가볍게 시작해요.');self.hint.setObjectName('muted');self.hint.setWordWrap(True)
        text.addStretch();text.addWidget(self.dateline);text.addWidget(self.greeting);text.addWidget(self.hint);text.addStretch()
        outer.addLayout(text,1);self.orbit=AmbientOrbit();outer.addWidget(self.orbit);self.clock=self.orbit.clock
    def resizeEvent(self,event):
        super().resizeEvent(event);self.orbit.setVisible(self.width()>=650)

class SummaryCard(QPushButton):
    def __init__(self,title,unit,parent=None):
        super().__init__(parent);self.setObjectName('homeSummary');self.title=title;self.unit=unit;self.target=None;self.number=0
        self.setMinimumSize(190,104);self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
        self.setCursor(Qt.CursorShape.PointingHandCursor);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout=QVBoxLayout(self);layout.setContentsMargins(22,15,22,18);layout.setSpacing(8)
        top=QHBoxLayout();self.title_label=QLabel(title);self.title_label.setObjectName('muted');top.addWidget(self.title_label);top.addStretch()
        arrow=QLabel('→');arrow.setObjectName('summaryArrow');top.addWidget(arrow);layout.addLayout(top)
        row=QHBoxLayout();row.setSpacing(7);self.number_label=QLabel('0');self.number_label.setObjectName('summaryNumber')
        self.unit_label=QLabel(unit);self.unit_label.setObjectName('muted')
        row.addWidget(self.number_label,0,Qt.AlignmentFlag.AlignBaseline);row.addWidget(self.unit_label,0,Qt.AlignmentFlag.AlignBaseline);row.addStretch();layout.addLayout(row);layout.addStretch()
        for child in self.findChildren(QLabel):child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.counter=QVariantAnimation(self);self.counter.setDuration(420);self.counter.setEasingCurve(QEasingCurve.Type.OutCubic);self.counter.valueChanged.connect(self._count)
    def _count(self,value):
        number=int(value)
        if self.number_label.text()!=str(number):self.number_label.setText(str(number))
        self.number=number
    def set_count(self,value,animate=True):
        value=int(value);self.setAccessibleName(f'{self.title} {value}{self.unit}. 상세 일정 열기')
        if value==self.target:return
        self.target=value;self.counter.stop()
        if animate and self.isVisible():self.counter.setStartValue(self.number);self.counter.setEndValue(value);self.counter.start()
        else:self._count(value)

class HomeView(QWidget):
    details_requested=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent)
        outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body=QWidget();body.setObjectName('homeBody');self.scroll.setWidget(body);body.setAutoFillBackground(False);self.scroll.viewport().setAutoFillBackground(False);outer.addWidget(self.scroll)
        layout=QVBoxLayout(body);layout.setContentsMargins(0,0,0,0);layout.setSpacing(16)
        self.hero=WelcomeHero();layout.addWidget(self.hero)
        row=QHBoxLayout();row.setSpacing(16)
        self.today_card=SummaryCard('오늘까지 할 일','건');self.remaining_card=SummaryCard('남은 일정','개')
        self.today_card.clicked.connect(lambda:self.details_requested.emit('today'));self.remaining_card.clicked.connect(lambda:self.details_requested.emit('remaining'))
        row.addWidget(self.today_card);row.addWidget(self.remaining_card);layout.addLayout(row)
        self.preview_area=QWidget();self.sections=QBoxLayout(QBoxLayout.Direction.LeftToRight,self.preview_area);self.sections.setContentsMargins(0,0,0,0);self.sections.setSpacing(16)
        today_pane=QWidget();preview=QVBoxLayout(today_pane);preview.setContentsMargins(0,0,0,0);preview.setSpacing(10)
        title=QHBoxLayout();self.upcoming_title=QLabel('오늘 할 일');self.upcoming_title.setObjectName('section');title.addWidget(self.upcoming_title);title.addStretch()
        detail=QPushButton('전체 보기  →');detail.setObjectName('ghost');detail.clicked.connect(lambda:self.details_requested.emit('today'));title.addWidget(detail);preview.addLayout(title)
        categories=QHBoxLayout();categories.setSpacing(6);self.category_buttons={};self.category='all';self._today_rows=[]
        for kind,text in (('all','전체'),('assignment','과제'),('movie','영상')):
            b=QPushButton(text);b.setObjectName('homeCategory');b.setProperty('category',kind);b.setCheckable(True);b.setAutoExclusive(True);b.setChecked(kind=='all')
            b.clicked.connect(lambda checked=False,k=kind:self.set_category(k));categories.addWidget(b);self.category_buttons[kind]=b
        self.type_select=QComboBox();self.type_select.setMaximumWidth(150);self.type_select.setAccessibleName('오늘의 사용자 유형');self.type_select.activated.connect(lambda index:self.set_category(self.type_select.itemData(index) or 'all'))
        categories.addWidget(self.type_select);self.type_select.hide();categories.addStretch();preview.addLayout(categories)
        self.upcoming=EventList();self.today_list=self.upcoming;self.upcoming.empty_text='오늘 남은 할 일이 없습니다'
        self.upcoming.setMinimumHeight(108);preview.addWidget(self.upcoming,1)
        remaining_pane=QWidget();remaining=QVBoxLayout(remaining_pane);remaining.setContentsMargins(0,0,0,0);remaining.setSpacing(10)
        remaining_head=QHBoxLayout();remaining_title=QLabel('남은 일정');remaining_title.setObjectName('section');remaining_head.addWidget(remaining_title);remaining_head.addStretch()
        remaining_all=QPushButton('전체 보기  →');remaining_all.setObjectName('ghost');remaining_all.clicked.connect(self.open_remaining);remaining_head.addWidget(remaining_all);remaining.addLayout(remaining_head)
        self.remaining_table=SchedulePreview(remaining_pane);remaining.addWidget(self.remaining_table,1)
        self.sections.addWidget(today_pane,2);self.sections.addWidget(remaining_pane,3);layout.addWidget(self.preview_area,1)
    def update_snapshot(self,snapshot,now=None):
        now=now or datetime.now(KST);pending=snapshot.pending(now)
        today=[event for event in pending if event.due is not None and event.due.date()==now.date()]
        self.hero.dateline.setText(f'{now.month}월 {now.day}일 {"월화수목금토일"[now.weekday()]}요일');self.hero.orbit.day.setText(str(now.day))
        self.today_card.set_count(len(today));self.remaining_card.set_count(len(pending))
        self._today_rows=today
        for kind,b in self.category_buttons.items():
            count=len(today) if kind=='all' else sum(e.kind==kind for e in today)
            b.setText({'all':'전체','assignment':'과제','movie':'영상'}[kind]+f' {count}')
        groups={}
        for e in today:
            if e.type_id is not None:
                key=(e.type_id,e.type_label);groups[key]=groups.get(key,0)+1
        self.type_select.clear();self.type_select.addItem('다른 유형',None)
        for (key,name),count in groups.items():self.type_select.addItem(f'{name} {count}',f'type:{key}')
        self.type_select.setVisible(bool(groups))
        if self.category not in self.category_buttons and self.type_select.findData(self.category)<0:self.category='all'
        self.set_category(self.category);self.remaining_table.set_events(pending,now)
    def set_category(self,kind):
        self.category=kind
        for key,b in self.category_buttons.items():b.setAutoExclusive(False);b.setChecked(kind==key);b.setAutoExclusive(True)
        self.type_select.setCurrentIndex(max(0,self.type_select.findData(kind)))
        self.upcoming.set_events(e for e in self._today_rows if kind=='all' or e.kind==kind or (e.type_id is not None and kind==f'type:{e.type_id}'))
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'sections'):self.sections.setDirection(QBoxLayout.Direction.LeftToRight if self.width()>=900 else QBoxLayout.Direction.TopToBottom)
    def open_remaining(self):self.details_requested.emit('remaining')
    def hideEvent(self,event):
        self.today_card.counter.stop();self.remaining_card.counter.stop();super().hideEvent(event)
    def showEvent(self,event):
        super().showEvent(event)
        for card in (self.today_card,self.remaining_card):
            if card.target is not None:
                card._count(card.target)
