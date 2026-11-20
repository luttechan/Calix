import pytest
from learning_calendar.preferences import read_settings,write_settings
@pytest.mark.parametrize('theme',['peach','amber','olive','lavender'])
def test_new_theme_survives_settings_reload(tmp_path,theme):
    path=tmp_path/'settings.json'
    write_settings(path,{'theme':theme})
    assert read_settings(path)['theme']==theme
