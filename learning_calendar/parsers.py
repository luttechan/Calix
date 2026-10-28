"""Only extract movies from LearningX modules and non-quiz assignments from Canvas."""
from __future__ import annotations
from collections.abc import Iterable
from urllib.parse import urljoin, urlsplit
from .models import Course, Event

BASE_URL = 'https://canvas.bufs.ac.kr'


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
        except (TypeError, ValueError, KeyError):
            continue
        name = str(row.get('longName') or row.get('shortName') or row.get('originalName') or f'과목 {cid}')
        found[cid] = Course(cid, name)
    return list(found.values())


def parse_movies(course: Course, payload: object) -> list[Event]:
    if isinstance(payload, dict):
        payload = payload.get('modules')
    if not isinstance(payload, list):
        raise ValueError('LearningX 주차학습 응답이 배열이 아닙니다.')
    found: dict[str, Event] = {}
    for module in payload:
        if not isinstance(module, dict) or module.get('published') is False:
            continue
        week = str(module.get('title') or '')
        for item in module.get('module_items') or []:
            if not isinstance(item, dict) or item.get('published') is False:
                continue
            data = item.get('content_data') or {}
            if not isinstance(data, dict):
                continue
            media = data.get('item_content_data') or {}
            if not isinstance(media, dict) or media.get('content_type') != 'movie':
                continue
            identifier = data.get('item_id') or item.get('content_id') or item.get('module_item_id')
            if identifier is None:
                continue
            key = f'movie:{course.id}:{identifier}'
            found[key] = Event(
                key=key, course_id=course.id, course_name=course.name,
                kind='movie',
                title=str(data.get('title') or item.get('title') or media.get('title') or f'동영상 {identifier}'),
                due_at=data.get('due_at'), completed=bool(item.get('completed')),
                url=safe_url(item.get('url')), week=week,
            )
    return list(found.values())


def parse_assignments(course: Course, groups: object, submissions: object) -> list[Event]:
    if not isinstance(groups, list):
        raise ValueError('과제 그룹 응답이 배열이 아닙니다.')
    if not isinstance(submissions, list):
        raise ValueError('제출 상태 응답이 배열이 아닙니다.')
    submission_by_id = {}
    for sub in submissions:
        if isinstance(sub, dict) and sub.get('assignment_id') is not None:
            submission_by_id[str(sub['assignment_id'])] = sub
    found: dict[str, Event] = {}
    for group in groups:
        if not isinstance(group, dict):
            continue
        assignments = group.get('assignments') or []
        if not isinstance(assignments, list):
            continue
        for a in assignments:
            if not isinstance(a, dict) or a.get('published') is False:
                continue
            if a.get('is_quiz_assignment') is True or 'online_quiz' in (a.get('submission_types') or []):
                continue
            if a.get('id') is None:
                continue
            aid = str(a['id'])
            sub = submission_by_id.get(aid) or a.get('submission') or {}
            state = sub.get('workflow_state')
            done = state in ('submitted', 'graded', 'pending_review') or bool(sub.get('submitted_at'))
            key = f'assignment:{course.id}:{aid}'
            found[key] = Event(
                key=key, course_id=course.id, course_name=course.name,
                kind='assignment', title=str(a.get('name') or f'과제 {aid}'),
                due_at=a.get('due_at') or sub.get('cached_due_date'),
                completed=done,
                url=safe_url(a.get('html_url') or f'/courses/{course.id}/assignments/{aid}'),
                week=str(group.get('name') or ''),
            )
    return list(found.values())
