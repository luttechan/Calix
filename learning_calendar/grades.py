"""Semester-linked, credit-weighted grade calculations."""
from decimal import Decimal, ROUND_HALF_UP
import math
from uuid import uuid4

SCALES = {
    "4.5": {"A+": 4.5, "A": 4.0, "B+": 3.5, "B": 3.0, "C+": 2.5, "C": 2.0, "D+": 1.5, "D": 1.0, "F": 0},
    "4.3": {"A+": 4.3, "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7, "C+": 2.3, "C": 2.0, "C-": 1.7, "D+": 1.3, "D": 1.0, "D-": 0.7, "F": 0},
    "4.0": {"A+": 4.0, "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7, "C+": 2.3, "C": 2.0, "C-": 1.7, "D+": 1.3, "D": 1.0, "D-": 0.7, "F": 0},
}


def initialize(store):
    store.db.executescript("""
    CREATE TABLE IF NOT EXISTS grade_items (
        semester TEXT NOT NULL, id TEXT NOT NULL, title TEXT NOT NULL DEFAULT '',
        credits REAL NOT NULL DEFAULT 0, grade TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL DEFAULT '일반', excluded INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(semester,id));
    CREATE TABLE IF NOT EXISTS grade_scales (
        semester TEXT PRIMARY KEY, scale TEXT NOT NULL DEFAULT '4.5');
    """)


def rows(store, semester):
    saved = {row["id"]: dict(row) for row in store.db.execute(
        "SELECT * FROM grade_items WHERE semester=?", (semester,))}
    sessions = store.timetable(all_terms=True)
    courses = {course.id: course.name for course in store.courses()}
    custom = {}
    for session in sessions:
        if session["semester"] == semester and not session["course_id"]:
            key = session["title"].strip().casefold()
            custom[key] = min(custom.get(key, session["id"]), session["id"])
    linked = {}
    for session in sessions:
        if session["semester"] != semester:
            continue
        course_id = session["course_id"]
        # Course IDs represent one course even when it has multiple time slots.
        identifier = "course:" + str(course_id) if course_id else "session:" + str(custom[session["title"].strip().casefold()])
        linked.setdefault(identifier, session["title"] or courses.get(course_id, "수업"))
    result = []
    for identifier, title in linked.items():
        item = saved.pop(identifier, dict(id=identifier, credits=0, grade="", category="일반", excluded=0))
        result.append(dict(item, title=title, linked=True))
    result.extend(dict(item, linked=False) for item in saved.values())
    return result


def summary(items, scale):
    points = Decimal(0)
    graded = Decimal(0)
    earned = Decimal(0)
    registered = Decimal(0)
    pending = 0
    for item in items:
        if item["excluded"]:
            continue
        credits = Decimal(str(item["credits"]))
        grade = item["grade"]
        registered += credits
        if not grade or grade not in (*SCALES[scale], "P", "NP"):
            pending += 1
            continue
        if grade == "P":
            earned += credits
        elif grade != "NP":
            graded += credits
            points += credits * Decimal(str(SCALES[scale][grade]))
            if grade != "F":
                earned += credits
    gpa = str((points / graded).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)) if graded else None
    return dict(gpa=gpa, graded_credits=float(graded), earned_credits=float(earned),
                registered_credits=float(registered), pending=pending)


def read(store, semester):
    names = [term["name"] for term in store.timetable_config()["terms"]]
    if semester not in names:
        raise ValueError("학기를 선택하세요.")
    row = store.db.execute("SELECT scale FROM grade_scales WHERE semester=?", (semester,)).fetchone()
    scale = row[0] if row else "4.5"
    items = rows(store, semester)
    return dict(semester=semester, scale=scale, grades=[*SCALES[scale], "P", "NP"],
                items=items, summary=summary(items, scale))


def dispatch(store, method, params):
    initialize(store)
    semester = params.get("semester", store.timetable_config()["main"])
    current = read(store, semester)
    if method == "grades.read":
        return current
    if method == "grades.scale":
        scale = params.get("scale")
        if scale not in SCALES:
            raise ValueError("평점 기준을 선택하세요.")
        with store.db:
            store.db.execute("INSERT OR REPLACE INTO grade_scales VALUES(?,?)", (semester, scale))
        return read(store, semester)
    identifier = params.get("id")
    existing = next((row for row in current["items"] if row["id"] == identifier), None)
    if method == "grades.delete":
        if existing is None or existing["linked"]:
            raise ValueError("시간표에 연결된 수업은 계산 제외를 사용하세요.")
        with store.db:
            store.db.execute("DELETE FROM grade_items WHERE semester=? AND id=?", (semester, identifier))
        return True
    if method != "grades.save":
        raise ValueError("지원하지 않는 학점 요청입니다.")
    if identifier is None:
        identifier = "manual:" + uuid4().hex
    elif existing is None:
        raise ValueError("수업을 다시 선택하세요.")
    title = params.get("title", existing["title"] if existing else "")
    credits = params.get("credits", existing["credits"] if existing else 0)
    grade = params.get("grade", existing["grade"] if existing else "")
    category = params.get("category", existing["category"] if existing else "일반")
    excluded = params.get("excluded", bool(existing["excluded"]) if existing else False)
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ValueError("과목명을 입력하세요.")
    if type(credits) not in (int, float) or not math.isfinite(credits) or not 0 <= credits <= 30 or credits * 2 != int(credits * 2):
        raise ValueError("학점은 0~30 사이에서 0.5 단위로 입력하세요.")
    if grade not in ("", "P", "NP", *SCALES[current["scale"]]):
        raise ValueError("현재 기준에 맞는 성적을 선택하세요.")
    if category not in ("전공", "교양", "일반") or type(excluded) is not bool:
        raise ValueError("수업 분류를 확인하세요.")
    with store.db:
        store.db.execute("INSERT OR REPLACE INTO grade_items VALUES(?,?,?,?,?,?,?)",
                         (semester, identifier, title.strip(), credits, grade, category, int(excluded)))
    return identifier
