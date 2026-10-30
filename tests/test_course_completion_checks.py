from types import SimpleNamespace
import pytest
from PySide6.QtWidgets import QApplication
from learning_calendar.models import Course
from learning_calendar.parsers import movie_completion

@pytest.mark.parametrize('item,done',[
    ({'completed':True},True),({'completed':False},False),({'completed':'false'},False),
    ({'completed':'true'},True),({'completed':False,'attendance_status':'attendance'},True),
    ({'attendance_status':'late'},True),({'attendance_status':'excused'},True),
    ({'attendance_status':'none'},False),({'attendance_status':'absent'},False)])
def test_school_video_completion_fields(item,done):assert movie_completion(item) is done

def test_missing_video_completion_is_not_guessed():
    assert movie_completion({}) is None



