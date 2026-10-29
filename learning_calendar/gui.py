"""Native, snapshot-driven UI. No browser, network or per-row widgets at startup."""
from __future__ import annotations
import logging
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import Qt, QTimer, QStandardPaths, QUrl, QProcess, QSize, Slot,QPoint,QRect
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontMetrics, QPainter, QPen, QAction, QKeySequence, QShortcut,QCursor,QImage
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QVBoxLayout,QHBoxLayout,QLabel,
    QPushButton,QToolButton,QAbstractButton,QComboBox,QLineEdit,QStackedWidget,QSplitter,QMenu,QDialog,
    QMessageBox,QFileDialog,QSizePolicy,QScrollArea,QTableWidget,QTableWidgetItem,QHeaderView,
    QAbstractItemView,QListWidget,QListWidgetItem,QSystemTrayIcon)
from .design import VERSION, icon, colors, stylesheet, apply_palette, THEME_NAMES, DEFAULT_THEME
from .home_view import HomeView, AnimatedStack
from .models import KST
from .storage import Store
from .snapshot import Snapshot
from .text_safety import tooltip_text
from .calendar_view import MonthCanvas
from .event_view import EventList, EVENT_ROLE
from .dialogs import SettingsDialog, AliasDialog, SessionDialog, MemoDialog, DAYS
from .preferences import read_settings,write_settings,read_account


def label(text='',name=''):
    w=QLabel(text);w.setObjectName(name);w.setTextFormat(Qt.TextFormat.PlainText);return w


class ElideLabel(QLabel):
    def __init__(self,text='',parent=None):
        super().__init__(parent);self.full_text=text
        self.setTextFormat(Qt.TextFormat.PlainText);self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self,text):
        self.full_text=str(text);self.setToolTip(tooltip_text(self.full_text))
        if self.isVisible():self._fit()
        else:super().setText(self.full_text)

    def _fit(self):
        super().setText(QFontMetrics(self.font()).elidedText(self.full_text,Qt.TextElideMode.ElideRight,max(1,self.contentsRect().width())))

    def resizeEvent(self,event):
        super().resizeEvent(event);self._fit()

    def showEvent(self,event):super().showEvent(event);self._fit()


def button(text,callback,name='',parent=None):
    w=QPushButton(text,parent);w.setObjectName(name)
    w.setCursor(Qt.CursorShape.PointingHandCursor);w.clicked.connect(callback);return w


class NavigationButton(QPushButton):
    def __init__(self,text,kind,parent=None):
        super().__init__(text,parent);self.kind=kind;self.setObjectName('nav')
        self.setIcon(icon(kind));self.setIconSize(QSize(20,20));self.setCheckable(True);self.setAutoExclusive(True)
        self.setFixedHeight(43);self.setMinimumWidth(126)
        self.setCursor(Qt.CursorShape.PointingHandCursor);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        f=QFont(self.font());f.setPixelSize(14);f.setWeight(QFont.Weight.Normal);self.setFont(f)


class MetricButton(QPushButton):
    """QPushButton's default hint only measures its own text, not child labels."""
    def sizeHint(self):
        hint=self.layout().sizeHint() if self.layout() else super().sizeHint()
        return hint.expandedTo(QSize(94,36))
    def minimumSizeHint(self):return self.sizeHint()


