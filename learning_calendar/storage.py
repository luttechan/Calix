from __future__ import annotations
from . import secure_db as sqlite3
import json
from contextlib import nullcontext
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import replace
from urllib.parse import urlsplit
from .models import Course, Event

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS focus_sessions (id TEXT PRIMARY KEY, day TEXT NOT NULL, seconds INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS courses (id INTEGER PRIMARY KEY, name TEXT NOT NULL, alias TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS events (
  key TEXT PRIMARY KEY, course_id INTEGER NOT NULL, kind TEXT NOT NULL,
  title TEXT NOT NULL, due_at TEXT, completed INTEGER NOT NULL,
  url TEXT NOT NULL DEFAULT '', week TEXT NOT NULL DEFAULT '',
  starred INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
  active INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_due ON events(due_at);
CREATE TABLE IF NOT EXISTS changes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL,
  change_type TEXT NOT NULL, detail TEXT NOT NULL, changed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS timetable (
 id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER NOT NULL,
 day INTEGER NOT NULL CHECK(day BETWEEN 0 AND 6), start_time TEXT NOT NULL,
 end_time TEXT NOT NULL, professor TEXT NOT NULL DEFAULT '', room TEXT NOT NULL DEFAULT ''
);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        columns = {r["name"] for r in self.db.execute("PRAGMA table_info(courses)")}
        if "alias" not in columns:
            self.db.execute(
                "ALTER TABLE courses ADD COLUMN alias TEXT NOT NULL DEFAULT ''"
            )
            self.db.commit()
        if "color" not in {
            r["name"] for r in self.db.execute("PRAGMA table_info(timetable)")
        }:
            self.db.execute(
                "ALTER TABLE timetable ADD COLUMN color TEXT NOT NULL DEFAULT ''"
            )
            self.db.commit()
        timetable_columns = {
            r["name"] for r in self.db.execute("PRAGMA table_info(timetable)")
        }
        for name, definition in (
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("is_online", "INTEGER NOT NULL DEFAULT 0"),
            ("semester", "TEXT NOT NULL DEFAULT ''"),
        ):
            if name not in timetable_columns:
                self.db.execute(f"ALTER TABLE timetable ADD COLUMN {name} {definition}")
        from .timetable_terms import initialize as initialize_terms

        initialize_terms(self)
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_timetable_semester ON timetable(semester,day,start_time)"
        )
        event_columns = {
            r["name"] for r in self.db.execute("PRAGMA table_info(events)")
        }
        for name, definition in (
            ("manual", "INTEGER NOT NULL DEFAULT 0"),
            ("type_id", "INTEGER"),
            ("series_id", "TEXT NOT NULL DEFAULT ''"),
            ("completion_verified", "INTEGER NOT NULL DEFAULT 1"),
            ("lms_data", "TEXT NOT NULL DEFAULT '{}'"),
            ("start_at", "TEXT"),
            ("lock_at", "TEXT"),
        ):
            if name not in event_columns:
                self.db.execute(f"ALTER TABLE events ADD COLUMN {name} {definition}")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS event_types(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE COLLATE NOCASE,color TEXT NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS event_customizations(event_key TEXT PRIMARY KEY,title TEXT,type_id INTEGER,note TEXT NOT NULL DEFAULT '')"
        )
        if not self.db.execute("SELECT 1 FROM event_types LIMIT 1").fetchone():
            self.db.executemany(
                "INSERT INTO event_types(name,color) VALUES(?,?)",
                [("할 일", "#7582E6"), ("약속", "#D48560"), ("공부", "#3AA68E")],
            )
        from .checklist_store import initialize

        initialize(self.db)
        self.db.commit()

    def close(self):
        self.db.close()

    def courses(self) -> list[Course]:
        return [
            Course(row["id"], row["alias"] or row["name"])
            for row in self.db.execute("SELECT * FROM courses ORDER BY name")
        ]

    def events(self, include_inactive: bool = False) -> list[Event]:
        where = "" if include_inactive else "WHERE e.active=1"
        rows = self.db.execute(
            f"""SELECT e.*, CASE WHEN e.manual=1 AND e.course_id=0 THEN '개인 일정' ELSE COALESCE(NULLIF(c.alias,''),c.name,'과목 '||e.course_id) END course_name,
                                  COALESCE(o.title,e.title) display_title,COALESCE(o.note,e.note) display_note,
                                  COALESCE(o.type_id,e.type_id) display_type_id,t.name type_name,t.color type_color
                                  FROM events e LEFT JOIN courses c ON c.id=e.course_id LEFT JOIN event_customizations o ON o.event_key=e.key
                                  LEFT JOIN event_types t ON t.id=COALESCE(o.type_id,e.type_id)
                                  {where} ORDER BY e.due_at IS NULL,e.due_at,e.title"""
        )
        return [
            Event(
                key=r["key"],
                course_id=r["course_id"],
                course_name=r["course_name"],
                kind=r["kind"],
                title=r["display_title"],
                due_at=r["due_at"],
                completed=bool(r["completed"]),
                completion_verified=bool(r["completion_verified"]),
                url=r["url"],
                week=r["week"],
                starred=bool(r["starred"]),
                note=r["display_note"],
                type_id=r["display_type_id"],
                type_name=r["type_name"] or "",
                type_color=r["type_color"] or "",
                manual=bool(r["manual"]),
                series_id=r["series_id"],
                source_title=r["title"],
                start_at=r["start_at"],
                lock_at=r["lock_at"],
                lms_data=json.loads(r["lms_data"]),
            )
            for r in rows
        ]

    def event_types(self):
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT t.*,COUNT(e.key) usage_count FROM event_types t LEFT JOIN (SELECT key,type_id FROM events WHERE manual=1 UNION ALL SELECT event_key,type_id FROM event_customizations) e ON e.type_id=t.id GROUP BY t.id ORDER BY t.id"
            )
        ]

    def save_event_details(self, key, title, type_id, note):
        row = self.db.execute(
            "SELECT title,manual FROM events WHERE key=?", (key,)
        ).fetchone()
        if row is None or row["manual"]:
            raise ValueError("학교 일정을 찾지 못했습니다.")
        title = str(title).strip()
        note = str(note)
        if not title or len(title) > 200:
            raise ValueError("일정명은 1~200자로 입력하세요.")
        if len(note) > 20000:
            raise ValueError("메모는 20,000자까지 저장할 수 있습니다.")
        if (
            type_id is not None
            and not self.db.execute(
                "SELECT 1 FROM event_types WHERE id=?", (type_id,)
            ).fetchone()
        ):
            raise ValueError("유형을 선택하세요.")
        override = None if title == row["title"] else title
        with self.db:
            self.db.execute(
                "INSERT INTO event_customizations(event_key,title,type_id,note) VALUES(?,?,?,?) ON CONFLICT(event_key) DO UPDATE SET title=excluded.title,type_id=excluded.type_id,note=excluded.note",
                (key, override, type_id, note),
            )

    def local_customizations(self):
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT event_key,title,type_id,note FROM event_customizations UNION ALL SELECT e.key,NULL,NULL,e.note FROM events e WHERE e.manual=0 AND e.note<>'' AND NOT EXISTS(SELECT 1 FROM event_customizations o WHERE o.event_key=e.key)"
            )
        ]

    def save_event_type(self, name, color, item_id=None):
        from .schedule_colors import normalize_color

        name = str(name).strip()
        color = normalize_color(color)
        if not name or len(name) > 24:
            raise ValueError("유형 이름은 1~24자로 입력하세요.")
        if name in ("과제", "영상"):
            raise ValueError("과제와 영상은 자동 동기화 유형입니다.")
        if not color:
            raise ValueError("색상을 선택하세요.")
        try:
            with self.db:
                if item_id:
                    self.db.execute(
                        "UPDATE event_types SET name=?,color=? WHERE id=?",
                        (name, color, item_id),
                    )
                else:
                    item_id = self.db.execute(
                        "INSERT INTO event_types(name,color) VALUES(?,?)", (name, color)
                    ).lastrowid
        except sqlite3.IntegrityError:
            raise ValueError("같은 이름의 유형이 있습니다.") from None
        return item_id

    def remove_event_type(self, item_id):
        if self.db.execute(
            "SELECT 1 FROM events WHERE type_id=? UNION ALL SELECT 1 FROM event_customizations WHERE type_id=? LIMIT 1",
            (item_id, item_id),
        ).fetchone():
            raise ValueError("사용 중인 유형은 삭제할 수 없습니다.")
        if self.db.execute("SELECT COUNT(*) FROM event_types").fetchone()[0] <= 1:
            raise ValueError("유형은 하나 이상 필요합니다.")
        with self.db:
            self.db.execute("DELETE FROM event_types WHERE id=?", (item_id,))

    def save_manual_event(
        self,
        title,
        type_id,
        due_at=None,
        course_id=0,
        note="",
        completed=False,
        key=None,
        *,
        _commit=True,
    ):
        from uuid import uuid4
        from .models import parse_datetime

        title = str(title).strip()
        if not title or len(title) > 200:
            raise ValueError("일정명은 1~200자로 입력하세요.")
        if len(note) > 20000:
            raise ValueError("메모는 20,000자까지 저장할 수 있습니다.")
        if due_at is not None and parse_datetime(due_at) is None:
            raise ValueError("기한을 확인하세요.")
        if not self.db.execute(
            "SELECT 1 FROM event_types WHERE id=?", (type_id,)
        ).fetchone():
            raise ValueError("유형을 선택하세요.")
        now = datetime.now(timezone.utc).isoformat()
        with self.db if _commit else nullcontext():
            if key:
                if not self.db.execute(
                    "SELECT 1 FROM events WHERE key=? AND manual=1", (key,)
                ).fetchone():
                    raise ValueError("수정할 수 없는 일정입니다.")
                self.db.execute(
                    "UPDATE events SET title=?,type_id=?,due_at=?,course_id=?,note=?,completed=?,updated_at=? WHERE key=?",
                    (title, type_id, due_at, course_id, note, int(completed), now, key),
                )
            else:
                key = "manual:" + uuid4().hex
                self.db.execute(
                    "INSERT INTO events(key,course_id,kind,title,due_at,completed,note,active,updated_at,manual,type_id) VALUES(?,?,'manual',?,?,?,?,1,?,1,?)",
                    (key, course_id, title, due_at, int(completed), note, now, type_id),
                )
        return key

    def create_manual_events(self, values, repeat="none", count=1):
        from .models import parse_datetime
        from datetime import timedelta
        from calendar import monthrange
        from uuid import uuid4

        repeat = str(repeat)
        if repeat not in ("none", "daily", "weekly", "monthly"):
            raise ValueError("반복 주기를 확인하세요.")
        count = 1 if repeat == "none" else int(count)
        if not 1 <= count <= 52:
            raise ValueError("반복은 52회까지 만들 수 있습니다.")
        base = parse_datetime(values.get("due_at"))
        if repeat != "none" and base is None:
            raise ValueError("반복 일정에는 기한이 필요합니다.")
        with self.db:
            key = self.save_manual_event(**values, _commit=False)
            keys = [key]
            if count == 1:
                return keys
            row = dict(
                self.db.execute("SELECT * FROM events WHERE key=?", (key,)).fetchone()
            )
            series = uuid4().hex
            self.db.execute("UPDATE events SET series_id=? WHERE key=?", (series, key))
            for index in range(1, count):
                if repeat == "monthly":
                    month = base.year * 12 + base.month - 1 + index
                    year, zero = divmod(month, 12)
                    due = base.replace(
                        year=year,
                        month=zero + 1,
                        day=min(base.day, monthrange(year, zero + 1)[1]),
                    )
                else:
                    due = base + timedelta(
                        days=index * (7 if repeat == "weekly" else 1)
                    )
                next_key = "manual:" + uuid4().hex
                keys.append(next_key)
                self.db.execute(
                    "INSERT INTO events(key,course_id,kind,title,due_at,completed,note,active,updated_at,manual,type_id,series_id) VALUES(?,?,'manual',?,?,?,?,1,?,1,?,?)",
                    (
                        next_key,
                        row["course_id"],
                        row["title"],
                        due.isoformat(),
                        row["completed"],
                        row["note"],
                        row["updated_at"],
                        row["type_id"],
                        series,
                    ),
                )
        return keys

    def manual_keys(self, key, whole_series=False):
        row = self.db.execute(
            "SELECT series_id FROM events WHERE key=? AND manual=1", (key,)
        ).fetchone()
        if not row:
            return []
        if whole_series and row["series_id"]:
            return [
                r["key"]
                for r in self.db.execute(
                    "SELECT key FROM events WHERE series_id=? AND manual=1",
                    (row["series_id"],),
                )
            ]
        return [key]

    def manual_snapshot(self, keys):
        import zlib, json

        rows = [
            dict(row)
            for key in keys
            for row in self.db.execute(
                "SELECT * FROM events WHERE key=? AND manual=1", (key,)
            )
        ]
        type_ids = {row["type_id"] for row in rows}
        types = [
            dict(row)
            for row in self.db.execute("SELECT * FROM event_types")
            if row["id"] in type_ids
        ]
        return zlib.compress(
            json.dumps({"rows": rows, "types": types}, ensure_ascii=False).encode(
                "utf-8"
            )
        )

    def restore_manual_snapshot(self, data, clear_keys=()):
        import zlib, json

        value = json.loads(zlib.decompress(data))
        mapping = {}
        with self.db:
            for row in value["types"]:
                existing = self.db.execute(
                    "SELECT id FROM event_types WHERE id=?", (row["id"],)
                ).fetchone()
                if existing:
                    mapping[row["id"]] = row["id"]
                    continue
                named = self.db.execute(
                    "SELECT id FROM event_types WHERE name=?", (row["name"],)
                ).fetchone()
                if named:
                    mapping[row["id"]] = named["id"]
                else:
                    mapping[row["id"]] = self.db.execute(
                        "INSERT INTO event_types(name,color) VALUES(?,?)",
                        (row["name"], row["color"]),
                    ).lastrowid
            for key in clear_keys:
                self.db.execute(
                    "UPDATE events SET active=0 WHERE key=? AND manual=1", (key,)
                )
            columns = (
                "key",
                "course_id",
                "kind",
                "title",
                "due_at",
                "completed",
                "url",
                "week",
                "starred",
                "note",
                "active",
                "updated_at",
                "manual",
                "type_id",
                "series_id",
            )
            for row in value["rows"]:
                row["type_id"] = mapping.get(row["type_id"], row["type_id"])
                self.db.execute(
                    "INSERT OR REPLACE INTO events("
                    + ",".join(columns)
                    + ") VALUES("
                    + ",".join("?" for _ in columns)
                    + ")",
                    tuple(row[c] for c in columns),
                )

    def complete_manual_event(self, key, completed):
        with self.db:
            self.db.execute(
                "UPDATE events SET completed=?,updated_at=? WHERE key=? AND manual=1",
                (int(completed), datetime.now(timezone.utc).isoformat(), key),
            )

    def remove_manual_event(self, key, whole_series=False):
        keys = self.manual_keys(key, whole_series)
        with self.db:
            for value in keys:
                self.db.execute(
                    "UPDATE events SET active=0,updated_at=? WHERE key=? AND manual=1",
                    (datetime.now(timezone.utc).isoformat(), value),
                )

    def all_course_details(self) -> list[dict]:
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT id,name,alias FROM courses ORDER BY COALESCE(NULLIF(alias,''),name)"
            )
        ]

    def set_alias(self, course_id: int, alias: str):
        with self.db:
            self.db.execute(
                "UPDATE courses SET alias=? WHERE id=?", (alias.strip()[:80], course_id)
            )

    def timetable_config(self):
        from .timetable_terms import config

        return config(self)

    def timetable(self, *, all_terms=False) -> list[dict]:
        return [
            dict(r)
            for r in self.db.execute(
                "SELECT * FROM timetable"
                + ("" if all_terms else " WHERE semester=?")
                + " ORDER BY day,start_time,course_id,id",
                () if all_terms else (self.timetable_config()["main"],),
            )
        ]

    def add_timetable(
        self,
        course_id: int,
        day: int,
        start: str,
        end: str,
        professor: str = "",
        room: str = "",
        item_id: int | None = None,
        *,
        color="",
        title="",
        is_online=False,
        semester=None,
        _commit=True,
    ):
        from .schedule_colors import normalize_color

        color = normalize_color(color)
        semester = semester or self.timetable_config()["main"]
        if not isinstance(semester, str) or semester not in {
            t["name"] for t in self.timetable_config()["terms"]
        }:
            raise ValueError("학기를 선택하세요.")
        if (
            type(course_id) is not int
            or course_id < 0
            or type(is_online) not in (bool, int)
            or is_online not in (0, 1)
        ):
            raise ValueError("수업을 확인하세요.")
        if (
            not isinstance(title, str)
            or len(title) > 120
            or (course_id == 0 and not title.strip())
        ):
            raise ValueError("수업명을 입력하세요.")
        if (
            not isinstance(professor, str)
            or len(professor) > 120
            or not isinstance(room, str)
            or len(room) > 100
        ):
            raise ValueError("교수명이나 강의실을 확인하세요.")
        if item_id is not None and (
            type(item_id) is not int
            or not self.db.execute(
                "SELECT 1 FROM timetable WHERE id=? AND semester=?", (item_id, semester)
            ).fetchone()
        ):
            raise ValueError("수업이 존재하지 않습니다.")
        if is_online:
            day, start, end = 0, "", ""
        else:
            self.validate_timetable(day, start, end, item_id, semester)
        values = (
            course_id,
            day,
            start,
            end,
            professor.strip(),
            room.strip(),
            color,
            title.strip(),
            int(is_online),
            semester,
        )
        with self.db if _commit else nullcontext():
            if item_id:
                self.db.execute(
                    "UPDATE timetable SET course_id=?,day=?,start_time=?,end_time=?,professor=?,room=?,color=?,title=?,is_online=?,semester=? WHERE id=?",
                    values + (item_id,),
                )
                return item_id
            return self.db.execute(
                "INSERT INTO timetable(course_id,day,start_time,end_time,professor,room,color,title,is_online,semester) VALUES (?,?,?,?,?,?,?,?,?,?)",
                values,
            ).lastrowid

    def add_timetable_slots(self, shared, slots, item_id=None):
        if (
            not isinstance(slots, list)
            or not 1 <= len(slots) <= 14
            or any(not isinstance(slot, dict) for slot in slots)
        ):
            raise ValueError("수업 시간은 1~14개로 설정하세요.")
        result = []
        with self.db:
            for index, slot in enumerate(slots):
                result.append(
                    self.add_timetable(
                        shared["course_id"],
                        slot.get("day"),
                        slot.get("start_time"),
                        slot.get("end_time"),
                        shared.get("professor", ""),
                        slot.get("room", ""),
                        item_id if index == 0 else None,
                        color=shared.get("color", ""),
                        title=shared.get("title", ""),
                        semester=shared.get("semester"),
                        _commit=False,
                    )
                )
        return result

    def validate_timetable(self, day, start, end, item_id=None, semester=None):
        from .schedule_colors import minutes

        if (
            type(day) is not int
            or not 0 <= day <= 6
            or not minutes(start) < minutes(end)
        ):
            raise ValueError("시간이나 요일이 올바르지 않습니다.")
        conflict = self.db.execute(
            "SELECT id FROM timetable WHERE is_online=0 AND semester=? AND day=? AND start_time<? AND end_time>? AND id<>? LIMIT 1",
            (
                semester or self.timetable_config()["main"],
                day,
                end,
                start,
                item_id or -1,
            ),
        ).fetchone()
        if conflict:
            raise ValueError("같은 요일에 겹치는 수업이 있습니다.")

    def set_timetable_color(self, item_id, color):
        from .schedule_colors import normalize_color

        with self.db:
            self.db.execute(
                "UPDATE timetable SET color=? WHERE id=?",
                (normalize_color(color), item_id),
            )

    def remove_timetable(self, item_id: int):
        with self.db:
            self.db.execute("DELETE FROM timetable WHERE id=?", (item_id,))

    def get_meta(self, key: str, default="") -> str:
        r = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def set_meta(self, key: str, value: str, *, _commit=True):
        with self.db if _commit else nullcontext():
            self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, value))

    def set_starred(self, key: str, starred: bool):
        with self.db:
            self.db.execute(
                "UPDATE events SET starred=? WHERE key=?", (int(starred), key)
            )

    def set_note(self, key: str, note: str):
        with self.db:
            row = self.db.execute(
                "SELECT manual FROM events WHERE key=?", (key,)
            ).fetchone()
            if row and not row["manual"]:
                self.db.execute(
                    "INSERT INTO event_customizations(event_key,note) VALUES(?,?) ON CONFLICT(event_key) DO UPDATE SET note=excluded.note",
                    (key, note),
                )
            else:
                self.db.execute("UPDATE events SET note=? WHERE key=?", (note, key))

    def recent_changes(self, limit: int = 100) -> list[dict]:
        return [
            dict(x)
            for x in self.db.execute(
                "SELECT * FROM changes ORDER BY id DESC LIMIT ?", (limit,)
            )
        ]

    def apply_batch(
        self,
        courses: list[Course],
        batches: dict[tuple[int, str], list[Event]],
        *,
        _commit=True,
    ) -> dict[str, int]:
        """Replace only fully retrieved course/kind data, preserving local notes and stars."""
        now = datetime.now(timezone.utc).isoformat()
        totals = {"new": 0, "updated": 0, "archived": 0, "unchanged": 0}
        if not batches:
            return totals
        for (cid, kind), entries in batches.items():
            for entry in entries:
                if (
                    not isinstance(entry, Event)
                    or entry.course_id != cid
                    or entry.kind != kind
                ):
                    raise ValueError("일정의 과목 또는 유형이 일치하지 않습니다.")
        with self.db if _commit else nullcontext():
            for course in courses:
                self.db.execute(
                    "INSERT INTO courses(id,name) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name",
                    (course.id, course.name),
                )
            for (cid, kind), entries in batches.items():
                existing = {
                    r["key"]: r
                    for r in self.db.execute(
                        "SELECT * FROM events WHERE course_id=? AND kind=?", (cid, kind)
                    )
                }
                by_url = {}
                for old in existing.values():
                    path = urlsplit(old["url"]).path
                    if path.startswith(f"/courses/{cid}/modules/items/"):
                        by_url.setdefault(path, []).append(old["key"])
                seen = set()
                for e in entries:
                    matches = by_url.get(urlsplit(e.url).path, ())
                    if kind == "movie" and e.key not in existing and len(matches) == 1:
                        e = replace(e, key=matches[0])
                    seen.add(e.key)
                    old = existing.get(e.key)
                    if old is not None and not e.completion_verified:
                        e = replace(e, completed=bool(old["completed"]))
                    if old is None:
                        ctype = "new"
                        description = f"새 일정: {e.title}"
                    elif (
                        old["due_at"],
                        old["completed"],
                        old["title"],
                        old["active"],
                        old["completion_verified"],
                        old["start_at"],
                        old["lock_at"],
                        old["lms_data"],
                    ) != (
                        e.due_at,
                        int(e.completed),
                        e.title,
                        1,
                        int(e.completion_verified),
                        e.start_at,
                        e.lock_at,
                        json.dumps(e.lms_data, ensure_ascii=False, sort_keys=True),
                    ):
                        ctype = "updated"
                        description = f"일정 변경: {e.title}"
                    else:
                        ctype = "unchanged"
                        description = ""
                    totals[ctype] += 1
                    if (
                        ctype == "unchanged"
                        and old["url"] == e.url
                        and old["week"] == e.week
                    ):
                        continue
                    self.db.execute(
                        """INSERT INTO events(key,course_id,kind,title,due_at,completed,url,week,active,updated_at,completion_verified,start_at,lock_at,lms_data)
                         VALUES(?,?,?,?,?,?,?,?,1,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET
                         course_id=excluded.course_id,kind=excluded.kind,title=excluded.title,due_at=excluded.due_at,
                         completed=excluded.completed,url=excluded.url,week=excluded.week,active=1,updated_at=excluded.updated_at,completion_verified=excluded.completion_verified,start_at=excluded.start_at,lock_at=excluded.lock_at,lms_data=excluded.lms_data""",
                        (
                            e.key,
                            e.course_id,
                            e.kind,
                            e.title,
                            e.due_at,
                            int(e.completed),
                            e.url,
                            e.week,
                            now,
                            int(e.completion_verified),
                            e.start_at,
                            e.lock_at,
                            json.dumps(e.lms_data, ensure_ascii=False, sort_keys=True),
                        ),
                    )
                    if description:
                        self.db.execute(
                            "INSERT INTO changes(event_key,change_type,detail,changed_at) VALUES (?,?,?,?)",
                            (e.key, ctype, description, now),
                        )
                for key, old in existing.items():
                    if (
                        key not in seen
                        and old["active"]
                        and getattr(entries, "complete", True)
                    ):
                        totals["archived"] += 1
                        self.db.execute(
                            "UPDATE events SET active=0 WHERE key=?", (key,)
                        )
                        self.db.execute(
                            "INSERT INTO changes(event_key,change_type,detail,changed_at) VALUES (?,?,?,?)",
                            (key, "archived", f'목록에서 사라짐: {old["title"]}', now),
                        )
            self.db.execute(
                "INSERT OR REPLACE INTO meta VALUES (?,?)", ("last_sync", now)
            )
        return totals
