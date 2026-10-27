"""Validated local archives. Credentials, cookies and decrypted secret text are excluded."""
from __future__ import annotations
import json
import re
import sqlite3
import zipfile
from pathlib import Path
from datetime import date
from .models import parse_datetime
from .schedule_colors import normalize_color,minutes

LIMIT=64*1024*1024


def _rows(db,query):return [dict(row) for row in db.execute(query)]


def write_backup(path,store,folder):
    folder=Path(folder)
    schedule=dict(owner=store.get_meta('canvas_user_id'),courses=_rows(store.db,'SELECT id,name,alias FROM courses'),
        types=_rows(store.db,'SELECT id,name,color FROM event_types'),timetable=store.timetable(),customizations=store.local_customizations(),
        events=_rows(store.db,'SELECT key,course_id,title,due_at,completed,note,starred,type_id,series_id FROM events WHERE manual=1 AND active=1'))
    payload=dict(format='Calix personal backup',version=3,schedule=schedule,journals=[],vault=None,holiday_overrides=[],holiday_preferences=dict(catholic=False,klone_birthday=False))
    holiday_path=folder/'holidays.db'
    if holiday_path.is_file():
        db=sqlite3.connect(holiday_path);db.row_factory=sqlite3.Row
        try:
            payload['holiday_overrides']=_rows(db,'SELECT day,name,enabled FROM overrides')
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='settings'").fetchone():
                for key in ('catholic','klone_birthday'):
                    row=db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone();payload['holiday_preferences'][key]=bool(row and row['value']=='1')
        finally:db.close()
    normal=folder/'journals.db'
    if normal.is_file():
        db=sqlite3.connect(normal);db.row_factory=sqlite3.Row
        try:
            has_html='html' in {r['name'] for r in db.execute('PRAGMA table_info(entries)')}
            payload['journals']=_rows(db,'SELECT id,date,title,body'+(',html' if has_html else '')+' FROM entries')
        finally:db.close()
    private=folder/'private-diary.db'
    if private.is_file():
        db=sqlite3.connect(private)
        try:
            header=db.execute('SELECT header FROM vault WHERE id=1').fetchone()
            if header:payload['vault']=dict(header=header[0].hex(),entries=[dict(id=r[0],nonce=r[1].hex(),cipher=r[2].hex()) for r in db.execute('SELECT id,nonce,cipher FROM entries')])
        finally:db.close()
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    if len(raw)>LIMIT:raise ValueError('백업 용량 한도는 64MB입니다.')
    path=Path(path);pending=path.with_name(path.name+'.tmp')
    with zipfile.ZipFile(pending,'w',compression=zipfile.ZIP_DEFLATED) as archive:archive.writestr('calix.json',raw)
    pending.replace(path)


def _string(value,limit,empty=True):
    if not isinstance(value,str) or len(value)>limit or (not empty and not value.strip()):raise ValueError('백업의 텍스트 형식을 확인하세요.')
    return value


def _integer(value,minimum=0,maximum=2**53):
    if type(value) is not int or not minimum<=value<=maximum:raise ValueError('백업의 숫자 형식을 확인하세요.')
    return value


def _list(value,maximum=20000):
    if not isinstance(value,list) or len(value)>maximum or any(not isinstance(r,dict) for r in value):raise ValueError('백업의 항목 형식을 확인하세요.')
    return value


def _id(value):
    if not isinstance(value,str) or re.fullmatch('[0-9a-f]{32}',value) is None:raise ValueError('백업의 일기 번호를 확인하세요.')
    return value


