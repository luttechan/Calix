from PySide6.QtCore import Qt
from PySide6.QtGui import QFont,QFontInfo,QRawFont,QFontMetrics
from PySide6.QtWidgets import QApplication
from learning_calendar.fonts import apply_korean_font


def test_italic_and_bold_italic_keep_bundled_korean_family():
    app=QApplication.instance() or QApplication([]);family=apply_korean_font(app)
    for weight in (QFont.Weight.Normal,QFont.Weight.Bold):
        font=QFont(family);font.setPixelSize(16);font.setItalic(True);font.setWeight(weight)
        info=QFontInfo(font);raw=QRawFont.fromFont(font)
        assert info.family()==family and info.italic()
        assert raw.supportsCharacter(ord('한')) and QFontMetrics(font).horizontalAdvance('한글 기울임 I')>0
