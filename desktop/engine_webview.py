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
    def __init__(self, payload, cancelled):
        super().__init__([], cancelled)
        self.payload = payload
        self.dom_snapshot = payload

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
        validated = []
        for row in payload["results"]:
            if not isinstance(row, dict):
                raise ValueError("수집 결과 형식을 확인하지 못했습니다.")
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
        payload = dict(payload, results=validated)
        client = BrowserClient(payload, self.cancel_event)
        batches, warnings = {}, []
        try:
            for course in courses:
                self.progress.emit(f"{course.name} / 수집 결과 저장 중")
                part, notes = client._fetch_course(course, self.progress.emit)
                batches.update(part)
                warnings.extend(notes)
            return owner, courses, batches, warnings, False, client.course_checks
        finally:
            client.session.close()
