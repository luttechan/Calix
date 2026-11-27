"""Portable workspace records and conflict-aware Aurora reconciliation."""

from contextlib import ExitStack
from datetime import date, datetime
from hashlib import sha256
import json
import re
from urllib.parse import urlsplit
from uuid import uuid4

from .models import Course, Event, KST, parse_datetime, validate_manual_period
from .schedule_colors import minutes, normalize_color


KINDS = ("event", "canvasEdit", "task", "lesson", "timetableTerm", "grade", "journal", "focus", "holiday")
IDENTITY = re.compile(r"[A-Za-z0-9:_-]{1,150}")
MARKS = {"", "P", "NP", "F", *(letter + suffix for letter in "ABCD" for suffix in ("", "+", "-"))}
SCHOOL_ID = re.compile(r"canvas:([1-9][0-9]{0,17}):(assignment|video):([A-Za-z0-9_-]{1,100})")


def revision(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return sha256(raw.encode()).hexdigest()


def workspace_id(store):
    identifier = store.get_meta("vesper_workspace")
    if not identifier:
        identifier = uuid4().hex
        store.set_meta("vesper_workspace", identifier)
    return identifier


def school_id(key, url, media=None):
    from .parsers import safe_url

    kind, _, tail = key.partition(":")
    course, _, item = tail.partition(":")
    if kind not in ("assignment", "movie") or not re.fullmatch(r"[0-9]+", course):
        return None
    if kind == "movie":
        path = urlsplit(safe_url(url) or "").path
        module = re.fullmatch(rf"/courses/{course}/modules/items/([0-9]+)/?", path)
        if module:
            return f"canvas:{course}:video:{module[1]}"
        module_id = (media or {}).get("canvas_module_item_id")
        if isinstance(module_id, str) and re.fullmatch(r"[0-9]{1,19}", module_id):
            return f"canvas:{course}:video:{module_id}"
    identifier = f"canvas:{course}:{'video' if kind == 'movie' else kind}:{item}"
    return identifier if ":" not in item and item and IDENTITY.fullmatch(identifier) else None


def school_keys(store):
    keys = {}
    for row in store.db.execute("SELECT key,url,lms_data FROM events WHERE manual=0 AND active=1"):
        identifier = school_id(row["key"], row["url"], json.loads(row["lms_data"]))
        if identifier:
            keys[identifier] = None if identifier in keys else row["key"]
    return {key: native for key, native in keys.items() if native}


def is_allowed(api, kind):
    scope = {"lesson": "timetable", "timetableTerm": "timetable", "grade": "grades"}.get(kind)
    if not scope:
        return True
    try:
        api.security.require(f"{scope}.read")
        return True
    except ValueError:
        return False


def scan(api, kinds):
    result = {kind: {} for kind in kinds}
    store = api.store
    db = store.db
    aliases = json.loads(store.get_meta("vesper_record_aliases", "{}"))
    native_ids = {kind: {} for kind in kinds}

    def record(kind, default, native, value):
        identifier = aliases.get(kind, {}).get(str(native), default)
        result[kind][identifier] = {"revision": revision(value), "value": value}
        native_ids[kind][identifier] = native

    courses = {course.id: course.name for course in store.courses()}
    if "event" in result:
        for event in store.events():
            if event.manual:
                record("event", event.key, event.key, dict(
                    title=event.title, course=courses.get(event.course_id, ""), start=event.start_at, due=event.due_at,
                    note=event.note, done=event.completed, starred=event.starred,
                    category=event.type_name, color=event.type_color, series=event.series_id or None,
                ))
    if "canvasEdit" in result:
        for row in db.execute("""
            SELECT e.key, e.url, e.lms_data, c.title, COALESCE(c.note,e.note) note
            FROM events e LEFT JOIN event_customizations c ON c.event_key=e.key
            WHERE e.manual=0 AND e.active=1 AND (c.title IS NOT NULL OR COALESCE(c.note,e.note)<>'')
        """):
            identifier = school_id(row["key"], row["url"], json.loads(row["lms_data"]))
            if identifier:
                record("canvasEdit", identifier, row["key"], dict(title=row["title"], note=row["note"]))
    if "task" in result:
        linked_keys = {native: identifier for identifier, native in school_keys(store).items()}
        for row in db.execute("""
            SELECT t.*,s.name section,v.name status,v.kind status_kind,v.color status_color
            FROM checklist_tasks t JOIN checklist_sections s ON s.id=t.section_id
            LEFT JOIN checklist_statuses v ON v.id=t.status_id
            WHERE t.trashed=0
        """):
            real_source = row["source_key"]
            source = linked_keys.get(real_source)
            if real_source and not source:
                continue
            identity = 'source:' + sha256(source.encode()).hexdigest() if source else f"task:{row['id']}"
            record("task", identity, row["id"], dict(
                title=row["title"] or "", section=row["section"], status=row["status"] or "계획",
                statusColor=row["status_color"] or "#7582E6", done=row["status_kind"] == "done",
                due=row["due_at"], note=row["note"], role=row["role"], instructor=row["professor"], category=row["category"] or "",
                source=source,
            ))
    if "lesson" in result:
        for row in store.timetable(all_terms=True):
            identifier = row["id"]
            record("lesson", f"lesson:{identifier}", identifier, dict(
                title=row["title"] or courses.get(row["course_id"], ""), term=row["semester"],
                weekday=(row["day"] + 1) % 7 + 1,
                start=minutes(row["start_time"]) if row["start_time"] else 540,
                end=minutes(row["end_time"]) if row["end_time"] else 600,
                room=row["room"], lecturer=row["professor"], online=bool(row["is_online"]), color=row["color"],
            ))
    if "timetableTerm" in result:
        for entry in store.timetable_config()["terms"]:
            name = entry["name"]
            days = sorted((day + 1) % 7 + 1 for day in entry["offDays"])
            record("timetableTerm", "term:" + sha256(name.encode()).hexdigest(), name,
                   {"title": name, "days": ",".join(map(str, days))})
    if "grade" in result:
        for row in db.execute("SELECT * FROM grade_items"):
            # Imported course rows keep their Canvas identity and protected deletion rules.
            if not row["id"].startswith("manual:"):
                continue
            native = f"{row['semester']}\x1f{row['id']}"
            identifier = "grade:" + sha256(native.encode()).hexdigest()
            record("grade", identifier, native, dict(title=row["title"], term=row["semester"], credits=row["credits"],
                mark=row["grade"], category=row["category"], excluded=bool(row["excluded"])))
    if "journal" in result:
        for row in api.diary.db.execute("SELECT id,date,title,body,html FROM entries"):
            record("journal", f"diary:{row['id']}", row["id"],
                   {key: row[key] for key in ("date", "title", "body", "html")})
    if "focus" in result:
        for row in db.execute("SELECT id,day,seconds FROM focus_sessions"):
            record("focus", f"focus:{row['id']}", row["id"], dict(day=row["day"], seconds=row["seconds"]))
    if "holiday" in result:
        for row in api.holidays.db.execute("SELECT day,name,enabled FROM overrides"):
            record("holiday", f"holiday:{row['day']}", row["day"],
                   dict(day=row["day"], title=row["name"], enabled=bool(row["enabled"])))
    return result, native_ids, aliases


def text(value, key, maximum, default=""):
    result = value.get(key, default)
    if not isinstance(result, str) or len(result) > maximum:
        raise ValueError()
    result.encode("utf-8")
    return result


def number(value, key, low, high):
    result = value.get(key)
    if type(result) is not int or not low <= result <= high:
        raise ValueError()
    return result


def flag(value, key, default=False):
    result = value.get(key, default)
    if type(result) is not bool:
        raise ValueError()
    return int(result)


def stamp(value, key):
    result = value.get(key)
    if result is not None and (not isinstance(result, str) or len(result) > 48 or parse_datetime(result) is None):
        raise ValueError()
    return result


def day_key(value, key):
    result = text(value, key, 10)
    if date.fromisoformat(result).isoformat() != result:
        raise ValueError()
    return result


def named(db, table, name, limit, fields=(), values=()):
    row = db.execute(f"SELECT id FROM {table} WHERE name=? COLLATE NOCASE", (name,)).fetchone()
    if row:
        return row[0]
    if db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] >= limit:
        raise ValueError()
    columns = ",".join(("name", *fields))
    placeholders = ",".join("?" for _ in ("name", *fields))
    return db.execute(f"INSERT INTO {table}({columns}) VALUES({placeholders})", (name, *values)).lastrowid


