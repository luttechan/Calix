"""Register the provided Pretendard once, with a bundled fallback."""
from pathlib import Path
import sys

def font_path():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    preferred=root/'asset'/'style'/'PretendardVariable.ttf'
    static=preferred.with_name('CalixSans-Regular.ttf')
    return preferred if preferred.is_file() else static if static.is_file() else preferred.with_name('malgun.ttf')

def choose_font_family(families):
    installed = {f.casefold(): f for f in families}
    return installed.get('calix sans') or installed.get('pretendard variable') or installed.get('pretendard') or installed.get('malgun gothic') or installed.get('맑은 고딕')

def apply_korean_font(app):
    from PySide6.QtGui import QFont, QFontDatabase
    if app.property('bufsFontFamily'):
        return app.property('bufsFontFamily')
    path = font_path()
    static=[path.with_name(f'CalixSans-{style}.ttf') for style in ('Regular','Medium','SemiBold','Bold')]
    candidates=static if all(face.is_file() for face in static) else [path]
    if candidates==static:
        candidates += [face for style in ('Italic','BoldItalic') if (face:=path.with_name(f'CalixSans-{style}.ttf')).is_file()]
    ids=[QFontDatabase.addApplicationFont(str(face)) for face in candidates if face.is_file()]
    font_id=next((value for value in ids if value>=0),-1)
    families=[family for value in ids if value>=0 for family in QFontDatabase.applicationFontFamilies(value)]
    if not families and path.name!='malgun.ttf':
        fallback=path.with_name('malgun.ttf');font_id=QFontDatabase.addApplicationFont(str(fallback)) if fallback.is_file() else -1
        families=QFontDatabase.applicationFontFamilies(font_id) if font_id>=0 else []
    family = choose_font_family(families) or (families[0] if families else 'Malgun Gothic')
    font = QFont(family)
    font.setPointSizeF(10.0)
    font.setWeight(QFont.Weight.Normal)
    font.setStyleStrategy(QFont.StyleStrategy.PreferDefault)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)
    app.setProperty('bufsFontFamily', family)
    app.setProperty('bufsBundledFontFamily', family)
    app.setProperty('bufsFontId', font_id)
    return family


def set_text_style(app,mode='pretendard'):
    from PySide6.QtGui import QFont
    bundled=app.property('bufsBundledFontFamily') or apply_korean_font(app)
    family='Malgun Gothic' if mode=='windows' else bundled
    font=QFont(family);font.setPointSizeF(10);font.setStyleStrategy(QFont.StyleStrategy.PreferDefault);font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font);app.setProperty('bufsFontFamily',family)
    return family
