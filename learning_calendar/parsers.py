"""Only extract movies from LearningX modules and non-quiz assignments from Canvas."""
from __future__ import annotations
from collections.abc import Iterable
from urllib.parse import urljoin, urlsplit
from .models import Course, Event,parse_datetime

BASE_URL = 'https://canvas.bufs.ac.kr'


class CollectedEvents(list):
    """Usable records plus whether missing records can safely be archived."""
    def __init__(self,values=(),*,complete=True):super().__init__(values);self.complete=complete


def item_identifier(value):
    if isinstance(value,bool) or not isinstance(value,(int,str)):raise ValueError('일정 ID가 올바르지 않습니다.')
    value=str(value)
    if not value or len(value)>128 or ':' in value or any(c.isspace() or ord(c)<32 for c in value):raise ValueError('일정 ID가 올바르지 않습니다.')
    return value


def due_value(value):
    if value is None or value=='':return None
    if not isinstance(value,str) or parse_datetime(value) is None:raise ValueError('일정 기한이 올바르지 않습니다.')
    return value


def record_event(found,blocked,event):
    if event.key in blocked:return False
    if event.key in found and found[event.key]!=event:
        found.pop(event.key);blocked.add(event.key);return False
    found[event.key]=event;return True


def safe_url(url: object) -> str:
    if not isinstance(url, str) or not url:
        return ''
    try:
        absolute = urljoin(BASE_URL, url)
        parsed = urlsplit(absolute)
        trusted=(parsed.scheme=='https' and parsed.hostname=='canvas.bufs.ac.kr' and parsed.port in (None,443) and parsed.username is None and parsed.password is None)
        return absolute if trusted else ''
    except ValueError:return ''


def course_list(payload: object) -> list[Course]:
    if not isinstance(payload, list):
        raise ValueError('과목 API의 응답 형식이 올바르지 않습니다.')
    found: dict[int, Course] = {}
    for row in payload:
        if not isinstance(row, dict):
            continue
        try:
            cid = int(row['id'])
        except (TypeError, ValueError, KeyError,OverflowError):
            continue
        if isinstance(row['id'],bool) or not 0<cid<2**63:continue
        name = str(row.get('name') or row.get('longName') or row.get('shortName') or row.get('originalName') or row.get('course_code') or f'과목 {cid}')
        found[cid] = Course(cid, name)
    return list(found.values())


def movie_completion(item):
    value=item.get('completed')
    if value is True or value==1 or (isinstance(value,str) and value.lower()=='true'):return True
    attendance=item.get('attendance_status')
    if attendance in ('attendance','late','excused'):return True
    if value is False or value==0 or (isinstance(value,str) and value.lower()=='false'):return False
    if attendance in ('none','absent'):return False
    return None


def parse_movies(course: Course, payload: object) -> list[Event]:
    if isinstance(payload, dict):
        payload = payload.get('modules')
    if not isinstance(payload, list):
        raise ValueError('LearningX 주차학습 응답이 배열이 아닙니다.')
    found: dict[str, Event] = {};blocked=set();complete=True
    for module in payload:
        if not isinstance(module,dict):complete=False;continue
        if module.get('published') is False:continue
        week = str(module.get('title') or '')
        items=module.get('module_items')
        if not isinstance(items,list):complete=False;continue
        for item in items:
            if not isinstance(item,dict):complete=False;continue
            if item.get('published') is False:continue
            data = item.get('content_data')
            if not isinstance(data,dict):
                if item.get('content_type') not in ('assignment','quiz','discussion','file','page'):complete=False
                continue
            media = data.get('item_content_data') or {}
            if not isinstance(media, dict):media={}
            if data.get('item_content_type')=='commons' and not media.get('content_type'):complete=False;continue
            if (media.get('content_type') or data.get('item_content_type')) not in ('movie','mp4','zoom'):
                continue
            identifier = data.get('item_id') or item.get('content_id') or item.get('module_item_id')
            try:identifier=item_identifier(identifier);due=due_value(data.get('due_at'))
            except ValueError:complete=False;continue
            key = f'movie:{course.id}:{identifier}'
            completion=movie_completion(item)
            event = Event(
                key=key, course_id=course.id, course_name=course.name,
                kind='movie',
                title=str(data.get('title') or item.get('title') or media.get('title') or f'동영상 {identifier}'),
                due_at=due, completed=completion is True,completion_verified=completion is not None,
                url=safe_url(item.get('url')), week=week,
            )
            if not record_event(found,blocked,event):complete=False
    return CollectedEvents(found.values(),complete=complete)


def parse_assignments(course: Course, groups: object, submissions: object) -> list[Event]:
    if not isinstance(groups, list):
        raise ValueError('과제 그룹 응답이 배열이 아닙니다.')
    if not isinstance(submissions, list):
        raise ValueError('제출 상태 응답이 배열이 아닙니다.')
    submission_by_id = {};complete=True
    for sub in submissions:
        if isinstance(sub, dict) and sub.get('assignment_id') is not None:
            submission_by_id[str(sub['assignment_id'])] = sub
        else:complete=False
    found: dict[str, Event] = {};blocked=set()
    for group in groups:
        if not isinstance(group, dict):
            complete=False;continue
        assignments = group.get('assignments')
        if not isinstance(assignments, list):
            complete=False;continue
        for a in assignments:
            if not isinstance(a,dict):complete=False;continue
            if a.get('published') is False:continue
            types=a.get('submission_types') or []
            if not isinstance(types,list):complete=False;continue
            if a.get('is_quiz_assignment') is True or 'online_quiz' in types:
                continue
            try:aid=item_identifier(a.get('id'))
            except ValueError:complete=False;continue
            sub = submission_by_id.get(aid) or a.get('submission') or {}
            if not isinstance(sub,dict):sub={}
            state = sub.get('workflow_state')
            done = state in ('submitted', 'graded', 'pending_review') or bool(sub.get('submitted_at'))
            key = f'assignment:{course.id}:{aid}'
            try:due=due_value(a.get('due_at') or sub.get('cached_due_date'))
            except ValueError:complete=False;continue
            event = Event(
                key=key, course_id=course.id, course_name=course.name,
                kind='assignment', title=str(a.get('name') or f'과제 {aid}'),
                due_at=due,
                completed=done,completion_verified=bool(sub.get('submitted_at')) or state in ('submitted','graded','pending_review','unsubmitted','untaken'),
                url=safe_url(a.get('html_url') or f'/courses/{course.id}/assignments/{aid}'),
                week=str(group.get('name') or ''),
            )
            if not record_event(found,blocked,event):complete=False
    return CollectedEvents(found.values(),complete=complete)
