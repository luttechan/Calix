from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QRawFont,QTextLayout,QTextCursor
from learning_calendar.fonts import apply_korean_font,font_path
from learning_calendar.diary_editor import DiaryEditor

def test_pretendard_renders_hangul_latin_and_numbers_without_font_fallback():
    app=QApplication.instance() or QApplication([]);family=apply_korean_font(app);assert family=='Calix Sans'
    assert font_path().is_file() and font_path().with_name('Pretendard-OFL.txt').is_file()
    for weight in (QFont.Weight.Normal,QFont.Weight.Medium,QFont.Weight.DemiBold,QFont.Weight.Bold):
        font=QFont(family,12,weight);raw=QRawFont.fromFont(font)
        assert all(raw.supportsCharacter(ord(char)) for char in '가나다한글ABC0123456789')
        layout=QTextLayout('한글 ABC 0123',font);layout.beginLayout();line=layout.createLine();line.setLineWidth(1000);layout.endLayout()
        assert layout.glyphRuns() and all(run.rawFont().familyName()==family for run in layout.glyphRuns())

def test_old_diary_font_adapts_without_changing_text_or_emphasis():
    app=QApplication.instance() or QApplication([]);apply_korean_font(app);editor=DiaryEditor()
    editor.setHtml('''<html><body style="font-family:'Malgun Gothic';"><p style="font-weight:700;color:#cf779a;">이전 일기</p><p>font-family:'Malgun Gothic'</p></body></html>''')
    assert editor.toPlainText()=="이전 일기\nfont-family:'Malgun Gothic'"
    cursor=editor.textCursor();cursor.setPosition(1);editor.setTextCursor(cursor)
    assert editor.currentCharFormat().fontWeight()==QFont.Weight.Bold
    assert editor.currentCharFormat().foreground().color().name()=='#cf779a'
    assert QApplication.font().family() in editor.toHtml();editor.deleteLater();app.processEvents()

def test_saved_variable_font_diary_uses_current_face_without_changing_literal_text():
    app=QApplication.instance() or QApplication([]);family=apply_korean_font(app);editor=DiaryEditor()
    editor.setHtml("<p style=\"font-family:'Pretendard Variable';font-weight:700\">이전 글</p><p>Pretendard Variable</p>")
    assert editor.toPlainText()=='이전 글\nPretendard Variable' and family in editor.toHtml()
    cursor=editor.textCursor();cursor.setPosition(1);editor.setTextCursor(cursor);assert editor.currentCharFormat().fontWeight()==QFont.Weight.Bold
    editor.deleteLater();app.processEvents()
