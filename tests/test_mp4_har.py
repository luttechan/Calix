"""Anonymized module shapes from the supplied October 29 HAR."""
from pathlib import Path
import json
from datetime import date,datetime
from PySide6.QtWidgets import QApplication
from learning_calendar.models import Course,KST
from learning_calendar.parsers import parse_movies
from learning_calendar.storage import Store
from learning_calendar.snapshot import Snapshot
from learning_calendar.event_view import EventListModel
from learning_calendar.calendar_view import MonthCanvas

def fixture():return json.loads((Path(__file__).parent/'fixtures/learningx_content_types.json').read_text())

def test_har_all_weekly_videos_are_collected_with_completion_dates_and_links(tmp_path):
    data=fixture();events=parse_movies(Course(1,'Video course'),data['video_course'])
    assert len(events)==17 and len({e.key for e in events})==17
    assert all(e.kind=='movie' and e.completion_verified and e.url for e in events)
    assert sum(e.completed for e in events)==11
    assert {e.week for e in events}=={f'Week {i}' for i in (*range(1,8),*range(9,15))}
    mp4_keys={f'movie:1:{i["content_data"]["item_id"]}' for m in data['video_course'] for i in m['module_items'] if i['content_data'].get('item_content_data',{}).get('content_type')=='mp4'}
    mp4=[e for e in events if e.key in mp4_keys]
    assert len(mp4)==4 and all(e.completed for e in mp4)
    assert sorted(e.due.date().isoformat() for e in mp4)==['2026-09-23']*2+['2026-09-30']*2
    assert parse_movies(Course(2,'Document course'),data['document_course'])==[]
    store=Store(tmp_path/'db.sqlite3');store.apply_batch([Course(1,'Video course')],{(1,'movie'):mp4})
    store.set_note(mp4[0].key,'Keep note');stats=store.apply_batch([Course(1,'Video course')],{(1,'movie'):events})
    assert stats['new']==13 and stats['archived']==0
    snapshot=Snapshot(store.events(),store.courses());assert len(snapshot.by_kind['movie'])==17 and snapshot.by_key[mp4[0].key].note=='Keep note'
    model=EventListModel();model.set_events(snapshot.filtered(type_key='movie'));assert model.rowCount()==17
    assert len(snapshot.filtered(query='Week 9',type_key='movie'))==1
    assert len(snapshot.pending(datetime(2026,10,29,12,42,tzinfo=KST)))==5
    store.close()

def test_har_mp4_videos_reach_completed_calendar_badges():
    app=QApplication.instance() or QApplication([])
    events=parse_movies(Course(1,'Video course'),fixture()['video_course'])
    widget=MonthCanvas();widget.resize(1200,750);widget.set_month(date(2026,9,1),date(2026,9,23),Snapshot.days(events));widget.show();app.processEvents();widget._layout_badges()
    for day in (23,30):
        badge=next(b for b in widget.badges if b.day==date(2026,9,day))
        assert len(badge.events)==3 and not badge.movie_done.isHidden() and badge.movie.isHidden()
        assert badge.movie_done.property('calendarOpacity')==.38
    widget.close();widget.deleteLater();app.processEvents()

def test_har_week_nine_is_visible_as_uncompleted_calendar_video():
    app=QApplication.instance() or QApplication([])
    events=parse_movies(Course(1,'Video course'),fixture()['video_course'])
    widget=MonthCanvas();widget.resize(1200,750);widget.set_month(date(2026,10,1),date(2026,10,28),Snapshot.days(events));widget.show();app.processEvents();widget._layout_badges()
    badge=next(b for b in widget.badges if b.day==date(2026,10,28))
    assert len(badge.events)==1 and badge.events[0].week=='Week 9' and not badge.events[0].completed
    assert not badge.movie.isHidden() and badge.movie_done.isHidden() and badge.movie.property('calendarOpacity')==1
    widget.close();widget.deleteLater();app.processEvents()
