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
                blooms=[(.12,0.,.85,c['accent'],35 if dark else 22),(.95,1.,.7,c['hero'],28 if dark else 35)]
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
    edge=rgba(c['line'],190);soft_edge=rgba(c['line'],210)
    panel=rgba(c['surface'],238);dense=rgba(c['surface'],250)
    clear=rgba(c['surface'],180)
    hover=rgba(c['soft'],235);accent=rgba(c['accent'],150)
    return f'''
QWidget#root,QWidget#page,QWidget#homeBody {{background:transparent;}}
QFrame#sidebar {{background:{clear};border:0;border-right:1px solid {edge};border-radius:0;}}
QPushButton,QToolButton {{background:{dense};border:1px solid {soft_edge};border-radius:8px;}}
QPushButton:hover,QToolButton:hover {{background:{hover};border-color:{accent};}}
QPushButton#primary {{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {c['accent']},stop:1 {c['accent']});color:{c['onaccent']};border-color:{rgba('#FFFFFF',75)};}}
QPushButton#quiet,QPushButton#ghost {{background:transparent;border-color:transparent;}}
QPushButton#quiet:hover,QPushButton#ghost:hover {{background:{hover};border-color:transparent;}}
QPushButton#nav {{background:transparent;border:1px solid transparent;border-radius:8px;}}
QPushButton#nav:checked {{background:{hover};border-color:transparent;color:{c['accent']};}}
QPushButton#metricCard,QPushButton#homeSummary,QFrame#orbCard,QFrame#panel,QFrame#boardCard,QFrame#inspector,QWidget#diaryLock {{background:{panel};border:1px solid {edge};border-radius:14px;}}
QPushButton#metricCard:hover,QPushButton#homeSummary:hover {{background:{hover};border-color:{accent};}}
QFrame#welcomeHero {{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {rgba(c['hero2'],235)},stop:1 {panel});border:1px solid {edge};border-radius:16px;}}
QLineEdit,QComboBox,QTimeEdit,QSpinBox,QPlainTextEdit,QTextEdit {{background:{dense};border:1px solid {soft_edge};border-radius:8px;}}
QLineEdit:focus,QComboBox:focus,QTimeEdit:focus,QSpinBox:focus,QPlainTextEdit:focus,QTextEdit:focus {{border:1px solid {c['accent']};}}
QListView,QTableWidget,QTableView#scheduleTable,QTableView#eventChoices {{background:{c['surface']};border:1px solid {edge};border-radius:12px;}}
QHeaderView::section {{background:{c['surface']};color:{c['muted']};border:0;border-bottom:1px solid {edge};}}
QCalendarWidget {{background:{c['surface']};border:0;border-radius:10px;}}
QCalendarWidget QTableView {{background:{c['surface']};border:0;}}
QWidget#weekSurface {{background:{panel};}}
QMenu,QComboBox QAbstractItemView {{background:{c['surface']};border:1px solid {edge};border-radius:8px;}}
QToolButton#commandMenu {{background:transparent;border:1px solid transparent;border-radius:8px;}}
QToolButton#timeStep {{background:transparent;border:0;border-radius:5px;}}
QToolButton#timeStep:hover {{background:{hover};}}
QPushButton#dayChoice:checked,QPushButton#segment:checked,QToolButton#formatButton:checked {{background:{hover};border-color:{accent};}}
QDialog {{background:{c['surface']};}}
QFrame#schedulePreview {{background:{c['surface']};border:1px solid {edge};border-radius:12px;}}
QPushButton#schedulePreviewRow {{background:transparent;border:0;border-bottom:1px solid {c['line']};border-radius:0;}}
QPushButton#schedulePreviewRow:hover {{background:{hover};}}
'''
