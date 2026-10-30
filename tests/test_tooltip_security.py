from PySide6.QtGui import QTextDocument,QImage,QPainter
from PySide6.QtWidgets import QApplication
from learning_calendar.text_safety import tooltip_text


def test_untrusted_tooltip_markup_is_literal_and_never_loads_resources():
    app=QApplication.instance() or QApplication([]);requested=[]
    class Document(QTextDocument):
        def loadResource(self,kind,url):requested.append(url.toString());return None
    value='<img src="file:///C:/private/photo.png"> & <b>과제</b>\n두 번째 줄'
    document=Document();document.setHtml(tooltip_text(value))
    target=QImage(800,160,QImage.Format.Format_ARGB32_Premultiplied);painter=QPainter(target);document.drawContents(painter);painter.end()
    assert document.toPlainText()==value and requested==[]


def test_plain_tooltips_keep_existing_strings():
    assert tooltip_text('영상 2건\n과제 1건')=='영상 2건\n과제 1건'
