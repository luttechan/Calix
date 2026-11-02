"""Parse a browser-authenticated snapshot without moving cookies or making requests."""

import json
from learning_calendar.worker import SyncTask
from learning_calendar.sync import CampusClient
from learning_calendar.parsers import course_list


def identity(value):
    if not isinstance(value, dict):
        raise ValueError("학교 계정 정보를 확인하세요.")
    owner = value.get("owner")
    if (
        not isinstance(owner, str)
        or not owner.isascii()
        or not owner.isdigit()
        or not 0 < int(owner) < 2**63
    ):
        raise ValueError("학교 계정 정보를 확인하세요.")
    courses = course_list(value.get("courses"))
    if not courses or len(courses) != len(value["courses"]) or len(courses) > 1000:
        raise ValueError("전체 수강 과목을 확인하지 못했습니다.")
    return owner, courses


class BrowserClient(CampusClient):
    def __init__(self, payload, cancelled, cached_movies=None):
        super().__init__([], cancelled)
        self.cached_movies = cached_movies or {}
        self.payload = payload
        self.dom_snapshot = payload

    def _course_assignments(self, course):
        events = super()._course_assignments(course)
        response = self.payload.get("responses", {}).get(
            f"/api/v1/courses/{course.id}/assignments", {}
        )
        if response.get("complete") is False:
            from learning_calendar.parsers import CollectedEvents

            return CollectedEvents(events, complete=False)
        return events

    def _snapshot_movies(self, course):
        if course.id in self.cached_movies:
            return self.cached_movies[course.id]
        row = next(
            (
                r
                for r in self.payload.get("results", [])
                if r.get("course_id") == course.id
            ),
            {},
        )
        if "canvas" not in row:
            return super()._snapshot_movies(course)
        from learning_calendar.canvas_modules import parse_canvas_modules
        from learning_calendar.parsers import CollectedEvents

        canvas = parse_canvas_modules(course, row["canvas"])
        videos = []
        complete = canvas.complete and row.get("sources_complete") is True
        if row.get("snapshot") is not None:
            lx = super()._snapshot_movies(course)
            videos.extend(lx)
            complete = complete and lx.complete
        videos.extend(canvas)
        return CollectedEvents(videos, complete=complete)

    def _paginated(self, path, params=None, *, collection=None):
        self._check_cancel()
        response = self.payload.get("responses", {}).get(path)
        if (
            not isinstance(response, dict)
            or "error" in response
            or not isinstance(response.get("data"), list)
        ):
            raise ValueError("과목 응답을 확인하지 못했습니다. 기존 일정을 유지합니다.")
        return response["data"]

    def _get(self, *args, **kwargs):
        raise RuntimeError("브라우저 수집에서 외부 HTTP 요청은 허용되지 않습니다.")


class BrowserSyncTask(SyncTask):
    def __init__(self, payload, path, parent=None):
        super().__init__([], path, parent, dom_snapshot=payload)

    def _fetch_network(self):
        payload = self.dom_snapshot
        owner, courses = identity(payload)
        if (
            payload.get("transport") != "webview2"
            or not isinstance(payload.get("results"), list)
            or not isinstance(payload.get("responses"), dict)
        ):
            raise ValueError("수집 응답을 확인하지 못했습니다.")
        if len(json.dumps(payload, ensure_ascii=False)) > 1800000:
            raise ValueError("수집 응답이 너무 큽니다.")
        from learning_calendar.storage import Store
        from learning_calendar.incremental import fingerprints

        store = Store(self.db_path)
        try:
            cached = (
                fingerprints(store) if store.get_meta("canvas_user_id") == owner else {}
            )
            from dataclasses import replace

            existing = [
                replace(e, title=e.source_title or e.title) for e in store.events()
            ]
        finally:
            store.close()
        cached_movies = {}
        self.video_fingerprints = {}
        validated = []
        for row in payload["results"]:
            if not isinstance(row, dict):
                raise ValueError("수집 결과 형식을 확인하지 못했습니다.")
            course_id = row.get("course_id")
            digest = row.get("fingerprint")
            if row.get("unchanged") is True:
                if (
                    type(course_id) is not int
                    or not isinstance(digest, str)
                    or cached.get(str(course_id)) != digest
                ):
                    raise ValueError(
                        "이전 동기화 기록이 일치하지 않습니다. 다시 동기화하세요."
                    )
                cached_movies[course_id] = [
                    e
                    for e in existing
                    if e.course_id == course_id and e.kind == "movie"
                ]
                self.video_fingerprints[str(course_id)] = digest
                validated.append(row)
                continue
            snapshot = row.get("snapshot")
            if snapshot is not None and (
                row.get("verified") is not True
                or not isinstance(snapshot, dict)
                or str(snapshot.get("owner")) != owner
                or (
                    snapshot.get("items") == []
                    and row.get("empty_confirmed") is not True
                )
            ):
                validated.append(
                    dict(course_id=row.get("course_id"), error="영상 목록 검증 실패")
                )
            else:
                validated.append(row)
                if isinstance(digest, str) and len(digest) == 64:
                    self.video_fingerprints[str(course_id)] = digest
        payload = dict(payload, results=validated)
        client = BrowserClient(payload, self.cancel_event, cached_movies)
        batches, warnings = {}, []
        try:
            for course in courses:
                self.progress.emit(f"{course.name} / 수집 결과 저장 중")
                part, notes = client._fetch_course(course, self.progress.emit)
                batches.update(part)
                warnings.extend(notes)
                row = next(
                    (r for r in payload["results"] if r.get("course_id") == course.id),
                    {},
                )
                for warning in row.get("canvas", {}).get("warnings", []):
                    if isinstance(warning, str):
                        warnings.append(f"{course.name}: {warning[:160]}")
            return owner, courses, batches, warnings, False, client.course_checks
        finally:
            client.session.close()
