"""LearningX attendance projection. Never infer attendance from a deadline."""

import json
from datetime import datetime
from .models import KST, parse_datetime

KEY = "attendance_v159"
STATES = {
    "attendance": "출석",
    "late": "지각",
    "absent": "결석",
    "excused": "공결",
    "none": "미확인",
}


def normalize_status(value) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    state = value.strip().casefold()
    return state if state in STATES else "unknown"


def integer(value):
    if type(value) is int and 0 <= value < 2**53:
        return value
    return None


def text(value, limit=500):
    return value[:limit] if isinstance(value, str) else ""


def date(value):
    if not isinstance(value, str) or not value:
        return ""
    try:
        if len(value) == 10:
            datetime.strptime(value, "%Y-%m-%d")
            return value
    except ValueError:
        return ""
    parsed = parse_datetime(value)
    return parsed.isoformat() if parsed else ""


def project(course, sources):
    rows = []
    lessons = sources.get("lessons")
    statuses = sources.get("lessons/attendances")
    indexed = {}
    if isinstance(statuses, list):
        for s in statuses:
            if isinstance(s, dict):
                indexed[
                    (integer(s.get("week_position")), integer(s.get("lesson_position")))
                ] = s
    if isinstance(lessons, list):
        for week in lessons[:200]:
            if not isinstance(week, dict) or not isinstance(week.get("lessons"), list):
                raise ValueError("출결 주차 형식을 확인하지 못했습니다.")
            w = integer(week.get("week_position"))
            if w is None:
                raise ValueError("출결 주차를 확인하지 못했습니다.")
            for lesson in week["lessons"][:200]:
                if not isinstance(lesson, dict):
                    raise ValueError("출결 차시를 확인하지 못했습니다.")
                l = integer(lesson.get("lesson_position"))
                if l is None:
                    raise ValueError("출결 차시를 확인하지 못했습니다.")
                state = normalize_status(indexed.get((w, l), {}).get("attendance_status")) or "none"
                rows.append(
                    dict(
                        key=f"lesson:{course.id}:{w}:{l}",
                        source="lesson",
                        course_id=course.id,
                        course_name=course.name,
                        week=w,
                        lesson=l,
                        date=date(lesson.get("makeup_date"))
                        or date(lesson.get("class_date"))
                        or date(lesson.get("display_class_date")),
                        start_at=date(week.get("unlock_at")),
                        due_at=date(week.get("due_at")),
                        title=f"{w}주차 {l}차시",
                        kind=text(lesson.get("attendance_calc_type"), 80),
                        status=state,
                    )
                )
    items = sources.get("attendance_items")
    summaries = sources.get("attendance_items/summary")
    summaries = (
        summaries.get("attendance_summaries", {}) if isinstance(summaries, dict) else {}
    )
    by_item_id = {}
    if isinstance(summaries, dict):
        for key, summary in summaries.items():
            if isinstance(summary, dict):
                item_id = integer(summary.get("item_id"))
                status = normalize_status(summary.get("attendance_status")) or "none"
                by_item_id[str(item_id) if item_id is not None else key] = status
    if isinstance(items, dict) and isinstance(items.get("attendance_items"), list):
        for item in items["attendance_items"][:10000]:
            if not isinstance(item, dict):
                raise ValueError("출결 항목을 확인하지 못했습니다.")
            if item.get("published") is False or item.get("use_attendance") is False:
                continue
            identifier = integer(item.get("item_id"))
            if identifier is None:
                raise ValueError("출결 항목 ID를 확인하지 못했습니다.")
            state = by_item_id.get(str(identifier), "none")
            media = item.get("item_content_data") or {}
            rows.append(
                dict(
                    key=f"item:{course.id}:{identifier}",
                    source="item",
                    course_id=course.id,
                    course_name=course.name,
                    week=integer(item.get("week_position")),
                    lesson=integer(item.get("lesson_position")),
                    date=date(item.get("unlock_at")),
                    start_at=date(item.get("unlock_at")),
                    due_at=date(item.get("due_at")),
                    title=text(item.get("title")),
                    kind=text(
                        media.get("content_type") or item.get("item_content_type"), 80
                    ),
                    status=state,
                )
            )
    return rows


def save(store, courses, payload):
    """Replace each successful source independently; failed sources stay visible."""
    try:
        previous = json.loads(store.get_meta(KEY, "{}"))
    except (ValueError, TypeError):
        previous = {}
    if not isinstance(previous, dict):
        previous = {}
    responses = payload.get("responses", {})
    now = datetime.now(KST).isoformat()
    for course in courses:
        old = previous.get(str(course.id), {})
        sources = dict(old.get("sources", {}))
        errors = []
        for path in (
            "lessons",
            "lessons/attendances",
            "attendance_items",
            "attendance_items/summary",
        ):
            response = responses.get(f"/learningx/api/v1/courses/{course.id}/{path}")
            if not isinstance(response, dict) or "data" not in response:
                errors.append(path)
                continue
            data = response["data"]
            valid = (
                isinstance(data, list)
                if path.startswith("lessons")
                else isinstance(data, dict)
                and isinstance(
                    data.get(
                        "attendance_items"
                        if path == "attendance_items"
                        else "attendance_summaries"
                    ),
                    list if path == "attendance_items" else dict,
                )
            )
            if not valid:
                errors.append(path)
                continue
            sources[path] = data
        try:
            rows = project(course, sources)
        except (ValueError, TypeError, AttributeError):
            previous[str(course.id)] = dict(old, stale=True)
            continue
        previous[str(course.id)] = dict(
            sources=sources,
            rows=rows,
            stale=bool(errors),
            updated_at=now if not errors else old.get("updated_at", ""),
        )
    # Drop no-longer-enrolled courses from the displayed projection.
    previous = {
        str(c.id): previous[str(c.id)] for c in courses if str(c.id) in previous
    }
    store.set_meta(KEY, json.dumps(previous, ensure_ascii=False), _commit=False)


def read(store):
    try:
        values = json.loads(store.get_meta(KEY, "{}"))
        return [
            dict(
                row,
                stale=value.get("stale", False),
                updated_at=value.get("updated_at", ""),
            )
            for value in values.values()
            for row in value.get("rows", [])
        ]
    except (ValueError, TypeError, AttributeError):
        return []
