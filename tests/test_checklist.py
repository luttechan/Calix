import copy
from dataclasses import replace
import pytest
from PySide6.QtCore import Qt,QCoreApplication,QEvent,QPoint
from PySide6.QtWidgets import QApplication,QAbstractItemView
from learning_calendar.models import Course,Event
from learning_calendar.storage import Store
from learning_calendar.checklist_store import ChecklistStore,backup_state,validate_state
from learning_calendar.checklist_view import ChecklistView,ROW_ROLE
from learning_calendar.local_backup import write_backup,read_backup,restore_backup


@pytest.fixture
def store(tmp_path):
    s=Store(tmp_path/'learning.db');yield s;s.close()


def school(store):
    courses=[Course(1,'기업가정신'),Course(2,'삶과 철학')]
    events=[Event('assignment:1:10',1,courses[0].name,'assignment','글쓰기','2026-11-02T23:59:00+09:00',False),Event('movie:2:20',2,courses[1].name,'movie','1주차 영상','2026-11-01T23:59:00+09:00',True)]
    store.apply_batch(courses,{(1,'assignment'):[events[0]],(2,'movie'):[events[1]]})
    return courses,events


def test_section_limits_and_preserving_deleted_section_tasks(store):
    repo=ChecklistStore(store)
    for name in ['개인','팀플','자격증','취업']:repo.save_section(name)
    with pytest.raises(ValueError):repo.save_section('초과')
    with pytest.raises(ValueError):repo.save_section('개인')
    section=repo.sections()[1]['id'];key=repo.add(section,'기억할 일');repo.save_section('개인 일정',section)
    assert repo.rows(section)[0]['title']=='기억할 일'
    repo.delete_section(section);trash=repo.rows(1,trash=True)
    assert trash[0]['id']==key and trash[0]['title']=='기억할 일'
    with pytest.raises(ValueError):repo.delete_section(1)


def test_school_imports_are_opt_in_and_local_progress_never_changes_school(store):
    courses,events=school(store);repo=ChecklistStore(store)
    assert not repo.rows(1,events)
    repo.set_included(['assignment']);assert len(repo.rows(1,events))==1
    row=repo.rows(1,events)[0];repo.save(row,'role','자료 조사');repo.save(row,'note','목차 준비');repo.toggle(row,True)
    assert not next(e for e in store.events() if e.kind=='assignment').completed
    assert repo.rows(1,events)[0]['status_kind']=='done'
    repo.set_included(['assignment','movie']);rows=repo.rows(1,events)
    assert len(rows)==2 and all(r['status_kind']=='done' for r in rows)
    store.apply_batch(courses,{(1,'assignment'):[replace(events[0],title='학교 이름 변경')]})
    rows=repo.rows(1,store.events());item=next(r for r in rows if r['source_kind']=='assignment')
    assert item['title']=='학교 이름 변경' and item['role']=='자료 조사' and item['note']=='목차 준비' and item['status_kind']=='done'
    repo.save(item,'title','내 작업 이름');repo.save(item,'due_at','');repo.set_included([]);repo.set_included(['assignment'])
    assert repo.rows(1,store.events())[0]['title']=='내 작업 이름' and repo.rows(1,store.events())[0]['due_at']==''


def test_custom_status_color_completion_and_toggle_restore(store):
    repo=ChecklistStore(store);key=repo.add(1,'Task');row=repo.rows(1)[0]
    status=repo.save_status('자료 수집','#7582E6');repo.save(row,'status_id',status);row=repo.rows(1)[0]
    repo.toggle(row,True);repo.toggle(repo.rows(1)[0],False)
    assert repo.rows(1)[0]['status_id']==status
    repo.save_status('자료 조사','#459CD4','open',status);assert repo.rows(1)[0]['status_name']=='자료 조사'
    repo.delete_status(status);assert repo.rows(1)[0]['status_id']==1
    with pytest.raises(ValueError):repo.save_status('계획','#7582E6','done',1)
    with pytest.raises(ValueError):repo.delete_status(4)


def test_professor_and_category_from_existing_data_without_network(store):
    courses,events=school(store);repo=ChecklistStore(store);repo.set_included(['assignment'])
    rows=repo.rows(1,events,[dict(course_id=1,professor='김교수')])
    assert rows[0]['category']=='기업가정신' and rows[0]['professor']=='김교수'
    repo.save(rows[0],'professor','박교수');assert repo.rows(1,events,[])[0]['professor']=='박교수'


