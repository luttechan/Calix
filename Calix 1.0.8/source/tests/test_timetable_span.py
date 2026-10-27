"""Minute-precise cards replace the old rounded table-cell spans."""
from learning_calendar.timetable_view import WeekSurface
from PySide6.QtWidgets import QApplication


def test_adjacent_short_classes_have_separate_nonoverlapping_geometry():
    app=QApplication.instance() or QApplication([]);surface=WeekSurface();surface.resize(900,900)
    rows=[dict(id=1,course_id=1,day=0,start_time='09:00',end_time='09:20',room='',professor='',color=''),
          dict(id=2,course_id=2,day=0,start_time='09:20',end_time='10:00',room='',professor='',color='')]
    surface.set_data(rows,{1:'수업 A',2:'수업 B'});surface.show();app.processEvents()
    first,second=surface.blocks[1],surface.blocks[2]
    assert first.geometry().bottom()<second.geometry().top()
    assert second.height()>first.height()
    assert first.title.full=='수업 A' and second.title.full=='수업 B'
    surface.close();surface.deleteLater();app.processEvents()


def test_geometry_uses_real_minute_duration():
    app=QApplication.instance() or QApplication([]);surface=WeekSurface();surface.resize(900,900)
    row=dict(id=1,course_id=1,day=2,start_time='09:15',end_time='10:45',room='',professor='',color='')
    surface.set_data([row],{1:'과목'});block=surface.blocks[1]
    assert abs(block.height()-(surface.hour_height*1.5-2))<=1
    surface.close();surface.deleteLater();app.processEvents()
