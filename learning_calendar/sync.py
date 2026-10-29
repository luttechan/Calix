from __future__ import annotations
import requests
import threading
from queue import Queue,Empty
from urllib.parse import urljoin, urlparse
from .models import Course, Event
from .parsers import course_list, parse_movies, parse_assignments, BASE_URL,safe_url
from .cookies import applies_to_canvas


class AuthenticationRequired(RuntimeError):
    pass

class LearningXAuthenticationRequired(AuthenticationRequired):
    pass

class LearningXTokenMissing(LearningXAuthenticationRequired):
    pass


class SyncCancelled(RuntimeError):
    """Raised when the user requests application shutdown during synchronization."""
    pass


class CampusClient:
    """Fetch only when explicitly invoked; never schedules background requests."""
    def __init__(self, cookies: list[dict], cancel_event: threading.Event | None = None):
        self.cancel_event = cancel_event or threading.Event()
        self.movie_auth_required=False
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 Calix/0.1',
            'Referer': BASE_URL + '/',
        })
        # LearningX uses BOTH the campus session cookies and a Bearer token.
        # The browser HAR confirms: Authorization == 'Bearer ' + xn_api_token.
        # Keep the token in memory only and NEVER print it in an error message.
        self._learningx_token: str | None = None
        selected={}
        for ck in cookies:
            # Cookies are collected from the explicitly opened university login browser.
            domain = str(ck.get('domain','')).lstrip('.').lower()
            if not applies_to_canvas(domain):
                continue
            key=(str(ck.get('name','')),str(ck.get('path','/')))
            old=selected.get(key)
            if old is None or domain=='canvas.bufs.ac.kr':selected[key]=ck
        for ck in selected.values():
            name = str(ck.get('name',''))
            value = str(ck.get('value',''))
            if name == 'xn_api_token' and value:
                self._learningx_token = value
            self.session.cookies.set(name,value,
                                     domain='canvas.bufs.ac.kr',path=str(ck.get('path','/')),
                                     secure=bool(ck.get('secure',True)))

    def _check_cancel(self):
        if self.cancel_event.is_set():
            raise SyncCancelled('동기화를 취소했습니다.')

    def _get(self, path: str, params: dict | None = None):
        self._check_cancel()
        url = safe_url(path)
        if not url:raise ValueError('허용되지 않은 학교 연결 주소입니다.')
        endpoint = urlparse(url).path  # Path only; no credentials or query strings.
        is_learningx = endpoint.startswith('/learningx/api/')
        headers = None
        if is_learningx:
            if not self._learningx_token:
                raise LearningXTokenMissing(
                    'LearningX 인증 토큰(xn_api_token)이 없습니다. '
                    '주차학습 연결을 자동으로 준비하고 있습니다.'
                )
            headers = {'Authorization': 'Bearer ' + self._learningx_token}
        resp = self.session.get(url, params=params, timeout=(5, 12),
                                allow_redirects=False, headers=headers)
        self._check_cancel()
        if is_learningx:
            for cookie in resp.cookies if hasattr(resp,'cookies') else ():
                if cookie.name=='xn_api_token' and cookie.value and applies_to_canvas(cookie.domain):
                    self._learningx_token=cookie.value
        if is_learningx and resp.status_code in (401,403):
            raise LearningXAuthenticationRequired(f'LearningX 동영상 API 인증 실패 (HTTP {resp.status_code}): {endpoint}')
        if resp.status_code == 401:
            api = 'LearningX 동영상 API' if is_learningx else 'Canvas 일반 API'
            raise AuthenticationRequired(
                f'{api} 인증 실패 (HTTP {resp.status_code})\n'
                f'요청 경로: {endpoint}\n'
                '로그인 세션이 만료되었거나 접근 권한이 없습니다. '
                '학교 로그인 화면에서 인증 상태를 확인해 주세요.'
            )
        if resp.status_code in (301, 302, 303, 307, 308):
            raise AuthenticationRequired(
                f'인증 리다이렉트 감지 (HTTP {resp.status_code}): {endpoint}\n'
                'Canvas 로그인 상태를 확인해 주세요.'
            )
        resp.raise_for_status()
        if 'json' not in resp.headers.get('content-type','').lower():
            raise AuthenticationRequired(f'JSON이 아닌 응답: {endpoint}. 로그인 상태를 확인해 주세요.')
        return resp

    def _paginated(self, path: str, params: dict | None = None, *, collection=None) -> list:
        result: list = []
        current_url = path
        current_params = params
        visited=set()
        for _ in range(1000):
            self._check_cancel()
            resp = self._get(current_url, current_params)
            obj = resp.json()
            if collection and isinstance(obj,dict):obj=obj.get(collection)
            if not isinstance(obj,list):
                raise ValueError(f'예상하지 못한 JSON 응답: {path}')
            result.extend(obj)
            if len(result)>100000:raise RuntimeError('조회 항목이 너무 많습니다. 기존 일정을 유지합니다.')
            # requests parses Link rel=next from Canvas automatically.
            link = getattr(resp,'links',{}).get('next',{}).get('url')
            if not link:
                return result
            link = urljoin(urljoin(BASE_URL,current_url), link)
            parsed = urlparse(link)
            if not safe_url(link) or parsed.path != urlparse(path).path:
                raise RuntimeError('신뢰할 수 없는 다음 페이지 URL이 반환되었습니다.')
            if link in visited:raise RuntimeError('다음 페이지가 반복됩니다. 기존 일정을 유지합니다.')
            visited.add(link)
            current_url = link
            current_params = None
        raise RuntimeError('페이지 수가 너무 많습니다. 기존 일정을 유지합니다.')

    def _list_courses(self):
        return course_list(self._paginated('/api/v1/courses',{
            'enrollment_type':'student','enrollment_state':'active','per_page':100}))

    def fetch(self, progress=None) -> tuple[list[Course],dict[tuple[int,str],list[Event]],list[str]]:
        say = progress or (lambda *_:None)
        self._check_cancel()
        say('전체 수강 과목 조회 중…')
        courses = self._list_courses()
        if not courses:
            raise RuntimeError('수강 중인 과목을 찾지 못했습니다.')
        batches: dict[tuple[int,str],list[Event]] = {}
        warnings: list[str] = []
        if len(courses)==1:
            batches,warnings=self._fetch_course(courses[0],say)
        else:
            # Each job owns its Session: no shared cookie jar or connection pool
            # races. At most four university requests run at the same time.
            rows=[dict(name=c.name,value=c.value,domain=c.domain,path=c.path,secure=c.secure)
                  for c in self.session.cookies if applies_to_canvas(c.domain)]
            def collect(course):
                self._check_cancel();client=CampusClient(rows,self.cancel_event)
                try:
                    part,notes=client._fetch_course(course,say)
                    return part,notes,client.movie_auth_required
                finally:client.session.close()
            jobs=Queue();results=Queue();stop=threading.Event()
            for course in courses:jobs.put(course)
            def consume():
                while not stop.is_set() and not self.cancel_event.is_set():
                    try:course=jobs.get_nowait()
                    except Empty:return
                    try:results.put((True,collect(course)))
                    except Exception as exc:results.put((False,exc));return
            workers=[threading.Thread(target=consume,name=f'bufs-sync-{i}',daemon=True) for i in range(min(4,len(courses)))]
            for worker in workers:worker.start()
            try:
                for _ in courses:
                    while True:
                        self._check_cancel()
                        try:ok,value=results.get(timeout=.025);break
                        except Empty:continue
                    if not ok:raise value
                    part,notes,needs_auth=value;batches.update(part);warnings.extend(notes);self.movie_auth_required|=needs_auth
            finally:
                stop.set()
                # Normal completion closes every owned Session. Cancellation
                # never joins a blocked daemon request during application exit.
                if not self.cancel_event.is_set():
                    for worker in workers:
                        while worker.is_alive():
                            self._check_cancel();worker.join(.025)
        return courses,batches,warnings

    def _fetch_course(self,course,say):
        batches={};warnings=[];self._check_cancel()
        say(f'{course.name} / 동영상 조회')
        try:
            modules=self._paginated(f'/learningx/api/v1/courses/{course.id}/modules',{'include_detail':'true','per_page':100},collection='modules')
            batches[(course.id,'movie')]=parse_movies(course,modules)
        except LearningXAuthenticationRequired:
            self.movie_auth_required=True;warnings.append(f'{course.name}: 동영상 인증을 자동으로 연결하고 있습니다.')
        except AuthenticationRequired:raise
        except (ValueError,requests.RequestException,RuntimeError) as err:
            warnings.append(f'{course.name}: 동영상 조회 실패 ({str(err)[:110]})')
        self._check_cancel();say(f'{course.name} / 일반 과제 조회')
        try:
            assignments=self._paginated(f'/api/v1/courses/{course.id}/assignments',{
                'exclude_response_fields[]':['description','rubric'],
                'include[]':['submission'],
                'override_assignment_dates':'true','per_page':'100'})
            batches[(course.id,'assignment')]=parse_assignments(course,[{'assignments':assignments}],[])
        except AuthenticationRequired:raise
        except (ValueError,requests.RequestException,RuntimeError) as err:
            warnings.append(f'{course.name}: 일반 과제 조회 실패 ({str(err)[:110]})')
        return batches,warnings
