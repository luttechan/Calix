"""Shape-only completion indicators; labels keep native Qt text rendering."""
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QColor,QPen

def paint_check(painter,rect,checked,theme):
    painter.save();painter.setRenderHint(painter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(theme['accent'] if checked else theme['muted']),1.2));painter.setBrush(QColor(theme['accent'] if checked else theme['surface']));painter.drawRoundedRect(rect,4,4)
    if checked:
        pen=QPen(QColor(theme['onaccent']),1.8);pen.setCapStyle(Qt.PenCapStyle.RoundCap);pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin);painter.setPen(pen)
        painter.drawLine(QPointF(rect.left()+rect.width()*.23,rect.top()+rect.height()*.52),QPointF(rect.left()+rect.width()*.43,rect.top()+rect.height()*.72))
        painter.drawLine(QPointF(rect.left()+rect.width()*.43,rect.top()+rect.height()*.72),QPointF(rect.left()+rect.width()*.79,rect.top()+rect.height()*.29))
    painter.restore()
