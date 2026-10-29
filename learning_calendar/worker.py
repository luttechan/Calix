"""Network and SQLite writes run outside the GUI thread."""
import logging
import threading
import time
from queue import Queue,Empty
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from .sync import CampusClient, SyncCancelled, AuthenticationRequired,sync_summary
from .storage import Store
from .snapshot import Snapshot

class SyncTask(QThread):
    progress=Signal(str)
    success=Signal(object)
    error=Signal(str)
    authentication_required=Signal(str)
    def __init__(self,cookies,db_path,parent=None,*,dom_snapshot=None):
        super().__init__(parent);self.cookies=cookies;self.db_path=Path(db_path)
        self.cancel_event=threading.Event()
        self.dom_snapshot=dom_snapshot

    def cancel(self):self.cancel_event.set()

    def _fetch_network(self):
        # Requests cannot interrupt every blocked socket. Only network work
        # may outlive cancellation; SQLite writes always stay on this QThread.
        result=Queue(maxsize=1);cancel=self.cancel_event;cookies=self.cookies
        def progress(message):
            if not cancel.is_set():self.progress.emit(message)
        def fetch():
            client=None
            try:
                client=CampusClient(cookies,cancel)
                client.dom_snapshot=self.dom_snapshot
                identity=client._get('/api/v1/users/self/profile').json()
                identifier=identity.get('id') if isinstance(identity,dict) else None
                if isinstance(identifier,bool) or not 0<int(identifier)<2**63:raise ValueError('학교 계정 정보가 올바르지 않습니다.')
                uid=str(int(identifier))
                if self.dom_snapshot is not None and str(self.dom_snapshot.get('owner'))!=uid:
                    raise AuthenticationRequired('주차학습 화면의 학교 계정이 일치하지 않습니다.')
                courses,batches,warnings=client.fetch(progress)
                value=(uid,courses,batches,warnings,getattr(client,'movie_auth_required',False),getattr(client,'course_checks',{}))
                result.put((True,value))
            except Exception as exc:result.put((False,exc))
            finally:
                if client:client.session.close()
        network=threading.Thread(target=fetch,name='calix-network',daemon=True);network.start()
        deadline=time.monotonic()+125
        while True:
            if cancel.is_set():raise SyncCancelled('취소됨')
            try:ok,value=result.get(timeout=.025)
            except Empty:
                if not network.is_alive():raise RuntimeError('학교 조회 작업이 중단됐습니다. 기존 일정을 유지합니다.')
                if time.monotonic()>deadline:
                    cancel.set();raise RuntimeError('학교 조회 시간이 초과됐습니다. 기존 일정을 유지합니다.')
                continue
            if not ok:raise value
            return value

    def run(self):
        store=None
        try:
            uid,courses,batches,warnings,movie_auth_required,course_checks=self._fetch_network()
            if self.cancel_event.is_set():raise SyncCancelled('취소됨')
            if not batches:raise RuntimeError('일정을 가져오지 못했습니다. 다시 시도하세요.')
            store=Store(self.db_path)
            owner=store.get_meta('canvas_user_id')
            if owner and owner!=uid:
                # Retain the old account's database; never merge two users.
                store.close();store=None
                path=self.db_path.parent / f'learning-user-{uid}.db'
                original=self.db_path.parent/'learning.db'
                if original.exists():
                    legacy=Store(original)
                    try:
                        if legacy.get_meta('canvas_user_id')==uid:path=original
                    finally:legacy.close()
                store=Store(path)
            if store.get_meta('canvas_user_id') not in ('',uid):raise RuntimeError('계정별 저장 파일이 일치하지 않습니다.')
            # Identity, events, timestamps and diagnostics form one transaction.
            # A failed write or cancellation cannot leave a half-saved sync.
            with store.db:
                if self.cancel_event.is_set():raise SyncCancelled('취소됨')
                store.set_meta('canvas_user_id',uid,_commit=False)
                stats=store.apply_batch(courses,batches,_commit=False)
                store.set_meta('sync_partial','1' if warnings else '0',_commit=False)
                summary=sync_summary(warnings,course_checks);store.set_meta('sync_summary',summary,_commit=False)
                snapshot=Snapshot(store.events(),store.courses())
                if self.cancel_event.is_set():raise SyncCancelled('취소됨')
            self.success.emit({'path':str(store.path),'snapshot':snapshot,'stats':stats,
                               'last_sync':store.get_meta('last_sync'),'warnings':warnings,'sessions':store.timetable(),
                               'movie_auth_required':movie_auth_required,'course_checks':course_checks,'sync_summary':summary})
        except SyncCancelled:
            pass
        except AuthenticationRequired as exc:
            self.authentication_required.emit(str(exc))
        except Exception as exc:
            logging.exception('동기화 실패');self.error.emit(str(exc))
        finally:
            self.cookies=[]
            if store:store.close()