def read_backup(path,owner=''):
    try:
        with zipfile.ZipFile(path) as archive:
            files=archive.infolist()
            if len(files)!=1 or files[0].filename!='calix.json' or files[0].file_size>LIMIT:raise ValueError('Calix 백업 파일이 아닙니다.')
            value=json.loads(archive.read(files[0]))
        if value.get('format')!='Calix personal backup' or value.get('version') not in (1,2,3):raise ValueError('지원하지 않는 백업입니다.')
        schedule=value['schedule'];source_owner=_string(schedule['owner'],100)
        if owner and source_owner and owner!=source_owner:raise ValueError('다른 학교 계정의 일정 백업입니다.')
        courses={}
        for row in _list(schedule['courses'],5000):
            cid=_integer(row['id'],1)
            if cid in courses:raise ValueError('과목 번호가 중복됩니다.')
            courses[cid]=dict(id=cid,name=_string(row['name'],500,False),alias=_string(row['alias'],80))
        types={};names=set()
        for row in _list(schedule['types'],500):
            tid=_integer(row['id'],1);name=_string(row['name'],24,False).strip();color=normalize_color(row['color'])
            if tid in types or name.casefold() in names or name in ('과제','영상') or not color:raise ValueError('일정 유형을 확인하세요.')
            types[tid]=dict(id=tid,name=name,color=color);names.add(name.casefold())
        if not types:raise ValueError('일정 유형이 없습니다.')
        if value['version']>=2 and 'customizations' not in schedule:raise ValueError('개인 편집 자료가 없습니다.')
        if value['version']>=3 and 'holiday_overrides' not in value:raise ValueError('공휴일 설정 자료가 없습니다.')
        if 'holiday_preferences' in value and (not isinstance(value['holiday_preferences'],dict) or type(value['holiday_preferences'].get('catholic')) is not bool):raise ValueError('축일 표시 설정을 확인하세요.')
        if 'klone_birthday' in value.get('holiday_preferences',{}) and type(value['holiday_preferences']['klone_birthday']) is not bool:raise ValueError('특수 일정 설정을 확인하세요.')
        from .holidays import validate_override
        holiday_keys=set()
        for row in _list(value.get('holiday_overrides',[]),10000):
            validate_override(row['day'],row['name'],row['enabled'])
            if row['day'] in holiday_keys:raise ValueError('공휴일 날짜가 중복됩니다.')
            holiday_keys.add(row['day'])
        edited=set()
        for row in _list(schedule.get('customizations',[])):
            key=_string(row['event_key'],160,False)
            if re.fullmatch(r'(assignment|movie):[0-9]+:[0-9]+',key) is None or key in edited:raise ValueError('학교 일정 번호를 확인하세요.')
            edited.add(key)
            if row['title'] is not None:_string(row['title'],200,False)
            if row['type_id'] is not None and row['type_id'] not in types:raise ValueError('일정 유형을 확인하세요.')
            _string(row['note'],20000)
        keys=set()
        for row in _list(schedule['events']):
            key=_string(row['key'],80,False)
            if not key.startswith('manual:') or key in keys:raise ValueError('일정 번호를 확인하세요.')
            keys.add(key);_string(row['title'],200,False);_string(row['note'],20000);_string(row['series_id'],64)
            if row['type_id'] not in types or row['course_id'] not in {0,*courses}:raise ValueError('일정의 과목이나 유형을 확인하세요.')
            for flag in ('completed','starred'):_integer(row[flag],0,1)
            if row['due_at'] is not None and (not isinstance(row['due_at'],str) or parse_datetime(row['due_at']) is None):raise ValueError('기한을 확인하세요.')
        occupied=[]
        for row in _list(schedule['timetable'],1000):
            day=_integer(row['day'],0,6);start=minutes(row['start_time']);end=minutes(row['end_time'])
            if start>=end or row['course_id'] not in courses:raise ValueError('수업 시간을 확인하세요.')
            if any(d==day and start<b and end>a for d,a,b in occupied):raise ValueError('수업 시간이 겹칩니다.')
            occupied.append((day,start,end));normalize_color(row['color']);_string(row['professor'],200);_string(row['room'],200)
        diaries=_list(value['journals']);diary_ids=set()
        for row in diaries:
            key=_id(row['id']);date.fromisoformat(row['date']);_string(row['title'],200);_string(row['body'],200000);_string(row.get('html',''),1000000)
            if key in diary_ids:raise ValueError('일기 번호가 중복됩니다.')
            diary_ids.add(key)
        vault=value['vault']
        if vault is not None:
            header=bytes.fromhex(vault['header'])
            if len(header)>1024:raise ValueError('암호화 저장소 형식을 확인하세요.')
            config=json.loads(header)
            if config['version']!=1 or config['kdf']!='argon2id-64m-3-4':raise ValueError('지원하지 않는 암호화 방식입니다.')
            for key,size in (('salt',16),('nonce',12),('key',48)):
                if len(bytes.fromhex(config[key]))!=size:raise ValueError('암호화 키 형식을 확인하세요.')
            secret_ids=set()
            for row in _list(vault['entries']):
                key=_id(row['id']);nonce=bytes.fromhex(row['nonce']);cipher=bytes.fromhex(row['cipher'])
                if key in secret_ids or len(nonce)!=12 or not 16<len(cipher)<=3000000:raise ValueError('암호화 일기 형식을 확인하세요.')
                secret_ids.add(key)
        return value
    except (KeyError,TypeError,AttributeError,UnicodeError,zipfile.BadZipFile,RecursionError):raise ValueError('백업 파일이 손상되었거나 형식이 다릅니다.') from None


