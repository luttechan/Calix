"""Convert verified native Canvas module metadata without loading media."""

from .models import Event, parse_datetime
from .parsers import CollectedEvents, safe_url, record_event


def parse_canvas_modules(course, value):
    if not isinstance(value, dict) or not isinstance(value.get("items"), list):
        raise ValueError("모듈 자료를 확인하지 못했습니다.")
    complete = value.get("complete") is True
    found, blocked = {}, set()
    for row in value["items"]:
        try:
            if not isinstance(row, dict):
                raise ValueError("모듈 항목 형식")
            item_id, source_id = row.get("id"), row.get("source_id")
            if (
                type(item_id) is not int
                or type(source_id) is not int
                or not 0 < item_id < 2**63
                or not 0 < source_id < 2**63
            ):
                raise ValueError("모듈 항목 ID")
            kind = row.get("source_kind")
            if kind not in ("file", "page", "externalurl", "externaltool"):
                raise ValueError("모듈 영상 유형")
            url = safe_url(row.get("url"))
            from urllib.parse import urlsplit

            if (
                not url
                or urlsplit(url).path != f"/courses/{course.id}/modules/items/{item_id}"
            ):
                raise ValueError("모듈 연결 주소")
            title = row.get("title")
            if not isinstance(title, str) or not title.strip() or len(title) > 1000:
                raise ValueError("모듈 영상명")
            details = row.get("content_details") or {}
            if not isinstance(details, dict):
                raise ValueError("모듈 일정 형식")
            dates = {}
            for key in ("due_at", "unlock_at", "lock_at"):
                raw = details.get(key)
                if raw is not None and not isinstance(raw, str):
                    raise ValueError("모듈 일정 날짜")
                date = parse_datetime(raw)
                if raw is not None and not date:
                    raise ValueError("모듈 일정 날짜")
                dates[key] = date.isoformat() if date else None
            done = row.get("completed")
            event = Event(
                f"movie:{course.id}:canvas-{kind}:{source_id}",
                course.id,
                course.name,
                "movie",
                title.strip(),
                dates["due_at"],
                done is True,
                url=url,
                week=str(row.get("week", ""))[:200],
                completion_verified=type(done) is bool,
                start_at=dates["unlock_at"],
                lock_at=dates["lock_at"],
            )
            # A repeated file/page refers to the same content, not a new video.
            if event.key in found:
                old = found[event.key]
                if (old.title, old.due_at, old.completed, old.completion_verified) != (
                    event.title,
                    event.due_at,
                    event.completed,
                    event.completion_verified,
                ):
                    complete = False
                continue
            if not record_event(found, blocked, event):
                complete = False
        except (TypeError, ValueError, OverflowError):
            complete = False
    return CollectedEvents(found.values(), complete=complete)