class MainWindow(QMainWindow):
    def __init__(self,data_dir=None,demo=False):
        super().__init__();self.setWindowTitle('Calix')
        self._isolated=data_dir is not None;self._ready_dialogs=None
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint,False)
        self._exit_confirmed=False;self._quit_on_close=False;self._exit_prompt_open=False
        self._shutdown_started=False;self._shutdown_forms_ready=False
        from .app_identity import app_icon
        self.setWindowIcon(app_icon())
        self.appdir=Path(data_dir) if data_dir else Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        if data_dir is None:
            from .paths import migrate_legacy_data
            migrate_legacy_data(self.appdir)
        self.appdir.mkdir(parents=True,exist_ok=True)
        self.settings_path=self.appdir/'settings.json';self.settings=read_settings(self.settings_path)
        from .holidays import HolidayCalendar
        self.holiday_calendar=HolidayCalendar(self.appdir/'holidays.db')
        active=self.settings.get('active_db','learning.db')
        if Path(str(active)).name!=active or not str(active).endswith('.db'):active='learning.db'
        self.store=Store(self.appdir/active);self.session_path=self.appdir/'canvas_session.dpapi'
        self.snapshot=Snapshot(self.store.events(),self.store.courses())
        self._sessions=self.store.timetable()
        self.last_sync=self.store.get_meta('last_sync');self.partial=self.store.get_meta('sync_partial')=='1'
        self.demo=False;self.demo_snapshot=None;self._thread=None;self._login_process=None
        self._login_server=None;self._login_socket=None;self._browser_buffer=bytearray()
        self._logged_in=False;self._logging_out=False;self._movies_ready=False;self._sync_after_browser=False;self._movie_reauth_attempted=False
        self._closing=False;self._closed=False;self._login_then_sync=False;self._dialogs={}
        self.selected_date=datetime.now(KST).date();self.month=self.selected_date.replace(day=1)
        self._today=self.selected_date;self._filtered=[];self._buckets={};self._timetable_signature=None
        self._busy=False;self._filter_signature=None;self._home_filter=None;self._page_filters={};self._page_cache={}
        self._undo_stack=[];self.diary=None;self._tray=None;self._event_popover=None;self._calendar=None
        from .reminders import DueReminders
        self.reminders=DueReminders()
        self._reauth_requested=False;self._reauth_attempted=False
        self.theme_key=self.settings.get('theme',DEFAULT_THEME)
        QApplication.instance().setProperty('calixGlass',bool(self.settings.get('glass',True)))
        apply_palette(QApplication.instance(),self.theme_key)
        self.setFont(QApplication.font());self.setStyleSheet(stylesheet(self.theme_key))
        self.search_timer=QTimer(self);self.search_timer.setSingleShot(True);self.search_timer.setInterval(140)
        self.search_timer.timeout.connect(self.refresh)
        self._build_ui();self._build_menus();self._reload_type_filter();self._reload_course_filter()
        if not demo:
            from .cookies import read_cookies,canvas_session_available
            self._set_logged_in(canvas_session_available(read_cookies(self.session_path)))
        screen=QApplication.primaryScreen();area=screen.availableGeometry() if screen else None
        self.setMinimumSize(min(780,area.width()) if area else 780,min(520,area.height()) if area else 520)
        self.resize(min(int(self.settings.get('window_width',1240)),area.width() if area else 1240),
                    min(int(self.settings.get('window_height',840)),area.height() if area else 840))
        self.local_clock=QTimer(self);self.local_clock.setInterval(60_000)
        self.local_clock.timeout.connect(self._tick);self.local_clock.timeout.connect(self._notify_due);self.local_clock.start()
        QTimer.singleShot(1500,self._notify_due)
        QShortcut(QKeySequence('Ctrl+F'),self,activated=self._focus_search)
        QShortcut(QKeySequence('Ctrl+N'),self,activated=self.add_manual)
        # Text editors keep their own native undo shortcuts.
        QShortcut(QKeySequence('Ctrl+R'),self,activated=self.manual_sync)
        if demo:self.preview()
        else:self.refresh()
        self.show_home(animate=False)

    def prepare_navigation(self):
        """Prepare native controls before the first interactive frame."""
        from .preferences import prepare_credentials
        try:prepare_credentials()
        except Exception:logging.warning('계정 보관함 준비 실패')
        self.calendar
        if not self._timetable_built:self._build_timetable()
        self._refresh_timetable()
        self._ensure_diary()
        self.ensurePolished()
        self.layout().activate();self.centralWidget().layout().activate()
        self.main_stack.setCurrentIndex(1)
        original=self.tabs.currentIndex()
        for index in range(self.tabs.count()):
            self.tabs.setCurrentIndex(index)
            self.refresh()
            page=self.tabs.widget(index);page.ensurePolished()
            if page.layout():page.layout().activate()
            for child in page.findChildren(QWidget):
                child.ensurePolished()
                if child.layout():child.layout().activate()
        self.tabs.setCurrentIndex(original)
        self.refresh()
        self.main_stack.setCurrentIndex(2)
        self.diary_holder.layout().activate()
        self.main_stack.setCurrentIndex(0)
        for view in (self.video_list,self.assignment_list):
            delegate=view.itemDelegate()
            for size,weight in ((14,QFont.Weight.DemiBold),(12,QFont.Weight.Normal)):
                _,metrics=delegate.text_style(view.font(),size,weight)
                for event in view.event_model.rows[:8]:metrics.horizontalAdvance(event.title+' '+event.course_name)
        self.calendar.badge_timer.stop();self.calendar._layout_badges()
        # A temporary warm-up surface is released here. Live pages remain
        # native widgets; page transitions never display cached images.
        for page in (self.tabs.widget(0),self.assignment_list,self.timetable_page,self.diary_holder):
            surface=QImage(page.size(),QImage.Format.Format_ARGB32_Premultiplied);surface.fill(Qt.GlobalColor.transparent);page.render(surface)
        if self._ready_dialogs is None:
            from .ready_dialogs import ReadyDialogs
            self._ready_dialogs=ReadyDialogs(self._make_ready_dialog,self);self._ready_dialogs.prime()

    def _make_ready_dialog(self,name):
        if name=='settings':return SettingsDialog(self,account='' if self._isolated else None)
        if name=='aliases':return AliasDialog(self.store,self)
        if name=='session':return SessionDialog(self._current_snapshot().courses,parent=self)
        if name=='theme':
            from .appearance import AppearanceDialog
            return AppearanceDialog(self.theme_key,self)
        if name=='credits':
            from .credits import CreditsDialog
            return CreditsDialog(self)
        if name in ('manual','types'):
            from .manual_events import ManualEventDialog,TypeManager
            return TypeManager(self.store,self) if name=='types' else ManualEventDialog(self.store,self._current_snapshot().courses,self.selected_date,parent=self)
        if name=='holiday':
            from .holiday_dialog import HolidayDialog
            return HolidayDialog(self.holiday_calendar,self.selected_date,self)
        if name=='special':
            from .special_dates_dialog import SpecialDatesDialog
            return SpecialDatesDialog(self.holiday_calendar,self)
        raise ValueError('Unknown dialog')

    def _take_ready_dialog(self,name):
        return self._ready_dialogs.take(name) if self._ready_dialogs else self._make_ready_dialog(name)

    def _build_ui(self):
        from .glass import GlassBackdrop
        root=GlassBackdrop();root.setObjectName('root');self.setCentralWidget(root)
        outer=QHBoxLayout(root);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        rail=QFrame();rail.setObjectName('sidebar');rail.setFixedWidth(184)
        side=QVBoxLayout(rail);side.setContentsMargins(12,23,12,16);side.setSpacing(5)
        brand=QHBoxLayout();mark=QLabel();mark.setPixmap(self.windowIcon().pixmap(30,30));brand.addWidget(mark);brand.addWidget(label('Calix','brand'));brand.addStretch();side.addLayout(brand)
        side.addWidget(label('나의 일정 공간','eyebrow'));side.addSpacing(22)
        side.addWidget(label('일정','eyebrow'));side.addSpacing(7)
        self.home_nav=NavigationButton('홈','home',rail);self.home_nav.clicked.connect(self.show_home);side.addWidget(self.home_nav)
        self.nav=[]
        for i,(name,kind) in enumerate((('달력','calendar'),('영상','video'),('과제','assignment'),('시간표','timetable'))):
            b=NavigationButton(name,kind,rail);b.clicked.connect(lambda checked=False,n=i:self.select_page(n))
            side.addWidget(b);self.nav.append(b)
        self.diary_nav=NavigationButton('일기장','diary',rail);self.diary_nav.clicked.connect(self.show_diary);side.addSpacing(10);side.addWidget(self.diary_nav)
        self.home_nav.setChecked(True);side.addStretch()
        side.addWidget(label('설정','eyebrow'));side.addSpacing(5)
        theme_button=button('테마',self.choose_theme,'quiet');theme_button.setIcon(icon('theme'));side.addWidget(theme_button)
        self.account_button=button('계정 설정',self.configure,'quiet');self.account_button.setIcon(icon('settings'));side.addWidget(self.account_button)
        credit_button=button('크레딧',self.credits,'quiet');credit_button.setIcon(icon('info'));side.addWidget(credit_button);side.addSpacing(10)
        self.exit_button=button('종료',self.request_exit,'quiet');self.exit_button.setIcon(icon('close'))
        self.exit_button.setAccessibleName('프로그램 종료');side.addWidget(self.exit_button)
        side.addWidget(label('v'+VERSION,'muted'));outer.addWidget(rail)
        main=QWidget();main.setObjectName('page');v=QVBoxLayout(main);v.setContentsMargins(24,20,24,14);v.setSpacing(14)
        header=QHBoxLayout();self.heading=label('홈','heading');header.addWidget(self.heading);header.addStretch()
        self.demo_badge=button('샘플 닫기',self.end_preview,'ghost');self.demo_badge.hide();header.addWidget(self.demo_badge)
        self.login_button=button('로그인',self.login,'ghost');header.addWidget(self.login_button)
        self.detail_button=button('상세 일정',lambda:self.open_details('all'),'ghost');header.addWidget(self.detail_button)
        self.sync_btn=button('동기화',self.manual_sync,'ghost');self.sync_btn.setToolTip('Ctrl+R');header.addWidget(self.sync_btn)
        self.add_task_button=button('일정 추가',lambda:self.add_manual(),'primary');self.add_task_button.setToolTip('Ctrl+N');header.addWidget(self.add_task_button)
        self.command_menu=QToolButton();self.command_menu.setObjectName('commandMenu');self.command_menu.setIcon(icon('menu'));self.command_menu.setToolTip('메뉴');self.command_menu.setFixedSize(40,38);self.command_menu.setAccessibleName('앱 메뉴');self.command_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup);header.addWidget(self.command_menu)
        v.addLayout(header)
        master=v;self.main_stack=AnimatedStack();self.home=HomeView();self.main_stack.addWidget(self.home)
        self.home.details_requested.connect(self.open_details)
        self.home.upcoming.activated.connect(lambda index:self.open_event(index.data(EVENT_ROLE)))
        self.home.remaining_table.activated.connect(lambda index:self.open_event(index.data(EVENT_ROLE)))
        self.home.upcoming.completion_requested.connect(self.complete_manual);self.home.remaining_table.completion_requested.connect(self.complete_manual)
        self.detail_workspace=QWidget();v=QVBoxLayout(self.detail_workspace);v.setContentsMargins(0,0,0,0);v.setSpacing(15)
        self.metrics=QWidget();metrics=QHBoxLayout(self.metrics);metrics.setContentsMargins(0,0,0,0);metrics.setSpacing(12)
        self.metric_labels=[];self.metric_buttons=[]
        for title,status in (('오늘 마감',6),('7일 이내',7),('미완료',1)):
            card=MetricButton();card.setObjectName('metricChip');card.setSizePolicy(QSizePolicy.Policy.Minimum,QSizePolicy.Policy.Fixed);card.setCursor(Qt.CursorShape.PointingHandCursor);card.clicked.connect(lambda checked=False,s=status:self._metric_filter(s))
            box=QHBoxLayout(card);box.setContentsMargins(12,6,12,6);box.setSpacing(8)
            caption=label(title,'muted');number=label('0','metricValue')
            for child in (caption,number):child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);box.addWidget(child)
            self.metric_labels.append(number);self.metric_buttons.append(card);metrics.addWidget(card)
        metrics.addStretch();v.addWidget(self.metrics)
        self.filter_bar=QWidget();filters=QHBoxLayout(self.filter_bar);filters.setContentsMargins(0,0,0,0);filters.setSpacing(10)
        self.search=QLineEdit();self.search.setPlaceholderText('일정 검색');self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName('일정 검색');self.search.textChanged.connect(lambda:self.search_timer.start());filters.addWidget(self.search,1)
        self.course_select=QComboBox();self.course_select.setMinimumWidth(135);self.course_select.setMaximumWidth(225)
        self.course_select.currentIndexChanged.connect(self.refresh);self.course_select.setAccessibleName('과목 필터');filters.addWidget(self.course_select)
        self.type_filter=QComboBox();self.type_filter.setMinimumWidth(92);self.type_filter.setMaximumWidth(160);self.type_filter.setAccessibleName('일정 유형 필터');self.type_filter.currentIndexChanged.connect(self.refresh);filters.addWidget(self.type_filter)
        self.state_select=QComboBox();self.state_select.addItems(['전체 상태','미완료','완료','기한 경과','즐겨찾기','기한 없음','오늘까지','7일 이내'])
        self.state_select.setMinimumWidth(120);self.state_select.currentIndexChanged.connect(self.refresh);self.state_select.setAccessibleName('상태 필터');filters.addWidget(self.state_select)
        self.filter_reset=button('초기화',self.reset_filters,'ghost');self.filter_reset.setToolTip('이 화면의 검색과 필터 지우기');filters.addWidget(self.filter_reset)
        v.addWidget(self.filter_bar)
        self.tabs=QStackedWidget();self.tabs.addWidget(self._build_calendar())
        self.video_list=self._event_list();self.assignment_list=self._event_list()
        self.tabs.addWidget(self.video_list);self.tabs.addWidget(self.assignment_list)
        self.timetable_page=QWidget();self.tabs.addWidget(self.timetable_page);self._timetable_built=False
        v.addWidget(self.tabs,1)
        self.main_stack.addWidget(self.detail_workspace);self.diary_holder=QWidget();self.main_stack.addWidget(self.diary_holder);master.addWidget(self.main_stack,1);v=master
        footer=QHBoxLayout();self.sync_info=label('','muted');footer.addWidget(self.sync_info,1)
        self.undo_button=button('되돌리기',self.undo_manual,'ghost');self.undo_button.setEnabled(False);self.undo_button.setToolTip('이전 일정 변경 취소');footer.addWidget(self.undo_button)
        self.status=ElideLabel('준비');self.status.setObjectName('muted');self.status.setFixedWidth(260);footer.addWidget(self.status)
        v.addLayout(footer);outer.addWidget(main,1)

    def _build_menus(self):
        file=self.menuBar().addMenu('파일')
        file.addAction('동기화',self.manual_sync);file.addAction('ICS 저장',self.export)
        file.addSeparator();file.addAction('개인 자료 백업',self.backup_personal);file.addAction('백업 복원',self.restore_personal)
        file.addSeparator();exit_action=file.addAction('종료',self.request_exit);exit_action.setShortcut(QKeySequence('Ctrl+Q'))
        settings=self.menuBar().addMenu('설정');settings.addAction('계정',self.configure)
        settings.addAction('과목 이름',self.edit_aliases);settings.addAction('변경 기록',self.show_changes)
        settings.addAction('테마',self.choose_theme)
        settings.addAction('일정 유형',self.manage_types)
        settings.addAction('공휴일',self.manage_holidays)
        other=settings.addMenu('기타');other.addAction('특수 일정 등록',self.manage_special_dates)
        view=self.menuBar().addMenu('보기')
        view.addAction('홈',self.show_home)
        for i,name in enumerate(('달력','동영상','과제','시간표')):
            action=QAction(name,self);action.setShortcut(QKeySequence(f'Ctrl+{i+1}'))
            action.triggered.connect(lambda checked=False,n=i:self.select_page(n));view.addAction(action)
        view.addAction('일기장',self.show_diary)
        view.addSeparator();view.addAction('샘플 화면',self.preview)
        help_menu=self.menuBar().addMenu('도움말');help_menu.addAction('크레딧',self.credits)
        help_menu.addAction('업데이트 확인',self.check_updates)
        help_menu.addAction('로그 폴더',self.open_logs)
        menu=QMenu(self.command_menu)
        for action in self.menuBar().actions():
            if action.menu():menu.addMenu(action.menu())
        self.command_menu.setMenu(menu);self.menuBar().hide()
        QShortcut(QKeySequence('Alt+M'),self,activated=self.command_menu.showMenu)

    def _build_calendar(self):
        page=QWidget();v=QVBoxLayout(page);v.setContentsMargins(0,0,0,0);v.setSpacing(12)
        row=QHBoxLayout();row.setSpacing(8);self.month_label=label('','month');row.addWidget(self.month_label);row.addSpacing(12)
        for title,cb,tip in [('‹',lambda:self.shift_month(-1),'이전 달'),('오늘',self.go_today,'오늘'),('›',lambda:self.shift_month(1),'다음 달')]:
            b=button(title,cb,'ghost');b.setToolTip(tip);b.setAccessibleName(tip)
            if title!='오늘':b.setFixedWidth(36)
            row.addWidget(b)
        row.addStretch();self.month_summary=label('','muted');row.addWidget(self.month_summary);row.addSpacing(6)
        self.holiday_button=button('공휴일',self.manage_holidays,'ghost');self.holiday_button.setToolTip('기본 공휴일과 임시공휴일 설정');row.addWidget(self.holiday_button)
        self.day_toggle=QPushButton('상세 일정');self.day_toggle.setObjectName('ghost');self.day_toggle.setCheckable(True);self.day_toggle.setAccessibleName('선택한 날짜의 상세 일정 열기');self.day_toggle.toggled.connect(self._toggle_day_panel);row.addWidget(self.day_toggle);v.addLayout(row)
        self.calendar_split=QSplitter(Qt.Orientation.Horizontal);self.calendar_split.setHandleWidth(12)
        self._calendar_placeholder=QWidget();self.calendar_split.addWidget(self._calendar_placeholder)
        self.day_panel=QFrame();self.day_panel.setObjectName('inspector');detail=QVBoxLayout(self.day_panel);detail.setContentsMargins(12,16,12,12);detail.setSpacing(12)
        heading=QHBoxLayout();self.day_title=label('','section');heading.addWidget(self.day_title);heading.addStretch();self.day_count=label('0','badge');heading.addWidget(self.day_count)
        close=QToolButton();close.setObjectName('zoomButton');close.setIcon(icon('close'));close.setFixedSize(30,30);close.setAccessibleName('상세 일정 닫기');close.setToolTip('닫기');close.clicked.connect(lambda:self.day_toggle.setChecked(False));heading.addWidget(close);detail.addLayout(heading)
        self.day_holiday=label('','holidayName');self.day_holiday.setWordWrap(True);self.day_holiday.hide();detail.addWidget(self.day_holiday)
        self.day_feast=label('','feastName');self.day_feast.setWordWrap(True);self.day_feast.hide();detail.addWidget(self.day_feast)
        self.day_list=self._event_list();detail.addWidget(self.day_list,1)
        self.day_panel.setMinimumWidth(270);self.day_panel.setMaximumWidth(340);self.calendar_split.addWidget(self.day_panel);self.day_panel.hide()
        self.calendar_split.setChildrenCollapsible(False);self.calendar_split.setStretchFactor(0,1);v.addWidget(self.calendar_split,1);return page

    def _toggle_day_panel(self,opened):
        if not hasattr(self,'day_panel'):return
        self.day_panel.setVisible(bool(opened))
        if opened:self.calendar_split.setSizes([max(300,self.calendar_split.width()-315),315])
        self.calendar.badge_timer.start(0)

    @property
    def calendar(self):
        if self._calendar is None:
            self._calendar=MonthCanvas();self._calendar.selected.connect(self.select_day);self._calendar.create_requested.connect(self.add_manual);self._calendar.details_requested.connect(self.show_calendar_group)
            previous=self.calendar_split.replaceWidget(0,self._calendar);previous.deleteLater();self._calendar_placeholder=None;self._render_visible()
        return self._calendar

    def _event_list(self):
        view=EventList()
        view.completion_requested.connect(self.complete_manual)
        view.activated.connect(lambda index:self.open_event(index.data(EVENT_ROLE)))
        view.customContextMenuRequested.connect(lambda pos,lst=view:self.event_menu(lst,pos))
        return view

    def select_page(self,index):
        self.main_stack._settle()
        if index==0:self.calendar
        if self.diary:
            if not self.diary.flush():return
            self.diary.lock()
        previous=self.tabs.currentIndex()
        if previous!=index:
            if previous<3:self._page_filters[previous]=(self.course_select.currentData(),self.search.text(),self.state_select.currentIndex(),self.type_filter.currentData())
            self.tabs.setCurrentIndex(index)
            if index<3:self._apply_filters(*self._page_filters.get(index,(None,'',0,None)))
        if index==3 and not self._timetable_built:self._build_timetable()
        self.tabs.setCurrentIndex(index);self.nav[index].setChecked(True)
        self.heading.setText(('달력','동영상','과제','시간표')[index])
        self.filter_bar.setVisible(index!=3);self.metrics.setVisible(index in (1,2) and self.height()>=640)
        self.add_task_button.setVisible(index!=3)
        self.type_filter.setVisible(index==0)
        self.main_stack.slide_to(1)
        self.refresh();self.detail_button.hide()
        self.detail_button.clicked.disconnect();self.detail_button.clicked.connect(self.show_home)
        self._update_footer()
        self._present_page()

    def show_home(self,checked=False,animate=True):
        if not hasattr(self,'main_stack'):return
        if self.diary:
            if not self.diary.flush():return
            self.diary.lock()
        self.home_nav.setChecked(True);self.heading.setText('홈')
        self.add_task_button.show()
        self.detail_button.show()
        self.home.update_snapshot(self._current_snapshot())
        if animate:self.main_stack.slide_to(0)
        else:self.main_stack.setCurrentIndex(0)
        self.detail_button.setText('일정 보기');self.detail_button.clicked.disconnect()
        self.detail_button.clicked.connect(lambda:self.open_details('all'))
        self._update_footer()
        self._present_page()

    def _present_page(self):
        # Present the incoming native page now; subsequent animation frames use
        # the ordinary update queue. No screenshots or nested event loops.
        if self.isVisible():self.main_stack.currentWidget().repaint()

    def open_details(self,scope='all'):
        self.select_page(0)
        self.reset_filters(6 if scope=='today' else 1 if scope=='remaining' else 0)

    def _apply_filters(self,course_id=None,query='',status=0,type_key=None):
        controls=(self.course_select,self.search,self.state_select,self.type_filter)
        for control in controls:control.blockSignals(True)
        try:
            self.course_select.setCurrentIndex(max(0,self.course_select.findData(course_id)))
            self.search.setText(query);self.state_select.setCurrentIndex(status)
            self.type_filter.setCurrentIndex(max(0,self.type_filter.findData(type_key)))
        finally:
            for control in controls:control.blockSignals(False)

    def reset_filters(self,status=0):
        # QPushButton.clicked may pass a bool; it is not a saved filter status.
        self._apply_filters(status=0 if isinstance(status,bool) else int(status));self.refresh()

    def choose_theme(self):
        dialog=self._take_ready_dialog('theme');dialog.chosen.connect(self.set_theme);dialog.notifications_changed.connect(self.set_notifications);dialog.glass_changed.connect(self.set_glass);self._exec_dialog(dialog)

    def set_glass(self,enabled):
        self.main_stack._settle();self.settings['glass']=bool(enabled);QApplication.instance().setProperty('calixGlass',bool(enabled))
        apply_palette(QApplication.instance(),self.theme_key);self.setStyleSheet(stylesheet(self.theme_key));self.centralWidget().invalidate();write_settings(self.settings_path,self.settings)
        for view in (self.video_list,self.assignment_list,self.day_list,self.home.upcoming,self.home.remaining_table):view.viewport().update()
        self.home._snapshot_cache=None
        if self.main_stack.currentIndex()==0:self.home.update_snapshot(self._current_snapshot())

    def set_notifications(self,enabled):
        self.settings['notifications']=bool(enabled);write_settings(self.settings_path,self.settings)
        if not enabled and self._tray:self._tray.hide();self._tray.deleteLater();self._tray=None
        if enabled:self._notify_due()

    def _notify_due(self):
        if self._closing or self.demo or not self.settings.get('notifications',False):return
        rows=self.reminders.pending(self.snapshot.events)
        if not rows or not QSystemTrayIcon.isSystemTrayAvailable():return
        if self._tray is None:
            self._tray=QSystemTrayIcon(self.windowIcon(),self);self._tray.setToolTip('Calix');self._tray.activated.connect(lambda reason:(self.showNormal(),self.activateWindow()));self._tray.show()
        title=rows[0].title if len(rows)==1 else f'{len(rows)}개의 일정'
        self._tray.showMessage('곧 마감됩니다',title+' / 15분 이내',QSystemTrayIcon.MessageIcon.Information,7000)

    def set_theme(self,key):
        if key not in THEME_NAMES:return
        self.main_stack._settle()
        self.theme_key=key;self.settings['theme']=key
        if self._ready_dialogs:self._ready_dialogs.invalidate()
        apply_palette(QApplication.instance(),key);self.setStyleSheet(stylesheet(key))
        write_settings(self.settings_path,self.settings)
        for b in [self.home_nav,self.diary_nav]+self.nav:b.setIcon(icon(b.kind))
        self.centralWidget().invalidate();self.update();self.home.hero.update()
        if self._calendar is not None:self._calendar.set_month(self.month,self.selected_date,self._buckets,self.holiday_calendar.year(self.month.year),self.holiday_calendar.special_dates(self.month.year))
        for view in (self.video_list,self.assignment_list,self.day_list,self.home.upcoming,self.home.remaining_table):view.viewport().update()
        self._timetable_signature=None
        if self._timetable_built:self._refresh_timetable()
        self.home._snapshot_cache=None
        if self.main_stack.currentIndex()==0:self.home.update_snapshot(self._current_snapshot())

    def _current_snapshot(self):return self.demo_snapshot if self.demo else self.snapshot

    def _reload_course_filter(self):
        selected=self.course_select.currentData();self.course_select.blockSignals(True);self.course_select.clear()
        self.course_select.addItem('모든 과목',None)
        for c in self._current_snapshot().courses:self.course_select.addItem(c.name,c.id)
        if any(e.manual and e.course_id==0 for e in self._current_snapshot().events):self.course_select.addItem('개인 일정',0)
        self.course_select.setCurrentIndex(max(0,self.course_select.findData(selected)));self.course_select.blockSignals(False)

    def _reload_type_filter(self):
        selected=self.type_filter.currentData();self.type_filter.blockSignals(True);self.type_filter.clear()
        for name,key in (('모든 유형',None),('과제','assignment'),('영상','movie')):self.type_filter.addItem(name,key)
        for row in self.store.event_types():self.type_filter.addItem(row['name'],f'type:{row["id"]}')
        self.type_filter.setCurrentIndex(max(0,self.type_filter.findData(selected)));self.type_filter.blockSignals(False)

    @Slot()
    def refresh(self):
        if self._closing:return
        self.search_timer.stop()
        now=datetime.now(KST);snapshot=self._current_snapshot()
        if getattr(self,'_cache_snapshot',None) is not snapshot:
            self._page_cache.clear();self._cache_snapshot=snapshot
            if self._ready_dialogs:self._ready_dialogs.invalidate()
        page=self.tabs.currentIndex();kind={1:'movie',2:'assignment'}.get(page)
        type_key=kind or self.type_filter.currentData()
        signature=(snapshot,self.course_select.currentData(),self.search.text(),self.state_select.currentIndex(),type_key)
        cached=self._page_cache.get(page)
        if cached and cached[0]==signature and cached[1]<=now<cached[2]:
            self._filtered,self._buckets,values=cached[3:]
        else:
            self._filtered=snapshot.filtered(self.course_select.currentData(),self.search.text(),self.state_select.currentIndex(),now=now,type_key=type_key)
            self._buckets=Snapshot.days(self._filtered)
            context=self._filtered if self.state_select.currentIndex()==0 else snapshot.filtered(self.course_select.currentData(),self.search.text(),now=now,type_key=type_key)
            values=Snapshot.count_deadlines(context,now)
            # Expire at the next due time, 7-day boundary, midnight, or minute.
            # This keeps counters correct when a deadline passes during navigation.
            until=min(now+timedelta(seconds=60),(now+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0))
            for event in context:
                due=event.due
                if due:
                    for boundary in (due,due-timedelta(days=7)):
                        if now<boundary<until:until=boundary
            self._page_cache[page]=(signature,now,until,self._filtered,self._buckets,values)
        self.filter_reset.setEnabled(bool(self.course_select.currentData() is not None or self.search.text() or self.state_select.currentIndex() or (page==0 and self.type_filter.currentData())))
        for w,value,button,status,title in zip(self.metric_labels,values,self.metric_buttons,(6,7,1),('오늘 마감','7일 이내','미완료')):
            w.setText(str(value));button.setAccessibleName(f'{title} {value}건')
            active=self.state_select.currentIndex()==status
            if button.property('active')!=active:button.setProperty('active',active);button.style().unpolish(button);button.style().polish(button)
        if self.main_stack.currentIndex()==0:self.home.update_snapshot(snapshot,now)
        self._render_visible();self._update_footer()

    def _metric_filter(self,status):
        if self.tabs.currentIndex()==0:
            self.selected_date=datetime.now(KST).date();self.month=self.selected_date.replace(day=1)
        self.state_select.setCurrentIndex(status);self.refresh()

    def _render_visible(self):
        index=self.tabs.currentIndex()
        if index==0:
            self.month_label.setText(f'{self.month.year}년 {self.month.month}월')
            month_count=sum(len(rows) for day,rows in self._buckets.items() if day.year==self.month.year and day.month==self.month.month)
            self.month_summary.setText(f'{month_count}개의 일정')
            holidays=self.holiday_calendar.year(self.month.year)
            feasts=self.holiday_calendar.special_dates(self.month.year)
            if self._calendar is not None:self._calendar.set_month(self.month,self.selected_date,self._buckets,holidays,feasts)
            self.day_title.setText(f'{self.selected_date.month}월 {self.selected_date.day}일  {DAYS[self.selected_date.weekday()]}')
            rows=self._buckets.get(self.selected_date,[]);self.day_count.setText(str(len(rows)));self.day_list.set_events(rows)
            self.day_toggle.setText('상세 일정');self.day_toggle.setAccessibleName('상세 일정')
            self.day_holiday.setText(holidays.get(self.selected_date,''));self.day_holiday.setVisible(bool(self.day_holiday.text()))
            self.day_feast.setText(feasts.get(self.selected_date,''));self.day_feast.setVisible(bool(self.day_feast.text()))
        elif index in (1,2):
            kind='movie' if index==1 else 'assignment';name='영상' if index==1 else '과제'
            view=self.video_list if index==1 else self.assignment_list
            total=len(self._current_snapshot().by_kind.get(kind,()))
            subject='영상이' if index==1 else '과제가'
            view.empty_text=f'필터에 맞는 {subject} 없습니다' if total else f'불러온 {subject} 없습니다'
            view.set_events(e for e in self._filtered if e.kind==kind)
        else:self._refresh_timetable()

    def _tick(self):
        if self._closing or self.isMinimized() or not self.isVisible():return
        today=datetime.now(KST).date()
        if today!=self._today:
            if self.selected_date==self._today:self.selected_date=today;self.month=today.replace(day=1)
            self._today=today
        self.refresh()

    def showEvent(self,event):
        super().showEvent(event)
        from .app_identity import apply_window_identity
        apply_window_identity(self)
        if hasattr(self,'local_clock'):self._tick()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'metrics') and hasattr(self,'tabs'):
            self.metrics.setVisible(self.tabs.currentIndex() in (1,2) and self.height()>=640)

    def _update_footer(self):
        if self.demo:self.sync_info.setText('샘플');return
        stamp='동기화 기록 없음'
        if self.last_sync:
            try:stamp='최근 동기화 '+datetime.fromisoformat(self.last_sync).astimezone(KST).strftime('%m.%d %H:%M')
            except ValueError:pass
        if self.main_stack.currentIndex()==1 and self.tabs.currentIndex()<3:
            kind={1:'movie',2:'assignment'}.get(self.tabs.currentIndex())
            total=sum(not kind or e.kind==kind for e in self._current_snapshot().events)
            stamp+=f' / 표시 {len(self._filtered)} / 불러옴 {total}건'
        self.sync_info.setText(stamp+(' / 일부 실패' if self.partial else ''))

    def select_day(self,day):
        self.selected_date=day;self.month=day.replace(day=1);self._render_visible()

    def shift_month(self,step):
        total=self.month.year*12+self.month.month-1+step
        self.month=date(total//12,total%12+1,1);self.selected_date=self.month;self._render_visible()

    def go_today(self):self.select_day(datetime.now(KST).date())

    def _set_busy(self,busy):
        self._busy=busy;self.sync_btn.setEnabled(not busy);self.login_button.setEnabled(not busy);self.account_button.setEnabled(not busy)
        self.add_task_button.setEnabled(not busy)
        self.sync_btn.setText('수집 중…' if busy else '동기화')
        if hasattr(self,'timetable'):self.timetable.set_read_only(busy or self.demo)

    def login(self):
        if self._busy or self._closing:return
        if self._logged_in:self.logout();return
        self._reauth_attempted=False;self._start_login(True)

    def _set_logged_in(self,value):
        self._logged_in=bool(value);self.login_button.setText('로그아웃' if value else '로그인')

    def _browser_command(self,command):
        if self._login_socket:
            self._login_socket.write((json.dumps({'command':command})+'\n').encode('utf-8'));self._login_socket.flush();return True
        return False

    def logout(self):
        self._logging_out=True;self._login_then_sync=False;self._sync_after_browser=False;self._movies_ready=False
        self.session_path.unlink(missing_ok=True);self._set_logged_in(False)
        if self._login_process:
            self._set_busy(True);self.status.setText('로그아웃 중');self._browser_command('logout')
        else:self._logging_out=False;self.status.setText('로그아웃 완료')

    def _start_login(self,then_sync):
        self._login_then_sync=then_sync;self._set_busy(True);self.status.setText('로그인 중')
        if self._login_process:
            self._browser_command('authenticate');return
        from PySide6.QtNetwork import QLocalServer
        self._login_server=QLocalServer(self);self._login_server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        server_name='bufs-browser-'+uuid4().hex
        if not self._login_server.listen(server_name):
            self._login_server.deleteLater();self._login_server=None;self._set_busy(False);self.status.setText('로그인 연결 실패');return
        self._login_server.newConnection.connect(self._browser_connected)
        self._login_output=self.appdir/f'login-{uuid4().hex}.dpapi'
        self._login_ready=self.appdir/f'login-{uuid4().hex}.ready'
        self._login_loading=QDialog(self,Qt.WindowType.Tool|Qt.WindowType.WindowStaysOnTopHint)
        self._login_loading.setWindowTitle('Calix 로그인');self._login_loading.setFixedSize(340,130)
        loading=QVBoxLayout(self._login_loading);loading.setContentsMargins(24,20,24,20)
        loading.addWidget(label('로그인 창을 열고 있어요…','section'))
        from PySide6.QtWidgets import QProgressBar
        bar=QProgressBar();bar.setRange(0,0);bar.setTextVisible(False);loading.addWidget(bar)
        self._login_loading.show();self._login_loading.raise_()
        self._login_ready_timer=QTimer(self);self._login_ready_timer.setInterval(100)
        self._login_ready_timer.timeout.connect(self._check_login_ready);self._login_ready_timer.start()
        proc=QProcess(self);self._login_process=proc
        proc.setProgram(sys.executable)
        args=[] if getattr(sys,'frozen',False) else [str(Path(__file__).resolve().parents[1]/'main.py')]
        args+=['--login','--session-output',str(self._login_output),'--ready-file',str(self._login_ready),'--theme',self.theme_key,'--control-server',server_name]
        if self.session_path.exists():args+=['--session-input',str(self.session_path)]
        # Restore the app's verified session; the child excludes stale CSRF
        # cookies and obtains a fresh CSRF token from the school itself.
        proc.setArguments(args)
        proc.readyReadStandardOutput.connect(lambda:proc.readAllStandardOutput())
        proc.readyReadStandardError.connect(lambda:proc.readAllStandardError())
        proc.finished.connect(self._login_finished)
        proc.errorOccurred.connect(self._login_error)
        proc.started.connect(self._grant_login_focus)
        proc.start()

    def _browser_connected(self):
        if self._login_socket:
            extra=self._login_server.nextPendingConnection();extra.abort();extra.deleteLater();return
        self._login_socket=self._login_server.nextPendingConnection();self._browser_buffer.clear()
        self._login_socket.readyRead.connect(self._browser_read)
        self._browser_read()
        if self._closing:self._browser_command('quit')

    def _browser_read(self):
        if not self._login_socket:return
        self._browser_buffer.extend(bytes(self._login_socket.readAll()))
        if len(self._browser_buffer)>16384:self._browser_buffer.clear();return
        while b'\n' in self._browser_buffer:
            line,_,tail=self._browser_buffer.partition(b'\n');self._browser_buffer=bytearray(tail)
            try:event=json.loads(line)
            except ValueError:continue
            if isinstance(event,dict):self._browser_event(event)

    def _browser_event(self,event):
        kind=event.get('event')
        if kind=='ready':self._close_login_loading();return
        if kind in ('authenticated','session_updated'):
            if self._logging_out or self._closing:return
            from .cookies import read_cookies,write_cookies,canvas_session_available
            rows=read_cookies(self._login_output)
            if not canvas_session_available(rows):return
            write_cookies(self.session_path,rows);self._set_logged_in(True)
            movie_became_ready=bool(event.get('movies_ready')) and not self._movies_ready
            self._movies_ready=bool(event.get('movies_ready'));self._close_login_loading()
            do_sync=(kind=='authenticated' and self._login_then_sync) or (movie_became_ready and self.partial)
            if kind=='authenticated':self._login_then_sync=False
            if kind=='authenticated':self.status.setText('로그인 완료')
            if self._thread is None:
                if kind=='authenticated':self._set_busy(False)
                if do_sync:self.manual_sync(auto=True)
            elif do_sync:self._sync_after_browser=True
        elif kind=='logged_out':
            self._logging_out=False;self._set_logged_in(False);self._set_busy(False);self.status.setText('로그아웃 완료')
        elif kind=='dismissed' and self._thread is None:
            self._login_then_sync=False;self._set_busy(False);self.status.setText('로그인 취소' if not self._logged_in else '로그인 유지 중')
        elif kind=='error':
            if self._thread is None:self._set_busy(False)
            self.status.setText('로그인 세션 저장 실패')

    def _grant_login_focus(self):
        if sys.platform=='win32' and self._login_process:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(int(self._login_process.processId()))

    def _check_login_ready(self):
        if self._login_ready.exists():self._close_login_loading()

    def _close_login_loading(self):
        timer=getattr(self,'_login_ready_timer',None)
        if timer:timer.stop();timer.deleteLater();self._login_ready_timer=None
        dialog=getattr(self,'_login_loading',None)
        if dialog:dialog.close();dialog.deleteLater();self._login_loading=None
        ready=getattr(self,'_login_ready',None)
        if ready:
            try:ready.unlink(missing_ok=True)
            except OSError:pass

    def _login_error(self,error):
        if error==QProcess.ProcessError.FailedToStart:
            self._finish_login(False,'로그인 창을 열지 못했습니다')

    def _login_finished(self,code,status):
        self._finish_login(False,'로그인 연결 종료')

    def _finish_login(self,accepted,message):
        proc=self._login_process
        if proc is None:return
        self._login_process=None;proc.deleteLater()
        self._close_login_loading()
        if self._login_socket:self._login_socket.abort();self._login_socket.deleteLater();self._login_socket=None
        if self._login_server:self._login_server.close();self._login_server.deleteLater();self._login_server=None
        if self._login_output.exists():self._login_output.unlink()
        if self._logging_out:self._logging_out=False;self._set_logged_in(False)
        if self._thread is None:self._set_busy(False)
        if not self._closing:self.status.setText('로그인 유지 중' if self._logged_in else message)
        if self._closing:QTimer.singleShot(0,self.close)

    def manual_sync(self,auto=False):
        if self._busy or self._closing:return
        if not auto:self._movie_reauth_attempted=False
        from .cookies import read_cookies,canvas_session_available
        cookies=read_cookies(self.session_path)
        if not canvas_session_available(cookies):self._start_login(True);return
        from .worker import SyncTask
        self._set_busy(True);self.status.setText('수집 중')
        task=SyncTask(cookies,self.store.path,self);self._thread=task
        task.progress.connect(self._progress);task.success.connect(self._sync_ok);task.error.connect(self._sync_failed)
        task.authentication_required.connect(self._sync_auth_required)
        task.finished.connect(self._sync_finished);task.start()

    @Slot(str)
    def _progress(self,text):
        if not self._closing:self.status.setText(text);self.status.setToolTip(tooltip_text(text))

    @Slot(object)
    def _sync_ok(self,result):
        if self._closing:return
        self._reauth_attempted=False
        self._set_logged_in(True)
        if Path(result['path'])!=self.store.path:
            self._page_filters.clear()
            self._undo_stack.clear();self.undo_button.setEnabled(False)
            self.store.close();self.store=Store(result['path'])
            self.settings['active_db']=self.store.path.name;write_settings(self.settings_path,self.settings)
        self.snapshot=result['snapshot'];self._sessions=result['sessions'];self.last_sync=result['last_sync'];self.partial=bool(result['warnings'])
        self.demo=False;self.demo_snapshot=None;self.demo_badge.hide();self._timetable_signature=None
        self._reload_type_filter();self._reload_course_filter();self.refresh()
        stats=result['stats'];self.status.setText('일부 실패' if self.partial else f"완료 / 추가 {stats['new']} / 변경 {stats['updated']}")
        checks=result.get('course_checks',{})
        for cid,report in checks.items():
            logging.info('영상 검증: 과목 %s / 확인 %s / 영상 %s / 완료 %s',cid,report['videos_verified'],report['videos'],report['watched'])
        movie_auth=result.get('movie_auth_required',False)
        if movie_auth and not self._movie_reauth_attempted:
            self._movie_reauth_attempted=True;self._reauth_requested=True
        notes=[note for note in result['warnings'] if '동영상 인증' not in note]
        if notes:
            box=QMessageBox(QMessageBox.Icon.Warning,'일부 조회 실패','기존 일정을 유지했습니다.',parent=self)
            box.setDetailedText('\n'.join(notes));box.exec();box.deleteLater()

    @Slot(str)
    def _sync_auth_required(self,message):
        if self._closing:return
        self._set_logged_in(False)
        if not self._reauth_attempted:
            self._reauth_requested=True;self._reauth_attempted=True
            self.status.setText('세션 만료 / 로그인 연결 중')
        else:self._sync_failed(message)

    @Slot(str)
    def _sync_failed(self,message):
        if self._closing:return
        self.status.setText('동기화 실패')
        box=QMessageBox(QMessageBox.Icon.Warning,'동기화 실패','로그인 상태와 연결을 확인하세요.',parent=self)
        box.setDetailedText(message);box.exec();box.deleteLater()

    @Slot()
    def _sync_finished(self):
        if self._closed:return
        task=self._thread;self._thread=None
        if task:task.deleteLater()
        self._set_busy(False)
        if self._closing:QTimer.singleShot(0,self.close)
        elif self._reauth_requested:
            self._reauth_requested=False;self._start_login(True)
        elif self._sync_after_browser:
            self._sync_after_browser=False;self.manual_sync(auto=True)

    def _reload(self):
        self.snapshot=Snapshot(self.store.events(),self.store.courses());self._reload_type_filter();self._reload_course_filter();self.refresh()

    def _ensure_diary(self):
        if self.diary is None:
            from .diary_view import DiaryPage
            self.diary=DiaryPage(self.appdir,self);layout=self.diary_holder.layout() or QVBoxLayout(self.diary_holder);layout.setContentsMargins(0,0,0,0);layout.addWidget(self.diary)
            self.diary.work_finished.connect(lambda:QTimer.singleShot(0,self.close) if self._closing else None)
        return self.diary

    def show_diary(self):
        self._ensure_diary()
        self.diary_nav.setChecked(True);self.heading.setText('일기장');self.add_task_button.hide();self.detail_button.hide();self.main_stack.slide_to(2)
        self._present_page()

    def backup_personal(self):
        if self._busy or (self.diary and self.diary.task):return
        if self.diary and not self.diary.flush():self.status.setText('일기를 먼저 저장하세요.');return
        path,_=QFileDialog.getSaveFileName(self,'개인 자료 백업',f'Calix-{date.today().isoformat()}.calix','Calix 백업 (*.calix)')
        if not path:return
        if not path.lower().endswith('.calix'):path+='.calix'
        from .local_backup import write_backup
        try:write_backup(path,self.store,self.appdir);self.status.setText('백업 저장됨 / 비밀 일기는 암호화 유지')
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'백업 실패',str(exc))

    def restore_personal(self):
        if self._busy or (self.diary and self.diary.task):return
        path,_=QFileDialog.getOpenFileName(self,'백업 복원','','Calix 백업 (*.calix)')
        if not path:return
        from .local_backup import read_backup,write_backup,restore_backup
        try:value=read_backup(path,self.store.get_meta('canvas_user_id'))
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'백업 확인 실패',str(exc));return
        message='개인 일정, 시간표, 일기를 백업 내용으로 교체합니다.\n비밀 일기는 백업 당시의 암호가 필요합니다.\n현재 자료는 복원 전에 자동 백업됩니다.'
        if 'holiday_overrides' in value:message=message.replace('개인 일정, 시간표','개인 일정, 공휴일 설정, 시간표')
        if QMessageBox.question(self,'백업 복원',message)!=QMessageBox.StandardButton.Yes:return
        if self.diary and not self.diary.flush():self.status.setText('일기를 먼저 저장하세요.');return
        recovery=self.appdir/'backups'/('복원전-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.calix');recovery.parent.mkdir(exist_ok=True)
        try:
            write_backup(recovery,self.store,self.appdir)
            if self.diary:
                self.diary.lock();self.diary.shutdown();self.diary.setParent(None);self.diary.deleteLater();self.diary=None
            restore_backup(value,self.store,self.appdir)
        except (OSError,ValueError, __import__('sqlite3').Error):
            # A recovery archive is deliberately retained for any partial disk failure.
            QMessageBox.warning(self,'복원 실패','복원을 완료하지 못했습니다. 복원 전 백업은 자료 폴더에 보관했습니다.');return
        self.holiday_calendar.reload();self._undo_stack.clear();self.undo_button.setEnabled(False);self._sessions=self.store.timetable();self._timetable_signature=None;self._reload()
        self.status.setText('백업 복원됨')
        if self.main_stack.currentIndex()==2:self.show_diary()

    def _focus_search(self):
        if self.main_stack.currentIndex()==2:self.diary.search.setFocus();return
        if self.main_stack.currentIndex()==0 or self.tabs.currentIndex()==3:self.open_details('all')
        self.search.setFocus()

    def add_manual(self,day=None,event=None):
        if self._busy:return
        if self.main_stack.currentIndex()==2:
            if self.diary.stack.currentWidget()==self.diary.workspace:self.diary.new_entry()
            return
        if self.demo:self.end_preview()
        from .manual_events import ManualEventDialog
        dialog=ManualEventDialog(self.store,self.snapshot.courses,day or self.selected_date,event,self) if event else self._take_ready_dialog('manual')
        if not event:
            from PySide6.QtCore import QDate
            selected=day or self.selected_date;dialog.date.setDate(QDate(selected.year,selected.month,selected.day))
        dialog.types_changed.connect(self._reload)
        if self._exec_dialog(dialog):
            values=dialog.values();old=self.store.manual_snapshot([event.key] if event else [])
            try:
                if event:keys=[self.store.save_manual_event(**values)]
                else:keys=self.store.create_manual_events(values,dialog.repeat.currentData(),dialog.repeat_count.value())
            except ValueError as exc:self.status.setText(str(exc));return
            self._push_undo('일정 저장',old,[] if event else keys);self._reload();self.status.setText('일정 저장됨')

    def manage_types(self):
        if self._busy:return
        from .manual_events import TypeManager
        dialog=self._take_ready_dialog('types');dialog.changed.connect(self._reload);self._exec_dialog(dialog)

    def manage_holidays(self):
        from .holiday_dialog import HolidayDialog
        from PySide6.QtCore import QDate
        dialog=self._take_ready_dialog('holiday');selected=self.selected_date
        if dialog.year.findData(selected.year)<0:dialog.year.addItem(f'{selected.year}년',selected.year)
        dialog.year.setCurrentIndex(dialog.year.findData(selected.year));dialog.day.setDate(QDate(selected.year,selected.month,selected.day))
        dialog.changed.connect(self.refresh);self._exec_dialog(dialog)

    def manage_special_dates(self):
        from .special_dates_dialog import SpecialDatesDialog
        dialog=self._take_ready_dialog('special');dialog.changed.connect(self.refresh);self._exec_dialog(dialog)

    def complete_manual(self,event,completed):
        if self._busy or not event.manual:return
        old=self.store.manual_snapshot([event.key]);self.store.complete_manual_event(event.key,completed)
        self._push_undo('완료 상태 변경',old);self._reload();self.status.setText('일정 완료' if completed else '미완료로 변경됨')

    def delete_manual(self,event):
        if self._busy:return
        whole=False
        if event.series_id:
            box=QMessageBox(self);box.setWindowTitle('반복 일정 삭제');box.setText('어떤 일정을 삭제할까요?')
            one=box.addButton('이번 일정',QMessageBox.ButtonRole.AcceptRole);all_items=box.addButton('전체 반복',QMessageBox.ButtonRole.DestructiveRole);box.addButton('취소',QMessageBox.ButtonRole.RejectRole);box.exec()
            chosen=box.clickedButton();box.deleteLater()
            if chosen not in (one,all_items):return
            whole=chosen==all_items
        elif QMessageBox.question(self,'일정 삭제','선택한 일정을 삭제할까요?')!=QMessageBox.StandardButton.Yes:return
        old=self.store.manual_snapshot(self.store.manual_keys(event.key,whole));self.store.remove_manual_event(event.key,whole)
        self._push_undo('일정 삭제',old);self._reload();self.status.setText('일정 삭제됨')

    def _push_undo(self,label,data,clear_keys=()):
        self._undo_stack.append((label,data,tuple(clear_keys)))
        while len(self._undo_stack)>20 or sum(len(item[1]) for item in self._undo_stack)>8*1024*1024:self._undo_stack.pop(0)
        self.undo_button.setEnabled(bool(self._undo_stack));self.undo_button.setToolTip(label+' 되돌리기')

    def undo_manual(self):
        if self._busy or not self._undo_stack:return
        label,data,keys=self._undo_stack.pop();self.store.restore_manual_snapshot(data,keys);self._reload();self.status.setText(label+' 되돌림');self.undo_button.setEnabled(bool(self._undo_stack))

    def _exec_dialog(self,dialog):
        try:return dialog.exec()==QDialog.DialogCode.Accepted
        finally:dialog.deleteLater()

    def configure(self):
        if self._busy:return
        try:before=read_account()
        except Exception:before=''
        dialog=self._take_ready_dialog('settings');dialog.student.setText(before);dialog.remove.setEnabled(bool(before))
        if self._exec_dialog(dialog):
            try:after=read_account()
            except Exception:after=before
            if before!=after:
                self.logout()
                self.status.setText('계정 변경 / 다시 로그인하세요')
            else:self.status.setText('저장됨')

    def edit_aliases(self):
        if self.demo or self._busy:return
        if self._exec_dialog(self._take_ready_dialog('aliases')):
            self._timetable_signature=None;self._reload()

    def preview(self):
        if self._busy:return
        from .demo import data
        courses,batches=data();self.demo_snapshot=Snapshot([e for group in batches.values() for e in group],courses)
        self.demo=True;self.demo_badge.show();self._timetable_signature=None;self._reload_course_filter();self.refresh()

    def end_preview(self):
        self.demo=False;self.demo_snapshot=None;self.demo_badge.hide();self._timetable_signature=None;self._reload_course_filter();self.refresh()

    def open_event(self,event):
        if not event:return
        self.show_calendar_details(event.due.date() if event.due else self.selected_date,[event],QCursor.pos())

    def show_calendar_details(self,day,rows,point):
        if not rows:return
        if self._event_popover and not self._event_popover.close():return
        from .event_popover import EventPopover
        self.select_day(day)
        popup=EventPopover(day,rows,self.store.event_types(),self.save_event_properties,self,read_only=self.demo or self._busy)
        self._event_popover=popup
        popup.original_requested.connect(self.open_original)
        popup.advanced_requested.connect(self._advanced_event)
        popup.list.completion_requested.connect(self._complete_popup_event)
        popup_id=id(popup)
        popup.destroyed.connect(lambda _obj=None,token=popup_id:self._clear_event_popover(token))
        popup.show_near(point)
        return popup

    def show_calendar_group(self,day,rows,point):
        all_rows=self._buckets.get(day,rows)
        popup=self.show_calendar_details(day,all_rows,point)
        if popup and rows:
            types={popup._type_key(row) for row in rows}
            if len(types)==1:popup.kind_filter.setCurrentIndex(max(0,popup.kind_filter.findData(next(iter(types)))))
            for i,event in enumerate(popup.list.event_model.rows):
                if event.key==rows[0].key:popup.list.setCurrentIndex(popup.list.model().index(i));break

    def _clear_event_popover(self,popup_id):
        if self._event_popover is not None and id(self._event_popover)==popup_id:self._event_popover=None

    def _advanced_event(self,event):
        if self.demo or self._busy:return
        if self._event_popover and not self._event_popover.close():return
        self.add_manual(event=self.snapshot.by_key.get(event.key,event))

    def _complete_popup_event(self,event,completed):
        popup=self._event_popover
        if self.demo or self._busy or not popup or not popup.flush():return
        self.complete_manual(event,completed)
        updated=self.snapshot.by_key.get(event.key)
        if updated:popup.replace_event(updated)

    def save_event_properties(self,event,title,type_id,note):
        if self.demo or self._busy:raise ValueError('동기화가 끝난 뒤 수정하세요.')
        latest=self.snapshot.by_key.get(event.key)
        if latest is None:raise ValueError('일정을 찾지 못했습니다.')
        if latest.manual:
            old=self.store.manual_snapshot([latest.key])
            self.store.save_manual_event(title,type_id,latest.due_at,latest.course_id,note,latest.completed,latest.key)
            self._push_undo('일정 편집',old)
        else:self.store.save_event_details(latest.key,title,type_id,note)
        self._reload();return self.snapshot.by_key.get(latest.key)

    def open_original(self,event):
        from .parsers import safe_url
        url=safe_url(event.url)
        if url:QDesktopServices.openUrl(QUrl(url))

    def event_menu(self,view,pos):
        event=view.indexAt(pos).data(EVENT_ROLE)
        if event is None:return
        if event.manual:
            menu=QMenu(self);edit=menu.addAction('일정 편집');done=menu.addAction('미완료로 변경' if event.completed else '완료로 표시');remove=menu.addAction('일정 삭제')
            chosen=menu.exec(view.viewport().mapToGlobal(pos));menu.deleteLater()
            if chosen==edit:self.add_manual(event=event)
            elif chosen==done:self.complete_manual(event,not event.completed)
            elif chosen==remove:self.delete_manual(event)
            return
        menu=QMenu(self);properties=menu.addAction('이름 / 유형 / 메모');original=menu.addAction('원본 열기');star=menu.addAction('즐겨찾기 해제' if event.starred else '즐겨찾기')
        memo=menu.addAction('메모');copy=menu.addAction('마감일 복사')
        star.setEnabled(not self.demo and not self._busy);memo.setEnabled(not self.demo and not self._busy)
        chosen=menu.exec(view.viewport().mapToGlobal(pos));menu.deleteLater()
        if chosen is None:return
        if chosen==properties:self.open_event(event)
        elif chosen==original:self.open_original(event)
        elif chosen==copy:QApplication.clipboard().setText(event.title+' / '+(event.due.strftime('%m/%d %H:%M') if event.due else '기한 없음'))
        elif chosen==star:self.store.set_starred(event.key,not event.starred);self._reload()
        elif chosen==memo:
            dialog=MemoDialog(event,self)
            if self._exec_dialog(dialog):self.store.set_note(event.key,dialog.edit.toPlainText());self._reload()

    def _build_timetable(self):
        from .timetable_view import TimetableView
        self._timetable_built=True;layout=QVBoxLayout(self.timetable_page);layout.setContentsMargins(0,0,0,0)
        self.timetable=TimetableView();layout.addWidget(self.timetable)
        self.timetable.add_requested.connect(self.add_session);self.timetable.edit_requested.connect(self.edit_session)
        self.timetable.remove_requested.connect(self.remove_session);self.timetable.color_changed.connect(self._color_session)
        self.timetable.move_requested.connect(self._move_session);self.timetable.slot_requested.connect(self._add_at_slot)

    def _refresh_timetable(self):
        if not self._timetable_built:return
        sessions=self._sessions;courses=self._current_snapshot().courses;names={c.id:c.name for c in courses}
        if self.demo:
            sessions=[dict(id=-i-1,course_id=courses[i%len(courses)].id,day=day,start_time=start,end_time=end,professor='',room=room,color=color)
                for i,(day,start,end,room,color) in enumerate([(0,'09:00','10:30','A201','#7582E6'),(1,'10:00','12:00','B304','#459CD4'),(2,'09:00','10:30','A201','#7582E6'),(3,'13:00','15:00','D102','#3AA68E'),(4,'11:00','12:30','C205','#CF779A'),(0,'14:00','15:30','E301','#CA9A46')])] if courses else []
        workloads=defaultdict(lambda:[0,0])
        for event in self._current_snapshot().pending():
            if event.kind in ('assignment','movie'):workloads[event.course_id][0 if event.kind=='assignment' else 1]+=1
        signature=(self.demo,tuple(names.items()),tuple(tuple(r.items()) for r in sessions),tuple(sorted((key,tuple(value)) for key,value in workloads.items())),self.theme_key,datetime.now(KST).date())
        if signature==self._timetable_signature:self.timetable.surface.update();return
        self._timetable_signature=signature;self.timetable.set_read_only(self.demo or self._busy);self.timetable.set_data(sessions,names,workloads)

    def _selected_session(self,item_id=None):
        if not self._timetable_built:return None
        item_id=self.timetable.selected_id if item_id is None else item_id
        return next((r for r in self._sessions if r['id']==item_id),None)

    def _validate_session(self,values,item_id=None):
        try:self.store.validate_timetable(values[1],values[2],values[3],item_id)
        except ValueError as exc:return str(exc)
        return ''

    def _add_at_slot(self,day,start):self.add_session(day,start)

    def add_session(self,day=None,start=None):
        if self.demo or self._busy:return
        if not self.snapshot.courses:self.status.setText('먼저 동기화하세요');return
        dialog=self._take_ready_dialog('session');dialog.validation=lambda values:self._validate_session(values)
        if day is not None:dialog.days[day].setChecked(True)
        if start is not None:
            from PySide6.QtCore import QTime
            from .schedule_colors import minutes,clock
            dialog.start.setTime(QTime.fromString(start,'HH:mm'));dialog.end.setTime(QTime.fromString(clock(min(1439,minutes(start)+60)),'HH:mm'))
        if self._exec_dialog(dialog):self._store_session(dialog.values(),color=dialog.color_value)

    def edit_session(self,item_id=None):
        if self.demo or self._busy:return
        row=self._selected_session(item_id)
        if not row:return
        dialog=SessionDialog(self.snapshot.courses,row,self);dialog.validation=lambda values:self._validate_session(values,row['id'])
        if self._exec_dialog(dialog):self._store_session(dialog.values(),row['id'],dialog.color_value)

    def _store_session(self,values,item_id=None,color=''):
        try:
            self.store.add_timetable(*values,item_id=item_id,color=color);self._sessions=self.store.timetable();self.status.setText('시간표 저장됨')
        except ValueError as exc:self.status.setText(str(exc));self.status.setToolTip(tooltip_text(str(exc)))
        self._timetable_signature=None;self._refresh_timetable()

    def _color_session(self,item_id,color):
        if self.demo or self._busy:
            self._timetable_signature=None;self._refresh_timetable();return
        self.store.set_timetable_color(item_id,color);self._sessions=self.store.timetable();self._refresh_timetable();self.status.setText('수업 색상 저장됨')

    def _move_session(self,item_id,day,start,end):
        row=self._selected_session(item_id)
        if row and not self.demo and not self._busy:self._store_session((row['course_id'],day,start,end,row['professor'],row['room']),item_id,row.get('color',''))
        else:self._timetable_signature=None;self._refresh_timetable()

    def remove_session(self,item_id=None):
        if self.demo or self._busy:return
        row=self._selected_session(item_id)
        if row and QMessageBox.question(self,'수업 삭제','선택한 수업을 삭제할까요?')==QMessageBox.StandardButton.Yes:
            self.store.remove_timetable(row['id']);self._sessions=self.store.timetable();self._refresh_timetable();self.status.setText('수업 삭제됨')

    def show_changes(self):
        dialog=QDialog(self);dialog.setWindowTitle('변경 기록');dialog.resize(680,430);v=QVBoxLayout(dialog)
        changes=self.store.recent_changes();table=QTableWidget(len(changes),3);table.setHorizontalHeaderLabels(['시각','구분','내용'])
        table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch);table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for i,c in enumerate(changes):
            stamp=datetime.fromisoformat(c['changed_at']).astimezone(KST).strftime('%m.%d %H:%M')
            kind={'new':'추가','updated':'변경','archived':'숨김'}.get(c['change_type'],c['change_type'])
            for j,value in enumerate((stamp,kind,c['detail'])):table.setItem(i,j,QTableWidgetItem(value))
        v.addWidget(table);self._exec_dialog(dialog)

    def export(self):
        if self.demo:return
        from .exporters import export_ics
        kind={1:'movie',2:'assignment'}.get(self.tabs.currentIndex());rows=[e for e in self._filtered if not kind or e.kind==kind]
        if not any(e.due for e in rows):self.status.setText('내보낼 일정 없음');return
        path,_=QFileDialog.getSaveFileName(self,'ICS 저장','학습일정.ics','iCalendar (*.ics)')
        if not path:return
        if not path.lower().endswith('.ics'):path+='.ics'
        answer=QMessageBox.question(self,'ICS 저장','완료 일정도 포함할까요?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No|QMessageBox.StandardButton.Cancel)
        if answer==QMessageBox.StandardButton.Cancel:return
        try:self.status.setText(f"{export_ics(rows,path,answer==QMessageBox.StandardButton.Yes)}건 저장")
        except OSError as exc:QMessageBox.warning(self,'저장 실패',str(exc))

    def credits(self):
        existing=self._dialogs.get('credits')
        if existing:existing.raise_();existing.activateWindow();return
        dialog=self._take_ready_dialog('credits');self._dialogs['credits']=dialog
        dialog.destroyed.connect(lambda:self._dialogs.pop('credits',None));dialog.open()

    def open_logs(self):
        path=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Calix'/'logs'
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def check_updates(self):
        existing=self._dialogs.get('updates')
        if existing:existing.show();existing.raise_();existing.activateWindow();return
        from .update_dialog import UpdateDialog
        dialog=UpdateDialog(self);self._dialogs['updates']=dialog
        dialog.install_requested.connect(self._install_update)
        dialog.destroyed.connect(lambda:self._dialogs.pop('updates',None));dialog.open()

    def _install_update(self,path):
        self._update_installer=path
        self.request_exit()
        if not self._exit_confirmed:self._update_installer=None

    def moveEvent(self,event):
        super().moveEvent(event)
        root=self.centralWidget()
        if root and hasattr(root,'repair_after_move'):root.repair_after_move()

    def closeEvent(self,event):
        if self._closed:event.accept();return
        if not self._exit_confirmed:event.ignore();return
        if not self._shutdown_started:
            self._shutdown_started=True;self._closing=True
            self.setEnabled(False)
            self.search_timer.stop();self.local_clock.stop();self.home.hero.clock.stop();self.main_stack._settle()
            self.exit_button.setEnabled(False);self.status.setText('종료 중')
            if self._thread and self._thread.isRunning():self._thread.cancel()
            if self._login_process:
                proc=self._login_process;self._browser_command('quit')
                QTimer.singleShot(1500,lambda:self._login_process is proc and proc.kill())
            self._shutdown_poll=QTimer(self);self._shutdown_poll.setInterval(50)
            self._shutdown_poll.timeout.connect(self.close);self._shutdown_poll.start()
        if not self._shutdown_forms_ready:
            if self._event_popover and not self._event_popover.close():
                self._cancel_shutdown();self.status.setText('변경 사항을 저장하지 못했습니다.');event.ignore();return
            if self.diary and not self.diary.prepare_close():
                if not self.diary.task:
                    self._cancel_shutdown();self.status.setText('일기를 저장하지 못했습니다.')
                event.ignore();return
            self._shutdown_forms_ready=True
        if self._thread and self._thread.isRunning():
            event.ignore();return
        if self._login_process:
            event.ignore();return
        self._shutdown_poll.stop()
        if self._ready_dialogs:self._ready_dialogs.shutdown()
        installer=getattr(self,'_update_installer',None)
        if installer:
            # Transfer the verified download to the installer before closing its dialog.
            update=self._dialogs.get('updates')
            if update:update.installer=None
        for dialog in list(self._dialogs.values()):dialog.close()
        try:
            self.settings.update(window_width=self.width(),window_height=self.height())
            write_settings(self.settings_path,self.settings)
        except OSError:logging.exception('설정 저장 실패')
        self.video_list.event_model.set_events([]);self.assignment_list.event_model.set_events([]);self.day_list.event_model.set_events([])
        from .app_identity import clear_window_identity
        clear_window_identity(self)
        if self._tray:self._tray.hide()
        if self.diary:self.diary.shutdown()
        self.holiday_calendar.close();self.store.close();self._closed=True;event.accept()
        if installer:
            started=QProcess.startDetached(installer,[])[0]
            if not started:
                QMessageBox.warning(None,'업데이트','설치 프로그램을 실행하지 못했습니다. 릴리즈에서 다시 내려받으십시오.')
        if self._quit_on_close:QTimer.singleShot(0,QApplication.instance().quit)

    def _has_pending_changes(self):
        return bool((self.diary and (self.diary.dirty or self.diary.task or getattr(self.diary,'_pending_secret',None))) or
                    (self._event_popover and self._event_popover.dirty) or
                    (self._thread and self._thread.isRunning()))

    def _confirm_exit(self,pending):
        box=QMessageBox(self);box.setWindowTitle('Calix')
        box.setText('변경 사항이 있습니다. 종료하시겠습니까?' if pending else '종료하시겠습니까?')
        save=box.addButton('저장하고 종료' if pending else '종료',QMessageBox.ButtonRole.AcceptRole)
        discard=box.addButton('바로 종료',QMessageBox.ButtonRole.DestructiveRole) if pending else None
        cancel=box.addButton('취소',QMessageBox.ButtonRole.RejectRole);box.setDefaultButton(cancel);box.setEscapeButton(cancel)
        try:
            box.exec();chosen=box.clickedButton()
            return 'save' if chosen is save else 'discard' if discard is not None and chosen is discard else 'cancel'
        finally:box.deleteLater()

    def request_exit(self,checked=False):
        if self._closing or self._exit_prompt_open:return
        timers=[timer for timer in (self.diary.save_timer if self.diary else None,
                                   self._event_popover.timer if self._event_popover else None) if timer and timer.isActive()]
        for timer in timers:timer.stop()
        self._exit_prompt_open=True
        try:
            choice=self._confirm_exit(self._has_pending_changes())
            if choice=='cancel':return
            if choice=='discard':
                if self._event_popover:self._event_popover.discard_pending()
                if self.diary:self.diary.discard_pending()
            else:
                if self._event_popover and not self._event_popover.flush():return
                if self.diary and not self.diary.flush():return
            self._exit_confirmed=True;self._quit_on_close=True;self.close()
        finally:
            self._exit_prompt_open=False
            if not self._exit_confirmed:
                for timer in timers:timer.start()

    def _cancel_shutdown(self):
        self._update_installer=None
        self._shutdown_poll.stop();self._shutdown_started=False;self._shutdown_forms_ready=False;self._closing=False;self._exit_confirmed=False
        self.setEnabled(True)
        self.exit_button.setEnabled(True);self.local_clock.start()
        if self.home.isVisible():self.home.hero.clock.start()

    def dispose(self):
        """Close an owned diagnostic window without an interactive prompt."""
        self._exit_confirmed=True;self._quit_on_close=False;self.close()
