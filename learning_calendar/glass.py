"""Frosted in-window materials. Text stays in ordinary native Qt controls."""
from PySide6.QtCore import Qt,QRectF,QTimer
from PySide6.QtGui import QColor,QImage,QPainter,QRadialGradient,QLinearGradient
from PySide6.QtWidgets import QWidget


def rgba(value,alpha):
    c=QColor(value);return f'rgba({c.red()},{c.green()},{c.blue()},{alpha})'


class GlassBackdrop(QWidget):
    """One small cached color field, independent of display DPI and window size."""
    def __init__(self,parent=None):
        super().__init__(parent);self._field=None;self._signature=None;self.render_count=0
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent,True);self.setAutoFillBackground(False)
        self.move_repaint=QTimer(self);self.move_repaint.setSingleShot(True);self.move_repaint.setInterval(50);self.move_repaint.timeout.connect(self.update)
    def repair_after_move(self):self.move_repaint.start()
    def invalidate(self):self._signature=None;self.update()
    def paintEvent(self,event):
        from .design import colors,glass_enabled
        c=colors();enabled=glass_enabled();signature=(c['bg'],enabled)
        if signature!=self._signature:
            self._signature=signature;self._field=None
            if enabled:
                image=QImage(640,420,QImage.Format.Format_ARGB32_Premultiplied);image.fill(QColor(c['bg']));p=QPainter(image)
                dark=QColor(c['bg']).lightness()<128
                blooms=[(.05,.05,.85,c['accent'],115 if dark else 95),(.93,.18,.64,'#9265BA' if dark else '#E9A7C7',90 if dark else 80),(.72,1.,.68,'#387D88' if dark else '#8FD9C8',80)]
                for x,y,r,color,alpha in blooms:
                    gradient=QRadialGradient(x*640,y*420,r*640);tint=QColor(color);tint.setAlpha(alpha);gradient.setColorAt(0,tint);tint.setAlpha(0);gradient.setColorAt(1,tint);p.fillRect(image.rect(),gradient)
                p.end();self._field=image;self.render_count+=1
        p=QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        if self._field is not None:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform);p.drawImage(self.rect(),self._field)
        else:p.fillRect(self.rect(),QColor(c['bg']))
        p.end()


def panel_stylesheet(c):
    dark=QColor(c['bg']).lightness()<128
    edge='rgba(255,255,255,47)' if dark else 'rgba(255,255,255,222)'
    soft_edge='rgba(255,255,255,29)' if dark else 'rgba(158,176,209,100)'
    panel=rgba(c['surface'],175 if dark else 180);dense=rgba(c['surface'],225 if dark else 224)
    sheen=rgba('#FFFFFF',18 if dark else 145);clear=rgba(c['surface'],110 if dark else 102)
    hover=rgba(c['soft'],218);accent=rgba(c['accent'],100 if dark else 65)
    return f'''
QWidget#root,QWidget#page,QWidget#homeBody {{background:transparent;}}
QFrame#sidebar {{background:{panel};border:1px solid {edge};border-radius:24px;margin:12px 0 12px 12px;}}
QPushButton,QToolButton {{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {dense},stop:1 {panel});border:1px solid {edge};border-radius:14px;}}
QPushButton:hover,QToolButton:hover {{background:{hover};border-color:{accent};}}
QPushButton#primary {{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {c['accent']},stop:1 {c['accent']});color:{c['onaccent']};border-color:{rgba('#FFFFFF',75)};}}
QPushButton#quiet,QPushButton#ghost {{background:{clear};border-color:{soft_edge};}}
QPushButton#nav {{background:transparent;border:1px solid transparent;border-radius:16px;}}
QPushButton#nav:checked {{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {hover},stop:1 {panel});border:1px solid {edge};}}
QPushButton#metricCard,QPushButton#homeSummary,QFrame#orbCard,QFrame#panel,QFrame#boardCard,QFrame#inspector,QWidget#diaryLock {{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {dense},stop:.22 {panel},stop:1 {clear});border:1px solid {edge};border-radius:22px;}}
QPushButton#metricCard:hover,QPushButton#homeSummary:hover {{background:{hover};border-color:{accent};}}
QFrame#welcomeHero {{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {rgba(c['hero'],210)},stop:.5 {panel},stop:1 {clear});border:1px solid {edge};border-radius:28px;}}
QLineEdit,QComboBox,QTimeEdit,QSpinBox,QPlainTextEdit,QTextEdit {{background:{dense};border:1px solid {soft_edge};border-radius:12px;}}
QLineEdit:focus,QComboBox:focus,QTimeEdit:focus,QSpinBox:focus,QPlainTextEdit:focus,QTextEdit:focus {{border:2px solid {c['accent']};}}
QListView,QTableWidget,QTableView#scheduleTable,QTableView#eventChoices {{background:{c['surface']};border:1px solid {edge};border-radius:18px;}}
QHeaderView::section {{background:{clear};color:{c['muted']};border:0;}}
QCalendarWidget {{background:{c['surface']};border:1px solid {edge};border-radius:20px;}}
QCalendarWidget QTableView {{background:{c['surface']};border:0;}}
QWidget#weekSurface {{background:{panel};}}
QMenu,QComboBox QAbstractItemView {{background:{c['surface']};border:1px solid {edge};border-radius:13px;}}
QToolButton#commandMenu {{background:{panel};border:1px solid {edge};border-radius:14px;}}
QToolButton#timeStep {{background:transparent;border:0;border-radius:5px;}}
QToolButton#timeStep:hover {{background:{hover};}}
QPushButton#dayChoice:checked,QPushButton#segment:checked,QToolButton#formatButton:checked {{background:{hover};border-color:{accent};}}
QDialog {{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {c['bg']},stop:1 {c['soft']});}}
QFrame#schedulePreview {{background:{c['surface']};border:1px solid {edge};border-radius:18px;}}
QPushButton#schedulePreviewRow {{background:transparent;border:0;border-bottom:1px solid {c['line']};border-radius:0;}}
QPushButton#schedulePreviewRow:hover {{background:{hover};}}
'''