def term(store, name):
    from .timetable_terms import write

    config = store.timetable_config()
    name = name or config["main"]
    changed = False
    if name not in {row["name"] for row in config["terms"]}:
        config["terms"].append({"name": name, "offDays": []})
        changed = True
    if not config["confirmed"]:
        config["confirmed"] = True
        config["main"] = name
        changed = True
    if changed:
        write(store, config)
    return name


def put(api, kind, native, value):
    store = api.store
    db = store.db
    new = uuid4().hex
    if kind == "canvasEdit":
        event = db.execute("SELECT title FROM events WHERE key=? AND manual=0 AND active=1", (native,)).fetchone()
        if not event:
            raise ValueError()
        title = value.get("title")
        if title is not None:
            title = text(value, "title", 200).strip()
            if not title:
                raise ValueError()
        db.execute("""INSERT INTO event_customizations(event_key,title,note) VALUES(?,?,?)
                      ON CONFLICT(event_key) DO UPDATE SET title=excluded.title,note=excluded.note""",
                   (native, None if title == event["title"] else title, text(value, "note", 20000)))
        return native
    title = text(value, "title", 200).strip()
    if kind != "focus" and not title:
        raise ValueError()
    if kind == "event":
        category = text(value, "category", 32).strip() or "할 일"
        start, due = stamp(value, "start"), stamp(value, "due")
        validate_manual_period(start, due)
        course_name = text(value, "course", 200)
        course = next((row.id for row in store.courses() if row.name == course_name), 0)
        previous = db.execute("SELECT course_id FROM events WHERE key=?", (native,)).fetchone()
        if previous and not course and not course_name:
            course = previous[0]
        color = normalize_color(text(value, "color", 7)) or "#7582E6"
        category_id = named(db, "event_types", category, 48, ("color",), (color,))
        key = store.save_manual_event(title, category_id, due, course, text(value, "note", 20000),
                                      bool(flag(value, "done")), native, start_at=start, _commit=False)
        series = value.get("series")
        if series is not None and (not isinstance(series, str) or not IDENTITY.fullmatch(series)):
            raise ValueError()
        if "series" in value:
            db.execute("UPDATE events SET series_id=? WHERE key=?", (series or "", key))
        db.execute("UPDATE events SET starred=? WHERE key=?", (flag(value, "starred"), key))
        return key
    if kind == "task":
        section = named(db, "checklist_sections", text(value, "section", 32).strip() or "수업", 6)
        status = named(db, "checklist_statuses", text(value, "status", 32).strip() or "계획", 30,
                       ("color", "kind"), (normalize_color(text(value, "statusColor", 7)) or "#7582E6",
                                           "done" if flag(value, "done") else "open"))
        source = value.get("source")
        source_key = school_keys(store).get(source) if isinstance(source, str) else None
        if source is not None and not source_key:
            raise ValueError()
        stored = db.execute("SELECT id FROM checklist_tasks WHERE source_key=?", (source_key,)).fetchone() if source_key else None
        key = native or (stored["id"] if stored else new)
        db.execute("""INSERT INTO checklist_tasks(id,section_id,status_id,title,due_at,note,role,professor,category,source_key)
                      VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                      section_id=excluded.section_id,status_id=excluded.status_id,title=excluded.title,due_at=excluded.due_at,
                      note=excluded.note,role=excluded.role,professor=excluded.professor,category=excluded.category,trashed=0""",
                   (key, section, status, title, stamp(value, "due"), text(value, "note", 20000),
                    text(value, "role", 100), text(value, "instructor", 120), text(value, "category", 100), source_key))
        return key
    if kind == "lesson":
        semester = term(store, text(value, "term", 40).strip())
        online = flag(value, "online")
        weekday = (number(value, "weekday", 1, 7) + 5) % 7
        start, end = number(value, "start", 0, 1439), number(value, "end", 1, 1439)
        if not online and start >= end:
            raise ValueError()
        hhmm = lambda n: f"{n // 60:02d}:{n % 60:02d}"
        attached = db.execute("SELECT course_id FROM timetable WHERE id=?", (native,)).fetchone()
        return store.add_timetable(
            attached[0] if attached else 0, weekday, hhmm(start), hhmm(end), text(value, "lecturer", 120),
            text(value, "room", 100), native, color=normalize_color(text(value, "color", 7)), title=title,
            is_online=online, semester=semester, _commit=False,
        )
    if kind == "timetableTerm":
        from .timetable_terms import write

        name = term(store, text(value, "title", 40).strip())
        if native and native != name:
            raise ValueError()
        days = text(value, "days", 13)
        if days and not re.fullmatch(r"[1-7](?:,[1-7]){0,6}", days):
            raise ValueError()
        config = store.timetable_config()
        entry = next(item for item in config["terms"] if item["name"] == name)
        entry["offDays"] = sorted({(int(day) + 5) % 7 for day in days.split(",")}) if days else []
        write(store, config)
        return name
    if kind == "grade":
        semester = term(store, text(value, "term", 40).strip())
        identifier = native.split("\x1f", 1)[1] if native else "manual:" + new
        if native and native.split("\x1f", 1)[0] != semester:
            raise ValueError()
        credits, mark = value.get("credits"), text(value, "mark", 3)
        category = text(value, "category", 20) or "일반"
        if (type(credits) not in (int, float) or not 0 <= credits <= 30 or (credits * 2) % 1 or
                mark not in MARKS or category not in ("전공", "교양", "일반")):
            raise ValueError()
        db.execute("INSERT OR REPLACE INTO grade_items VALUES(?,?,?,?,?,?,?)",
                   (semester, identifier, title, credits, mark, category, flag(value, "excluded")))
        return semester + "\x1f" + identifier
    if kind == "journal":
        key = native or new
        body = text(value, "body", 200000)
        # HTML authored on Aurora is preserved on metadata-only edits.
        previous = api.diary.db.execute("SELECT body,html FROM entries WHERE id=?", (key,)).fetchone()
        html = previous["html"] if previous and previous["body"] == body else ""
        api.diary.db.execute("INSERT OR REPLACE INTO entries(id,date,title,body,html) VALUES(?,?,?,?,?)",
                             (key, day_key(value, "date"), title, body, html))
        return key
    if kind == "focus":
        key = native or new
        db.execute("INSERT OR REPLACE INTO focus_sessions VALUES(?,?,?)",
                   (key, day_key(value, "day"), number(value, "seconds", 1, 86400)))
        return key
    from .holidays import validate_override

    key = day_key(value, "day")
    if native and native != key:
        raise ValueError()
    api.holidays.db.execute("INSERT OR REPLACE INTO overrides(day,name,enabled) VALUES(?,?,?)",
                           validate_override(key, title, flag(value, "enabled", True)))
    return key


