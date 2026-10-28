"""Network and SQLite writes run outside the GUI thread."""
import logging
import threading
from queue import Queue,Empty
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from .sync import CampusClient, SyncCancelled, AuthenticationRequired
from .storage import Store
from .snapshot import Snapshot

class SyncTask(QThread):
    progress=Signal(str)
    success=Signal(object)
    error=Signal(str)
    authentication_required=Signal(str)
    def __init__(self,cookies,db_path,parent=None):
        super().__init__(parent);self.cookies=cookies;self.db_path=Path(db_path)
        self.cancel_event=threading.Event()

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
                identity=client._get('/api/v1/users/self/profile').json()
                uid=str(int(identity['id']))
                courses,batches,warnings=client.fetch(progress)
                value=(uid,courses,batches,warnings,getattr(client,'movie_auth_required',False))
                result.put((True,value))
            except Exception as exc:result.put((False,exc))
            finally:
                if client:client.session.close()
        threading.Thread(target=fetch,name='calix-network',daemon=True).start()
        while True:
            if cancel.is_set():raise SyncCancelled('취소됨')
            try:ok,value=result.get(timeout=.025)
            except Empty:continue
            if not ok:raise value
            return value

    def run(self):
        store=None
        try:
            uid,courses,batches,warnings,movie_auth_required=self._fetch_network()
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
            # For pre-v0.6 databases, bind once to the first verified identity.
            store.set_meta('canvas_user_id',uid)
            stats=store.apply_batch(courses,batches)
            store.set_meta('sync_partial','1' if warnings else '0')
            snapshot=Snapshot(store.events(),store.courses())
            self.success.emit({'path':str(store.path),'snapshot':snapshot,'stats':stats,
                               'last_sync':store.get_meta('last_sync'),'warnings':warnings,'sessions':store.timetable(),
                               'movie_auth_required':movie_auth_required})
        except SyncCancelled:
            pass
        except AuthenticationRequired as exc:
            self.authentication_required.emit(str(exc))
        except Exception as exc:
            logging.exception('동기화 실패');self.error.emit(str(exc))
        finally:
            self.cookies=[]
            if store:store.close()
