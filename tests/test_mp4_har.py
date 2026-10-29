"""Anonymized module shapes from the supplied October 29 HAR."""
from pathlib import Path
import json
from datetime import date
from PySide6.QtWidgets import QApplication
from learning_calendar.models import Course
from learning_calendar.parsers import parse_movies
from learning_calendar.storage import Store
from learning_calendar.snapshot import Snapshot
from learning_calendar.event_view import EventListModel
from learning_calendar.calendar_view import MonthCanvas

def fixture():return json.loads((Path(__file__).parent/'fixtures/learningx_content_types.json').read_text())

def test_har_mp4_videos_are_collected_with_completion_dates_and_links(tmp_path):
    data=fixture();events=parse_movies(Course(1,'Video course'),data['video_course'])
    assert len(events)==4 and len({e.key for e in events})==4
    assert all(e.kind=='movie' and e.completed and e.completion_verified and e.url for e in events)
    assert sorted(e.due.date().isoformat() for e in events)==['2026-09-23']*2+['2026-09-30']*2
    assert parse_movies(Course(2,'Document course'),data['document_course'])==[]
    store=Store(tmp_path/'db.sqlite3');store.apply_batch([Course(1,'Video course')],{(1,'movie'):events})
    store.set_note(events[0].key,'Keep note');store.apply_batch([Course(1,'Video course')],{(1,'movie'):events})
    snapshot=Snapshot(store.events(),store.courses());assert len(snapshot.by_kind['movie'])==4 and snapshot.by_key[events[0].key].note=='Keep note'
    model=EventListModel();model.set_events(snapshot.filtered(type_key='movie'));assert model.rowCount()==4
    store.close()

def test_har_mp4_videos_reach_completed_calendar_badges():
    app=QApplication.instance() or QApplication([])
    events=parse_movies(Course(1,'Video course'),fixture()['video_course'])
    widget=MonthCanvas();widget.resize(1200,750);widget.set_month(date(2026,9,1),date(2026,9,23),Snapshot.days(events));widget.show();app.processEvents();widget._layout_badges()
    for day in (23,30):
        badge=next(b for b in widget.badges if b.day==date(2026,9,day))
        assert len(badge.events)==2 and not badge.movie_done.isHidden() and badge.movie.isHidden()
        assert badge.movie_done.property('calendarOpacity')==.38
    widget.close();widget.deleteLater();app.processEvents()