def drop(api, kind, native):
    db = api.store.db
    if kind == "event":
        db.execute("UPDATE events SET active=0 WHERE key=? AND manual=1", (native,))
    elif kind == "canvasEdit":
        db.execute("UPDATE event_customizations SET title=NULL,note='' WHERE event_key=?", (native,))
        db.execute("UPDATE events SET note='' WHERE key=? AND manual=0", (native,))
    elif kind == "task":
        db.execute("UPDATE checklist_tasks SET trashed=1 WHERE id=?", (native,))
    elif kind == "grade":
        db.execute("DELETE FROM grade_items WHERE semester=? AND id=?", tuple(native.split("\x1f", 1)))
    elif kind == "journal":
        api.diary.db.execute("DELETE FROM entries WHERE id=?", (native,))
    elif kind == "holiday":
        api.holidays.db.execute("DELETE FROM overrides WHERE day=?", (native,))
    elif kind == "lesson":
        db.execute("DELETE FROM timetable WHERE id=?", (native,))
    elif kind == "timetableTerm":
        return
    else:
        db.execute("DELETE FROM focus_sessions WHERE id=?", (native,))


def reconcile(api, offer):
    from .vesper_transfer import LIMIT

    changes = offer.get("changes")
    if not isinstance(changes, dict) or any(kind not in KINDS for kind in changes):
        raise ValueError("연동 데이터를 확인하세요.")
    if any(not isinstance(rows, dict) for rows in changes.values()) or sum(map(len, changes.values())) > 6000:
        raise ValueError("연동 데이터를 확인하세요.")
    kinds = [kind for kind in KINDS if is_allowed(api, kind)]
    # A closed timetable/grade scope stays closed during transfer.
    conflicts = []
    store = api.store
    owner = store.get_meta("canvas_user_id")
    with ExitStack() as transaction:
        for connection in (store.db, api.diary.db, api.holidays.db):
            transaction.enter_context(connection)
            connection.execute("BEGIN IMMEDIATE")
        if offer.get("school"):
            if owner and offer.get("schoolOwner") == owner:
                import_school(store, offer["school"])
            else:
                conflicts.append("school/account")
        current, keys, aliases = scan(api, kinds)
        remote_keys = school_keys(store) if changes.get("canvasEdit") else {}
        for kind, rows in changes.items():
            for identifier, change in rows.items():
                if not IDENTITY.fullmatch(identifier) or not isinstance(change, dict):
                    raise ValueError("연동 데이터를 확인하세요.")
                if kind not in kinds:
                    conflicts.append(f"{kind}/{identifier}")
                    continue
                if kind == "canvasEdit" and (not owner or offer.get("schoolOwner") != owner or identifier not in remote_keys):
                    conflicts.append(f"{kind}/{identifier}")
                    continue
                previous = current[kind].get(identifier)
                base, value = change.get("base"), change.get("value")
                if (previous and previous["value"] == value) or (previous is None and value is None):
                    continue
                if base != (previous["revision"] if previous else None):
                    conflicts.append(f"{kind}/{identifier}")
                    continue
                native = keys[kind].get(identifier)
                if value is None:
                    drop(api, kind, native)
                elif isinstance(value, dict):
                    target = {"journal": api.diary.db, "holiday": api.holidays.db}.get(kind, store.db)
                    target.execute("SAVEPOINT vesper_item")
                    try:
                        if kind == "holiday" and identifier != f"holiday:{value.get('day')}":
                            raise ValueError()
                        if kind == "canvasEdit":
                            native = remote_keys[identifier]
                        if kind == "task" and value.get("source") is not None:
                            source = text(value, "source", 150)
                            if (not owner or offer.get("schoolOwner") != owner or
                                    identifier != "source:" + sha256(source.encode()).hexdigest()):
                                raise ValueError()
                        updated = put(api, kind, native, value)
                        target.execute("RELEASE vesper_item")
                        aliases.setdefault(kind, {})[str(updated)] = identifier
                    except (ValueError, OverflowError):
                        target.execute("ROLLBACK TO vesper_item")
                        target.execute("RELEASE vesper_item")
                        conflicts.append(f"{kind}/{identifier}")
                else:
                    conflicts.append(f"{kind}/{identifier}")
        store.set_meta("vesper_record_aliases", json.dumps(aliases, ensure_ascii=False), _commit=False)
        remote_owner = offer.get("schoolOwner")
        snapshot = outgoing(api, kinds, conflicts, share_school=not remote_owner or remote_owner == owner)
        if len(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode()) > LIMIT - 1024:
            raise ValueError("동기화 용량 한도를 초과했습니다.")
    api.holidays.reload()
    snapshot["nickname"] = sync_nickname(api, offer.get("nickname"), conflicts)
    return snapshot


