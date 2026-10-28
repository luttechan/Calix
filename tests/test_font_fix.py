from learning_calendar.fonts import choose_font_family, font_path

def test_pretendard_is_preferred():
    assert choose_font_family(['Noto Sans KR','Malgun Gothic','Pretendard','Pretendard Variable'])=='Pretendard Variable'

def test_case_insensitive_pretendard_and_fallback():
    assert choose_font_family(['pretendard','malgun gothic'])=='pretendard'
    assert choose_font_family(['Malgun Gothic'])=='Malgun Gothic'

def test_missing_font_is_not_invented():
    assert choose_font_family(['Segoe UI']) is None
    assert font_path().name=='PretendardVariable.ttf'