def restore_backup(value,store,folder):
    """Call only with read_backup's validated result and after a recovery backup."""
    schedule=value['schedule'];folder=Path(folder)
    preserved=store.local_customizations() if 'customizations' not in schedule else None
    old_types={row['id']:row for row in store.event_types()} if preserved is not None else {}
    # All SQL is fixed and parameterized. No imported database/schema is executed.
    db=store.db
    db.execute('ATTACH DATABASE ? AS diary_restore',(str(folder/'journals.db'),))
    try:
        db.execute('ATTACH DATABASE ? AS vault_restore',(str(folder/'private-diary.db'),))
        try:
            db.execute('ATTACH DATABASE ? AS holiday_restore',(str(folder/'holidays.db'),))
            try:
                # SQLite's rollback journal coordinates these databases as one
                # transaction. No user-provided SQL/schema enters this connection.
                with db:
                    if 'holiday_preferences' in value:
                        db.execute('CREATE TABLE IF NOT EXISTS holiday_restore.settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
                        for key in ('catholic','klone_birthday'):
                            if key in value['holiday_preferences']:db.execute('INSERT INTO holiday_restore.settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,'1' if value['holiday_preferences'][key] else '0'))
                    if 'holiday_overrides' in value:
                        db.execute('CREATE TABLE IF NOT EXISTS holiday_restore.overrides(day TEXT PRIMARY KEY,name TEXT NOT NULL,enabled INTEGER NOT NULL CHECK(enabled IN (0,1)))')
                        db.execute('DELETE FROM holiday_restore.overrides')
                        db.executemany('INSERT INTO holiday_restore.overrides(day,name,enabled) VALUES(?,?,?)',[tuple(row[key] for key in ('day','name','enabled')) for row in value['holiday_overrides']])
                    db.execute("CREATE TABLE IF NOT EXISTS diary_restore.entries(id TEXT PRIMARY KEY,date TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,html TEXT NOT NULL DEFAULT '')")
                    if 'html' not in {r['name'] for r in db.execute('PRAGMA diary_restore.table_info(entries)')}:
                        db.execute("ALTER TABLE diary_restore.entries ADD COLUMN html TEXT NOT NULL DEFAULT ''")
                    db.execute('CREATE TABLE IF NOT EXISTS vault_restore.vault(id INTEGER PRIMARY KEY CHECK(id=1),header BLOB NOT NULL)')
                    db.execute('CREATE TABLE IF NOT EXISTS vault_restore.entries(id TEXT PRIMARY KEY,nonce BLOB NOT NULL,cipher BLOB NOT NULL)')
                    if schedule['owner'] and not store.get_meta('canvas_user_id'):
                        db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('canvas_user_id',schedule['owner']))
                    db.execute('DELETE FROM events WHERE manual=1');db.execute('DELETE FROM event_types');db.execute('DELETE FROM timetable')
                    for row in schedule['courses']:
                        db.execute('INSERT INTO courses(id,name,alias) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET alias=excluded.alias',(row['id'],row['name'],row['alias']))
                    for row in schedule['types']:db.execute('INSERT INTO event_types(id,name,color) VALUES(?,?,?)',(row['id'],row['name'],row['color']))
                    customizations=schedule.get('customizations',preserved or [])
                    if preserved is not None:
                        mapping={}
                        for tid in {r['type_id'] for r in preserved if r['type_id'] is not None}:
                            original=old_types[tid];match=db.execute('SELECT id FROM event_types WHERE name=? COLLATE NOCASE',(original['name'],)).fetchone()
                            mapping[tid]=match['id'] if match else db.execute('INSERT INTO event_types(name,color) VALUES(?,?)',(original['name'],original['color'])).lastrowid
                        customizations=[dict(row,type_id=mapping.get(row['type_id'])) for row in preserved]
                    db.execute('DELETE FROM event_customizations');db.execute("UPDATE events SET note='' WHERE manual=0")
                    db.executemany('INSERT INTO event_customizations(event_key,title,type_id,note) VALUES(?,?,?,?)',[tuple(row[key] for key in ('event_key','title','type_id','note')) for row in customizations])
                    for row in schedule['events']:
                        db.execute("INSERT INTO events(key,course_id,kind,title,due_at,completed,note,starred,active,updated_at,manual,type_id,series_id) VALUES(?,?,'manual',?,?,?,?,?,1,'',1,?,?)",tuple(row[key] for key in ('key','course_id','title','due_at','completed','note','starred','type_id','series_id')))
                    for row in schedule['timetable']:db.execute('INSERT INTO timetable(course_id,day,start_time,end_time,professor,room,color) VALUES(?,?,?,?,?,?,?)',tuple(row[key] for key in ('course_id','day','start_time','end_time','professor','room','color')))
                    db.execute('DELETE FROM diary_restore.entries')
                    db.executemany('INSERT INTO diary_restore.entries(id,date,title,body,html) VALUES(?,?,?,?,?)',[(r['id'],r['date'],r['title'],r['body'],r.get('html','')) for r in value['journals']])
                    db.execute('DELETE FROM vault_restore.entries');db.execute('DELETE FROM vault_restore.vault')
                    if value['vault']:
                        db.execute('INSERT INTO vault_restore.vault VALUES(1,?)',(bytes.fromhex(value['vault']['header']),))
                        db.executemany('INSERT INTO vault_restore.entries VALUES(?,?,?)',[(r['id'],bytes.fromhex(r['nonce']),bytes.fromhex(r['cipher'])) for r in value['vault']['entries']])
            finally:db.execute('DETACH DATABASE holiday_restore')
        finally:db.execute('DETACH DATABASE vault_restore')
    finally:db.execute('DETACH DATABASE diary_restore')