def import_school(store, incoming):
    """Merge verified school rows without retiring the desktop's own records."""
    from .parsers import CollectedEvents, safe_url

    if not isinstance(incoming, list) or len(incoming) > 5000:
        raise ValueError("학교 일정의 범위를 확인하세요.")
    courses = {course.id: course for course in store.courses()}
    additions = {}
    keys = school_keys(store)
    seen = set()
    for row in incoming:
        if not isinstance(row, dict):
            raise ValueError("학교 일정의 형식을 확인하세요.")
        key = text(row, "id", 150)
        identity = SCHOOL_ID.fullmatch(key)
        if not identity or key in seen:
            continue
        seen.add(key)
        course, source_kind, item = identity.groups()
        owner_course = courses.get(int(course))
        if not owner_course:
            continue
        kind = "movie" if source_kind == "video" else "assignment"
        title = text(row, "title", 500).strip()
        due = stamp(row, "due")
        done = flag(row, "done")
        native = keys.get(key)
        if native:
            store.db.execute("UPDATE events SET due_at=COALESCE(due_at,?),"
                             "completed=CASE WHEN ? AND completion_verified=0 THEN 1 ELSE completed END,"
                             "completion_verified=CASE WHEN ? THEN 1 ELSE completion_verified END WHERE key=? AND manual=0",
                             (due, done, done, native))
            continue
        url = safe_url(row.get("url")) if isinstance(row.get("url"), str) else None
        native = f"{kind}:{course}:{item}"
        if not title or not url or store.db.execute("SELECT 1 FROM events WHERE key=?", (native,)).fetchone():
            continue
        path = urlsplit(url).path
        expected = f"/courses/{course}/assignments/{item}" if kind == "assignment" else f"/courses/{course}/modules/items/{item}"
        if path.rstrip("/") != expected:
            continue
        events = additions.setdefault((owner_course.id, kind), CollectedEvents((), complete=False))
        events.append(Event(native, owner_course.id, owner_course.name, kind, title, due, done, url=url,
                            completion_verified=done))
    if additions:
        store.apply_batch([], additions, _commit=False)


