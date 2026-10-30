"""Five coherent native themes; all custom painters share the same tokens."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QIcon,QPainter,QPalette,QPen,QPixmap
from PySide6.QtWidgets import QApplication

VERSION='1.2.0-r3'
THEME_NAMES={'pink':'핑크','sky':'스카이블루','mint':'민트','purple':'퍼플','dark':'다크'}
THEMES={
 'pink':dict(bg='#FFF6FA',side='#FFFDFE',surface='#FFFFFF',soft='#FCE7F0',hover='#FFF0F6',ink='#342431',muted='#836875',line='#EDDCE5',accent='#B13970',onaccent='#FFFFFF',hero='#F8D7E7',hero2='#FFEDF5'),
 'sky':dict(bg='#F7F8FA',side='#FCFCFD',surface='#FFFFFF',soft='#EEF0FB',hover='#F1F3FA',ink='#20242C',muted='#6D7480',line='#E6E8EE',accent='#586BD6',onaccent='#FFFFFF',hero='#E8EBF8',hero2='#F2F4FA'),
 'mint':dict(bg='#F3FAF7',side='#FEFFFE',surface='#FFFFFF',soft='#DFF2E9',hover='#EAF7F0',ink='#233D34',muted='#637E73',line='#D8E9E0',accent='#217A5B',onaccent='#FFFFFF',hero='#CEECDF',hero2='#EDF9F3'),
 'purple':dict(bg='#F7F4FF',side='#FEFDFF',surface='#FFFFFF',soft='#ECE3FC',hover='#F1EBFE',ink='#352B4D',muted='#7C7091',line='#E4DDF1',accent='#7651AE',onaccent='#FFFFFF',hero='#E3D7F8',hero2='#F5EEFF'),
 'dark':dict(bg='#11151D',side='#151A23',surface='#1C232F',soft='#2B384C',hover='#253145',ink='#EBF0F9',muted='#9EACC2',line='#313D50',accent='#AECDF6',onaccent='#18273C',hero='#263F60',hero2='#1B293B'),
}
DEFAULT_THEME='sky'

def type_tokens(color):
    c=colors();accent=QColor(color or c['accent']);base=QColor(c['surface']);dark=base.lightness()<128
    mix=.22 if dark else .12
    bg=QColor(*[round(accent.getRgb()[i]*mix+base.getRgb()[i]*(1-mix)) for i in range(3)])
    ink=accent.lighter(150) if dark else accent.darker(155)
    if dark and ink.lightness()<130:ink=QColor('#CCD7EC')
    return dict(ink=ink.name(),bg=bg.name(),line=accent.name())

def colors():
    app=QApplication.instance()
    return theme_tokens(app.property('bufsTheme') if app else DEFAULT_THEME)


def theme_tokens(key):
    c=dict(THEMES.get(key,THEMES[DEFAULT_THEME]));app=QApplication.instance()
    if app and app.property('calixGlass'):
        muted=QColor(c['muted']);c['muted']=(muted.lighter(112) if QColor(c['bg']).lightness()<128 else muted.darker(118)).name()
    return c


def category_colors(key=None):
    app=QApplication.instance();key=key or (app.property('bufsTheme') if app else DEFAULT_THEME)
    if key=='dark':
        return dict(assignment_ink='#F3CC8B',assignment_bg='#3B3020',assignment_line='#C89C55',movie_ink='#BED9FF',movie_bg='#21344D',movie_line='#719BD1')
    return dict(assignment_ink='#8C521A',assignment_bg='#FFF5E5',assignment_line='#BF8138',movie_ink='#345D9C',movie_bg='#EFF5FF',movie_line='#6991CC')

def glass_enabled():
    app=QApplication.instance()
    return bool(app and app.property('calixGlass'))


def stylesheet(key=DEFAULT_THEME):
    c=theme_tokens(key);c.update(category_colors(key))
    app=QApplication.instance();c['font_family']=(app.property('bufsFontFamily') if app else None) or 'Pretendard Variable';c['feast_ink']='#C3A6EC' if QColor(c['bg']).lightness()<128 else '#765197';c['danger_ink']='#F2A6B8' if QColor(c['bg']).lightness()<128 else '#A93B60'
    base='''
QWidget {{ font-family:"{font_family}"; color:{ink}; font-size:14px; }}
QListView#propertyOptions {{background:{surface};border:0;border-radius:8px;padding:2px;outline:0;}}
QListView#propertyOptions::item {{padding:0;margin:0;border:0;}}
QLineEdit#propertySearch {{padding:8px 12px;min-height:20px;}}
QTableView#checklistTable {{ background:{surface};alternate-background-color:{surface};border:1px solid {line};border-radius:12px;selection-background-color:{soft};selection-color:{ink}; }}
QTableView#checklistTable::item {{ padding:7px 9px;border-bottom:1px solid {line}; }}
QTableView#checklistTable::item:focus {{border:1px solid {accent};}}
QFrame#timeInput {{background:{surface};border:1px solid {line};border-radius:10px;}}
QFrame#timeInput[invalid="true"] {{border:1px solid #D94B61;}}
QFrame#timeInput:focus {{border:1px solid {accent};}}
QTabBar::tab {{ padding:9px 17px;border:0;border-bottom:2px solid transparent;color:{muted};background:transparent; }}
QTabBar::tab:selected {{ color:{accent};border-bottom:2px solid {accent};font-weight:600; }}
QMainWindow, QDialog, QWidget#root, QWidget#page {{ background:{bg}; }}
QLabel {{ background:transparent; }}
QFrame#sidebar {{ background:{side}; border-right:1px solid {line}; }}
QLabel#brand {{ font-size:20px; font-weight:700; }}
QLabel#eyebrow {{ font-size:12px; color:{muted}; }}
QLabel#muted, QLabel#subtle {{ color:{muted}; font-size:12px; }}
QLabel#heading {{ font-size:28px; font-weight:700; }}
QLabel#month {{ font-size:21px; font-weight:700; }}
QLabel#section {{ font-size:16px; font-weight:700; }}
QLabel#metric {{ font-size:26px; font-weight:700; }}
QLabel#badge {{ background:{soft}; color:{accent}; border-radius:7px; padding:4px 9px; font-size:12px; }}
QFrame#panel, QFrame#metricCard {{ background:{surface}; border:1px solid {line}; border-radius:16px; }}
QFrame#creditHero {{ background:{hero}; border:1px solid {line}; border-radius:18px; }}
QLabel#creator {{ font-size:30px; font-weight:700; }}
QFrame#welcomeHero {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {hero},stop:1 {hero2}); border:0; border-radius:24px; }}
QLabel#homeGreeting {{ font-size:32px; font-weight:700; }}
QFrame#orbCard {{ background:{surface}; border:1px solid {line}; border-radius:18px; }}
QLabel#orbitDate {{ color:{accent}; font-size:34px; font-weight:600; }}
QLabel#summaryNumber {{ font-size:36px; font-weight:700; }}
QLabel#summaryArrow {{ color:{accent}; font-size:19px; }}
QPushButton#homeSummary {{ background:{surface}; border:1px solid {line}; border-radius:20px; padding:0; min-height:104px; }}
QPushButton#homeSummary:hover, QPushButton#homeSummary:focus {{ background:{hover}; border-color:{accent}; }}
QPushButton, QToolButton {{ background:{surface}; color:{ink}; border:1px solid {line}; border-radius:8px; padding:8px 13px; min-height:20px; }}
QPushButton:hover, QToolButton:hover {{ background:{hover}; border-color:{accent}; }}
QPushButton:pressed {{ background:{soft}; }}
QPushButton:disabled {{ color:{muted}; background:{bg}; border-color:{line}; }}
QPushButton#primary {{ background:{accent}; color:{onaccent}; border-color:{accent}; font-weight:700; }}
QPushButton#quiet {{ background:transparent; border-color:transparent; text-align:left; }}
QPushButton#quiet:hover {{ background:{soft}; }}
QPushButton#nav {{ background:transparent; border:0; padding:8px 12px; text-align:left; color:{muted}; font-weight:400; }}
QPushButton#nav:hover {{ background:{hover}; color:{ink}; }}
QPushButton#nav:checked {{ background:{soft}; color:{accent}; font-weight:400; }}
QPushButton#ghost {{ background:transparent;border-color:transparent; }}
QPushButton#danger {{ background:transparent; border-color:#BC8193; color:{danger_ink}; }}
QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QTimeEdit, QSpinBox {{ background:{surface}; border:1px solid {line}; border-radius:9px; padding:7px 10px; min-height:22px; selection-background-color:{soft}; selection-color:{ink}; }}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color:{accent}; }}
QComboBox::drop-down {{ border:0; width:24px; }}
QComboBox QAbstractItemView {{ background:{surface}; border:1px solid {line}; selection-background-color:{soft}; selection-color:{ink}; padding:4px; }}
QListView, QTableWidget {{ background:{surface}; border:1px solid {line}; border-radius:12px; outline:0; }}
QListView::item {{ border:1px solid {line}; border-radius:9px; background:{surface}; margin:4px 7px; padding:8px 11px; }}
QListView::item:hover {{ background:{hover}; }}
QListView::item:selected {{ background:{soft}; color:{ink}; border-color:{accent}; }}
QCalendarWidget {{ background:{surface}; border:0; border-radius:10px; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{background:{surface};}}
QCalendarWidget QToolButton {{background:transparent;border:0;border-radius:6px;padding:4px 8px;min-height:24px;color:{ink};}}
QCalendarWidget QToolButton:hover {{background:{hover};}}
QCalendarWidget QToolButton::menu-indicator {{image:none;}}
QCalendarWidget QSpinBox {{background:{surface};border:1px solid {line};padding:2px 6px;}}
QCalendarWidget QTableView {{ background:{surface}; color:{ink}; border:0; outline:0; selection-background-color:{soft}; selection-color:{ink}; }}
QLabel#assignmentBadge {{ color:{assignment_ink}; background:{assignment_bg}; border:1px solid {assignment_line}; border-radius:5px; padding:1px 6px; font-size:12px; font-weight:600; }}
QLabel#movieBadge {{ color:{movie_ink}; background:{movie_bg}; border:1px solid {movie_line}; border-radius:5px; padding:1px 6px; font-size:12px; font-weight:600; }}
QLabel#assignmentBadge[compact="true"], QLabel#movieBadge[compact="true"] {{ padding:0; border-radius:2px; }}
QHeaderView::section {{ background:{soft}; color:{muted}; padding:8px; border:0; }}
QTableWidget::item {{ padding:4px; border-bottom:1px solid {line}; }}
QScrollArea {{ border:0; background:transparent; }}
QScrollBar:vertical {{ background:transparent; width:7px; margin:3px; }}
QScrollBar::handle:vertical {{ background:{line}; border-radius:3px; min-height:28px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ height:7px; background:transparent; }}
QScrollBar::handle:horizontal {{ background:{line}; border-radius:3px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
QMenuBar, QMenu {{ background:{side}; color:{ink}; }}
QMenu {{ border:1px solid {line}; padding:5px; }}
QMenu::item {{ padding:8px 28px 8px 12px; border-radius:5px; }}
QMenu::item:selected, QMenuBar::item:selected {{ background:{soft}; }}
QMenu::separator {{ height:1px; background:{line}; margin:5px; }}
QToolTip {{ background:{surface}; color:{ink}; border:1px solid {line}; padding:6px; }}
QSplitter::handle {{ background:transparent; }}
QPushButton#homeCategory {{ min-height:20px; padding:4px 9px; border-radius:6px; font-size:12px; }}
QPushButton#homeCategory:checked {{ background:{soft}; border-color:{accent}; color:{accent}; }}
QPushButton#homeCategory[category="assignment"]:checked {{ background:{assignment_bg}; border-color:{assignment_line}; color:{assignment_ink}; }}
QPushButton#homeCategory[category="movie"]:checked {{ background:{movie_bg}; border-color:{movie_line}; color:{movie_ink}; }}
QTableView#scheduleTable {{ background:{surface}; border:1px solid {line}; border-radius:12px; gridline-color:{line}; }}
QTableView#scheduleTable::item {{ padding:6px; border-bottom:1px solid {line}; }}
QHeaderView::section {{ background:{soft}; color:{muted}; border:0; padding:9px 6px; font-size:12px; }}
QLabel#brand {{ font-size:28px; font-weight:700; color:{ink}; }}
QLabel#heading {{ font-size:27px; font-weight:700; }}
QLabel#caption {{ font-size:12px; color:{muted}; }}
QLabel#fieldLabel {{ font-size:13px; font-weight:600; color:{ink}; }}
QLabel#formError {{ font-size:12px; color:#B34C67; }}
QPushButton:focus, QToolButton:focus, QLineEdit:focus, QComboBox:focus, QTimeEdit:focus {{ border:1px solid {accent}; }}
QPushButton#nav {{ min-height:28px; border-radius:8px; padding:7px 12px; }}
QPushButton#nav:checked {{ background:{soft};color:{accent}; }}
QPushButton#metricCard {{ min-height:80px;background:{surface};border:1px solid {line};border-radius:14px;padding:0; }}
QPushButton#metricCard:hover,QPushButton#metricCard[active="true"] {{ border-color:{accent};background:{hover}; }}
QToolButton#commandMenu {{ background:{surface};border:1px solid {line};border-radius:10px;padding:8px 12px; }}
QToolButton#commandMenu::menu-indicator {{ image:none; }}
QTimeEdit#timeInput,QSpinBox#countInput {{ padding-right:36px;min-height:22px; }}
QToolButton#timeStep {{ background:transparent;border:0;border-radius:5px;padding:0;min-height:0; }}
QToolButton#timeStep:hover {{ background:{soft}; }}
QToolButton#timeStep:pressed {{ background:{line}; }}
QPushButton#dateInput {{ text-align:left; }}
QListWidget#typeList::item {{ padding:8px;border:0;border-radius:8px; }}
QListWidget#typeList::item:selected {{ background:{soft};color:{accent}; }}
QFrame#boardCard,QFrame#inspector {{ background:{surface};border:1px solid {line};border-radius:18px; }}
QWidget#weekSurface {{ background:{surface}; }}
QLabel#weekDay {{ font-size:13px;font-weight:600;color:{ink}; }}
QLabel#weekDayToday {{ font-size:13px;font-weight:600;color:{accent};background:{soft};border-radius:10px; }}
QLabel#timeAxis {{ font-size:12px;color:{muted}; }}
QLabel#classTitle {{ font-size:14px;font-weight:600;color:{ink}; }}
QLabel#classTime,QLabel#classRoom {{ font-size:12px;color:{muted}; }}
QPushButton#segment,QPushButton#dayChoice {{ min-height:22px;padding:6px 10px;border-radius:8px; }}
QPushButton#segment:checked,QPushButton#dayChoice:checked {{ background:{soft};border-color:{accent};color:{accent}; }}
QPushButton#zoomButton,QToolButton#zoomButton {{ min-height:0;padding:0;border-radius:8px;font-size:17px; }}
QLabel#creditVersion {{ background:{soft};color:{accent};border:1px solid {line};border-radius:10px;padding:5px 12px; }}
QFrame#creditHero {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #172B48,stop:1 #2B527D);border-radius:20px;border:0; }}
QLabel#creatorMark {{ background:#365878;color:#FFFFFF;border:1px solid #7796B8;border-radius:48px;font-size:25px;font-weight:700; }}
QLabel#creatorName {{ color:#FFFFFF;font-size:28px;font-weight:700; }}
QLabel#creatorRole {{ color:#D0DEEF;font-size:13px; }}
QPushButton#creditLink {{ text-align:left;padding:14px;min-height:52px;border-radius:12px; }}
QTableWidget {{ selection-background-color:{soft};selection-color:{ink};alternate-background-color:{hover}; }}
QListView::item {{ border:0;background:transparent;margin:0;padding:0; }}
QListView::item:hover,QListView::item:selected {{ border:0;background:transparent; }}
QLabel#brand {{font-size:25px;}}
QLabel#heading {{font-size:24px;}}
QLabel#metricValue {{font-size:14px;font-weight:700;color:{ink};}}
QPushButton#metricChip {{min-height:24px;border-radius:8px;padding:0;background:{surface};border:1px solid {line};}}
QPushButton#metricChip[active="true"] {{background:{soft};border-color:{accent};}}
QLabel#dateNumber {{font-size:14px;font-weight:500;background:transparent;color:{ink};}}
QLabel#dateNumber[compactDate="true"] {{font-size:12px;}}
QLabel#dateNumber[dayState="outside"] {{color:{muted};font-weight:400;}}
QLabel#dateNumber[dayState="today"],QLabel#dateNumber[dayState="selected"],QLabel#dateNumber[dayState="saturday"] {{color:{accent};}}
QLabel#dateNumber[dayState="sunday"] {{color:#BE607C;}}
QLabel#dateNumber[dayState="holiday"],QLabel#holidayName {{color:#BE607C;}}
QLabel#dateNumber[isToday="true"] {{background:{accent};color:{onaccent};border-radius:8px;font-weight:600;}}
QLabel#holidayName {{font-size:11px;background:transparent;}}
QLabel#feastName {{font-size:11px;background:transparent;color:{feast_ink};}}
QWidget#diaryLock {{background:{surface};border:1px solid {line};border-radius:20px;}}
QLineEdit#diaryTitle {{font-size:24px;font-weight:600;padding:12px 10px;}}
QTextEdit#diaryBody {{font-size:16px;padding:18px;}}
QToolButton#formatButton {{padding:0;min-height:0;border-radius:8px;font-size:16px;}}
QToolButton#formatButton:checked {{background:{soft};border-color:{accent};color:{accent};}}
QToolButton#formatColor {{padding:5px 10px;min-height:22px;}}
QListWidget#diaryList::item {{padding:14px 10px;margin:3px 0;border-radius:10px;}}
QListWidget#diaryList::item:selected {{background:{soft};color:{ink};}}
QListWidget#diaryList::item:hover {{background:{hover};}}
QCheckBox {{spacing:8px;}}
QCheckBox::indicator {{width:16px;height:16px;border:1px solid {muted};border-radius:4px;background:{surface};}}
QCheckBox::indicator:checked {{background:{accent};border:4px solid {accent};}}
QPushButton#segment:checked {{background:{soft};color:{accent};border-color:{accent};}}
'''.format(**c)
    if glass_enabled():
        from .glass import panel_stylesheet
        base+=panel_stylesheet(c)
    return base

THEME=stylesheet(DEFAULT_THEME)

def apply_palette(app,key=None):
    key=key or app.property('bufsTheme') or DEFAULT_THEME
    if key not in THEMES:key=DEFAULT_THEME
    app.setProperty('bufsTheme',key);c=theme_tokens(key);p=QPalette()
    for role,value in {'Window':c['bg'],'WindowText':c['ink'],'Base':c['surface'],'AlternateBase':c['soft'],'Text':c['ink'],'Button':c['surface'],'ButtonText':c['ink'],'Highlight':c['soft'],'HighlightedText':c['ink'],'ToolTipBase':c['surface'],'ToolTipText':c['ink'],'PlaceholderText':c['muted']}.items():
        p.setColor(getattr(QPalette.ColorRole,role),QColor(value))
    for role in ('Text','ButtonText','WindowText'):p.setColor(QPalette.ColorGroup.Disabled,getattr(QPalette.ColorRole,role),QColor(c['muted']))
    app.setPalette(p)

_icons={}
def icon(name,tint=None):
    c=colors();semantic=category_colors()
    ink=tint or (semantic['assignment_ink'] if name=='assignment' else semantic['movie_ink'] if name=='video' else c['accent'])
    key=(ink,name)
    if key in _icons:return _icons[key]
    pix=QPixmap(40,40);pix.setDevicePixelRatio(2);pix.fill(Qt.GlobalColor.transparent)
    p=QPainter(pix);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(ink),1.5,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
    if name=='home':
        p.drawLine(2,9,10,2);p.drawLine(10,2,18,9);p.drawLine(4,8,4,18);p.drawLine(4,18,16,18);p.drawLine(16,18,16,8);p.drawRect(8,12,4,6)
    elif name=='calendar':
        p.drawRoundedRect(2,4,16,14,3,3);p.drawLine(2,9,18,9);p.drawLine(6,2,6,6);p.drawLine(14,2,14,6)
    elif name=='video':
        p.drawRoundedRect(2,3,16,14,3,3);p.drawLine(8,7,13,10);p.drawLine(13,10,8,13);p.drawLine(8,13,8,7)
    elif name=='timetable':
        p.drawRoundedRect(2,3,16,15,2,2);p.drawLine(2,8,18,8);p.drawLine(8,8,8,18);p.drawLine(13,8,13,18)
    elif name=='custom':
        p.drawRoundedRect(3,3,14,14,4,4);p.drawLine(7,10,9,12);p.drawLine(9,12,14,7)
    elif name=='up':
        p.drawLine(5,12,10,7);p.drawLine(10,7,15,12)
    elif name=='down':
        p.drawLine(5,7,10,12);p.drawLine(10,12,15,7)
    elif name=='diary':
        p.drawRoundedRect(5,3,15,18,2,2);p.drawLine(9,3,9,21);p.drawLine(12,8,17,8);p.drawLine(12,12,17,12)
    elif name=='close':
        p.drawLine(5,5,15,15);p.drawLine(15,5,5,15)
    elif name=='menu':
        p.drawLine(3,5,17,5);p.drawLine(3,10,17,10);p.drawLine(3,15,17,15)
    elif name=='info':
        p.drawEllipse(2,2,16,16);p.drawLine(10,9,10,14);p.drawPoint(10,6)
    elif name=='theme':
        p.drawEllipse(2,2,16,16);p.drawLine(10,2,10,18);p.drawArc(5,5,10,10,90*16,180*16)
    elif name=='settings':
        for y,x in ((5,6),(10,13),(15,8)):
            p.drawLine(2,y,18,y);p.drawEllipse(x-2,y-2,4,4)
    else:
        p.drawRoundedRect(4,2,12,16,2,2)
        for y in (7,11,15):p.drawLine(7,y,13,y)
    p.end()
    if len(_icons)>=128:_icons.pop(next(iter(_icons)))
    _icons[key]=QIcon(pix);return _icons[key]