def test_trash_is_reversible_even_after_source_checkbox_is_disabled(store):
    _,events=school(store);repo=ChecklistStore(store);repo.set_included(['assignment']);rows=repo.rows(1,events)
    repo.trash(rows);assert not repo.rows(1,events)
    repo.set_included([]);trash=repo.rows(1,events,trash=True);assert len(trash)==1
    repo.trash(trash,False);repo.set_included(['assignment']);assert len(repo.rows(1,events))==1


def test_backup_restores_checklist_sections_states_source_overrides_and_off_days(store,tmp_path):
    _,events=school(store);repo=ChecklistStore(store);repo.set_included(['assignment']);repo.save(repo.rows(1,events)[0],'role','조장')
    section=repo.save_section('개인');repo.add(section,'취업 준비');repo.save_status('지원 완료','#217A5B','done');store.set_meta('timetable_off_days','[2,4]')
    before=backup_state(store);archive=tmp_path/'backup.calix';write_backup(archive,store,tmp_path)
    value=read_backup(archive);assert value['version']==4
    repo.save_section('바뀐 이름',section);repo.set_included([]);restore_backup(value,store,tmp_path)
    assert backup_state(store)==before
    for change in [dict(off_days=[True]),dict(sources=['javascript']),dict(sections=[]),dict(tasks=[{**before['tasks'][0],'section_id':999}])]:
        with pytest.raises((ValueError,KeyError)):validate_state({**copy.deepcopy(before),**change})


@pytest.fixture
def app():return QApplication.instance() or QApplication([])


def close(widget,app):widget.close();widget.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()


def test_native_table_sort_edit_filter_and_restart(store,app):
    courses,events=school(store);view=ChecklistView(store);view.set_data(store,events,courses,[]);view.show();app.processEvents()
    assert view.proxy.rowCount()==0
    view.import_assignment.setChecked(True);view.import_movie.setChecked(True);assert view.proxy.rowCount()==2
    for col in range(7):
        for order in [Qt.SortOrder.AscendingOrder,Qt.SortOrder.DescendingOrder]:view.table.sortByColumn(col,order);assert view.proxy.rowCount()==2
    index=view.proxy.index(0,3);key=index.data(ROW_ROLE)['id'];assert view.proxy.setData(index,'진행 담당')
    view.pending.setChecked(True);assert view.proxy.rowCount()==1
    view.search.setText('없는 과목');view.filter_changed();assert view.proxy.rowCount()==0
    view.search.clear();view.pending.setChecked(False);view.filter_changed();view.set_data(store,events,courses,[],True)
    assert not view.proxy.setData(view.proxy.index(0,0),'차단')
    close(view,app);repo=ChecklistStore(store);assert next(r for r in repo.rows(1,events) if r['id']==key)['role']=='진행 담당'


@pytest.mark.parametrize('width,height,days',[(800,500,5),(1200,900,7),(920,700,5),(800,1200,7)])
def test_timetable_header_alignment_and_day_off_restore(app,width,height,days):
    from learning_calendar.timetable_view import TimetableView
    view=TimetableView();view.resize(width,height)
    rows=[dict(id=1,course_id=1,day=0,start_time='09:00',end_time='11:00',professor='',room='',color=''),dict(id=2,course_id=1,day=1,start_time='14:00',end_time='15:00',professor='',room='',color='')]
    view.set_data(rows,{1:'수업'},off_days={0});view.set_days(days);view.show()
    for _ in range(4):app.processEvents()
    view.align_headers();surface=view.surface;offset=surface.mapTo(view.headers,QPoint(0,0)).x();column=(surface.width()-surface.AXIS)/days
    for day in range(days):assert view.day_labels[day].x()==round(offset+surface.AXIS+day*column)
    assert surface.blocks[1].isHidden() and not surface.off_labels[0].isHidden() and not surface.blocks[2].isHidden()
    view.set_data(rows,{1:'수업'},off_days=set());app.processEvents();assert not surface.blocks[1].isHidden()
    close(view,app)


def test_main_checklist_navigation_font_settings_and_read_only(app,tmp_path):
    from learning_calendar.gui import MainWindow
    from learning_calendar.preferences import read_settings
    window=MainWindow(tmp_path);window.show_checklist();assert window.main_stack.currentIndex()==3
    window.set_font_mode('windows');assert read_settings(window.settings_path)['font_mode']=='windows'
    window.set_font_mode('pretendard');window._set_busy(True);assert window.checklist.model.read_only
    window._set_busy(False);window._set_off_days({0,3});assert window.store.get_meta('timetable_off_days')=='[0, 3]'
    window.dispose();close(window,app)