def sync_nickname(api, change, conflicts):
    from .preferences import write_settings

    current = api.settings.get("nickname", "")
    if change is None:
        return current
    value, base = (change.get("value"), change.get("base")) if isinstance(change, dict) else (None, None)
    if (not isinstance(value, str) or len(value) > 30 or value != value.strip()
            or (value and not value.isprintable()) or (base is not None and not isinstance(base, str))):
        conflicts.append("profile/nickname")
        return current
    if value == current or (base is None and current):
        return current
    if base is not None and base != current:
        conflicts.append("profile/nickname")
        return current
    try:
        write_settings(api.settings_path, dict(api.settings, nickname=value))
    except (OSError, ValueError):
        conflicts.append("profile/nickname")
        return current
    api.settings["nickname"] = value
    return value


def outgoing(api, kinds, conflicts, *, share_school=True):
    store = api.store
    result, records_to_native, _ = scan(api, kinds)
    from .attendance import read
    from .parsers import safe_url

    if not share_school and "task" in result:
        result["task"] = {key: row for key, row in result["task"].items() if not key.startswith("source:")}
    scoped_attendance = read(store) if share_school else []
    item_due = {str(row.get("key")): row.get("due_at") for row in scoped_attendance
                if row.get("source") == "item" and not row.get("stale") and row.get("due_at")}
    school = {}
    for event in store.events() if share_school else ():
        if event.manual:
            continue
        identifier = school_id(event.key, event.url, event.lms_data)
        if identifier:
            due = event.due
            if due is None and event.kind == "movie":
                learning_item = event.lms_data.get("learningx_item_id")
                if not learning_item:
                    path = urlsplit(safe_url(event.url) or "").path
                    exact = re.fullmatch(r"/learningx/lti/[^/]+/items/view/([0-9]+)/?", path)
                    learning_item = exact[1] if exact and exact[1] == event.key.rsplit(":", 1)[-1] else None
                if learning_item:
                    due = parse_datetime(item_due.get(f"item:{event.course_id}:{learning_item}"))
            if identifier in school and (school[identifier]["due"] or due is None):
                continue
            school[identifier] = dict(
                id=identifier, title=event.title, course=event.course_name, kind=event.kind,
                due=due.isoformat() if due else None,
                done=event.completed, note=event.note, url=safe_url(event.url) if event.url else None,
                status=event.lms_data.get("status"),
                feedback="\n\n".join(str(item.get("text", "")) for item in (event.lms_data.get("comments") or ())
                                     if isinstance(item, dict))[:20000] or None,
            )
    attendance = [dict(id=str(row.get("key", "")), course=row.get("course_name", ""), title=row.get("title", ""),
                       status=row.get("status", ""), date=row.get("date")) for row in scoped_attendance]
    snapshot = dict(records=result, conflicts=conflicts, school=list(school.values()), attendance=attendance,
                    owner=store.get_meta("canvas_user_id"), mainTerm=store.timetable_config()["main"])
    if "lesson" in result:
        course_ids = {row["id"]: row["course_id"] for row in store.timetable(all_terms=True) if row["course_id"] > 0}
        for key, row in result["lesson"].items():
            course_id = course_ids.get(records_to_native["lesson"][key])
            if course_id:
                row["courseID"] = course_id
        snapshot["timetableColors"] = api.settings["timetable_colors"]
    return snapshot
