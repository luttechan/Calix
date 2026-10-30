"""Bounded, single-use prepared dialogs. Drafts never return to the cache."""
import logging
from PySide6.QtCore import QObject,QTimer,Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget,QApplication

NAMES=('settings','theme','credits','aliases','types','manual','session','holiday','special')


class ReadyDialogs(QObject):
    def __init__(self,factory,parent,limit=2):
        super().__init__(parent);self.factory=factory;self.cache={};self.generation=0;self.closed=False;self.pending=set();self.warmed=set();self.limit=max(0,int(limit))

    def prepare(self,name):
        if self.closed or name in self.cache or not self.limit:return
        while len(self.cache)>=self.limit:self.cache.pop(next(iter(self.cache))).deleteLater()
        dialog=self.factory(name)
        dialog.ensurePolished()
        if dialog.layout():dialog.layout().activate()
        for child in dialog.findChildren(QWidget):
            child.ensurePolished()
            if child.layout():child.layout().activate()
        dialog.winId()
        style=(name,getattr(self.parent(),'theme_key',''),self.parent().settings.get('glass',True))
        if style not in self.warmed:
            surface=QImage(dialog.size(),QImage.Format.Format_ARGB32_Premultiplied);surface.fill(Qt.GlobalColor.transparent)
            dialog.render(surface);self.warmed.add(style)
        self.cache[name]=dialog

    def prime(self):
        for name in NAMES[:self.limit]:self.prepare(name)

    def take(self,name):
        dialog=self.cache.pop(name,None)
        if dialog is None:dialog=self.factory(name)
        dialog.finished.connect(lambda _=0,key=name:self.refill(key))
        return dialog

    def refill(self,name):
        if self.closed or name in self.pending:return
        self.pending.add(name);generation=self.generation
        QTimer.singleShot(250,self,lambda:self._refill(generation,[name]))

    def _refill(self,generation,names):
        if self.closed or generation!=self.generation:return
        if not self.parent().isVisible() or self.parent().isMinimized():
            for name in names:self.pending.discard(name)
            return
        if QApplication.activeModalWidget() or getattr(self.parent(),'_busy',False) or getattr(self.parent(),'_closing',False):
            QTimer.singleShot(250,self,lambda:self._refill(generation,names));return
        name,*remaining=names;self.pending.discard(name)
        try:self.prepare(name)
        except Exception:logging.warning('메뉴 준비 실패: %s',name)
        if remaining:QTimer.singleShot(16,self,lambda:self._refill(generation,remaining))

    def invalidate(self):
        self.generation+=1;self.pending.clear()
        for dialog in self.cache.values():dialog.deleteLater()
        self.cache.clear()
        # Do not rebuild every dialog after a theme/snapshot change. The next
        # requested dialog is created with fresh data and then cached on close.

    def shutdown(self):
        self.closed=True;self.invalidate()
