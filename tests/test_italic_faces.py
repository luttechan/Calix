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


def test_directwrite_selects_actual_upright_and_italic_glyphs():
    import json,os,subprocess,sys
    from pathlib import Path
    import pytest
    if sys.platform!='win32':pytest.skip('Windows DirectWrite check')
    code=r'''
import sys,json,os
sys.path[:0]=json.loads(os.environ['CALIX_FONT_TEST_PATHS'])
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QRawFont
from learning_calendar.fonts import apply_korean_font,font_path
app=QApplication([]);family=apply_korean_font(app)
for weight,italic,name in [(400,False,'Regular'),(700,False,'Bold'),(400,True,'Italic'),(700,True,'BoldItalic')]:
    font=QFont(family);font.setPixelSize(18);font.setWeight(QFont.Weight(weight));font.setItalic(italic)
    actual=QRawFont.fromFont(font);expected=QRawFont(str(font_path().with_name('CalixSans-'+name+'.ttf')),18)
    assert actual.fontTable('glyf')==expected.fontTable('glyf'),(name,actual.styleName())
    assert actual.supportsCharacter(ord('한'))
'''
    env=os.environ.copy();env['QT_QPA_PLATFORM']='windows:fontengine=directwrite';env['CALIX_FONT_TEST_PATHS']=json.dumps(sys.path)
    result=subprocess.run([sys.executable,'-B','-c',code],env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
