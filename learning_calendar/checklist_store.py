"""Personal checklist data; school events remain read-only references."""
import json
import sqlite3
from uuid import uuid4
from .models import parse_datetime
from .schedule_colors import normalize_color

DEFAULT_STATUSES=[(1,'계획','#7C879B','open'),(2,'진행중','#459CD4','open'),(3,'검토중','#CA9A46','open'),(4,'완료','#3AA68E','done'),(5,'취소','#CF779A','cancel')]
SCHEMA='''
CREATE TABLE IF NOT EXISTS checklist_sections(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS checklist_statuses(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE COLLATE NOCASE,color TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('open','done','cancel')));
CREATE TABLE IF NOT EXISTS checklist_tasks(id TEXT PRIMARY KEY,section_id INTEGER NOT NULL REFERENCES checklist_sections(id),source_key TEXT UNIQUE,title TEXT,due_at TEXT,category TEXT,role TEXT NOT NULL DEFAULT '',professor TEXT,status_id INTEGER REFERENCES checklist_statuses(id),note TEXT NOT NULL DEFAULT '',trashed INTEGER NOT NULL DEFAULT 0 CHECK(trashed IN (0,1)),previous_status INTEGER);
CREATE INDEX IF NOT EXISTS checklist_section_rows ON checklist_tasks(section_id,trashed);
'''

def initialize(db):
    db.executescript(SCHEMA)
    if not db.execute('SELECT 1 FROM checklist_sections LIMIT 1').fetchone():db.execute("INSERT INTO checklist_sections VALUES(1,'수업')")
    if not db.execute('SELECT 1 FROM checklist_statuses LIMIT 1').fetchone():db.executemany('INSERT INTO checklist_statuses VALUES(?,?,?,?)',DEFAULT_STATUSES)


def checked_text(value,limit,required=False):
    if not isinstance(value,str) or len(value)>limit or '\x00' in value or (required and not value.strip()):raise ValueError('입력 내용을 확인하세요.')
    return value.strip() if required else value


class ChecklistStore:
    def __init__(self,store):self.store=store;self.db=store.db
    def sections(self):return [dict(r) for r in self.db.execute('SELECT * FROM checklist_sections ORDER BY id')]
    def statuses(self):return [dict(r) for r in self.db.execute('SELECT * FROM checklist_statuses ORDER BY id')]
    def save_section(self,name,item_id=None):
        name=checked_text(name,32,True)
        if item_id is None and len(self.sections())>=5:raise ValueError('섹션은 최대 5개입니다.')
        try:
            with self.db:
                if item_id is None:return self.db.execute('INSERT INTO checklist_sections(name) VALUES(?)',(name,)).lastrowid
                if not self.db.execute('UPDATE checklist_sections SET name=? WHERE id=?',(name,item_id)).rowcount:raise ValueError('섹션을 찾지 못했습니다.')
                return item_id
        except sqlite3.IntegrityError:raise ValueError('같은 이름의 섹션이 있습니다.') from None
    def delete_section(self,item_id):
        if item_id==1:raise ValueError('수업 섹션은 삭제할 수 없습니다.')
        with self.db:
            self.db.execute('UPDATE checklist_tasks SET section_id=1,trashed=1 WHERE section_id=?',(item_id,))
            self.db.execute('DELETE FROM checklist_sections WHERE id=?',(item_id,))
    def save_status(self,name,color,kind='open',item_id=None):
        name=checked_text(name,24,True);color=normalize_color(color)
        if not color or kind not in ('open','done','cancel'):raise ValueError('상태의 색상과 유형을 확인하세요.')
        if item_id is None and len(self.statuses())>=50:raise ValueError('상태는 최대 50개입니다.')
        if item_id==1 and kind!='open' or item_id==4 and kind!='done' or item_id==5 and kind!='cancel':raise ValueError('계획 / 완료 / 취소의 상태 유형은 유지해야 합니다.')
        try:
            with self.db:
                if item_id is None:return self.db.execute('INSERT INTO checklist_statuses(name,color,kind) VALUES(?,?,?)',(name,color,kind)).lastrowid
                if not self.db.execute('UPDATE checklist_statuses SET name=?,color=?,kind=? WHERE id=?',(name,color,kind,item_id)).rowcount:raise ValueError('상태를 찾지 못했습니다.')
                return item_id
        except sqlite3.IntegrityError:raise ValueError('같은 이름의 상태가 있습니다.') from None
    def delete_status(self,item_id):
        if item_id<=5:raise ValueError('기본 상태는 이름과 색상을 변경할 수 있습니다.')
        with self.db:
            self.db.execute('UPDATE checklist_tasks SET status_id=1 WHERE status_id=?',(item_id,))
            self.db.execute('UPDATE checklist_tasks SET previous_status=NULL WHERE previous_status=?',(item_id,))
            self.db.execute('DELETE FROM checklist_statuses WHERE id=?',(item_id,))
    def included(self):
        try:value=json.loads(self.store.get_meta('checklist_sources','[]'))
        except ValueError:return set()
        return set(value)&{'assignment','movie'} if isinstance(value,list) and all(isinstance(x,str) for x in value) else set()
    def set_included(self,kinds):self.store.set_meta('checklist_sources',json.dumps(sorted(set(kinds)&{'assignment','movie'})))
    def freeze_imports(self,events):
        kinds=self.included()
        if not kinds:return
        with self.db:
            for event in events:
                if not event.manual and event.kind in kinds:
                    self.db.execute('INSERT OR IGNORE INTO checklist_tasks(id,section_id,source_key,note) VALUES(?,1,?,?)',('event:'+event.key,event.key,event.note))
            self.db.execute("INSERT OR REPLACE INTO meta VALUES('checklist_sources','[]')")
    def import_events(self,events):
        count=0
        with self.db:
            for event in events:
                if event.manual or event.kind not in ('assignment','movie'):continue
                key='event:'+event.key;existing=self.db.execute('SELECT trashed FROM checklist_tasks WHERE id=?',(key,)).fetchone()
                if existing is None:
                    self.db.execute('INSERT INTO checklist_tasks(id,section_id,source_key,note) VALUES(?,1,?,?)',(key,event.key,event.note));count+=1
                elif existing['trashed']:
                    self.db.execute('UPDATE checklist_tasks SET trashed=0 WHERE id=?',(key,));count+=1
        return count
    def contains(self,event):
        row=self.db.execute('SELECT trashed FROM checklist_tasks WHERE source_key=?',(event.key,)).fetchone()
        return row is not None and not row['trashed']
    def rows(self,section_id,events=(),sessions=(),trash=False):
        records={r['id']:dict(r) for r in self.db.execute('SELECT * FROM checklist_tasks WHERE section_id=?',(section_id,))}
        states={s['id']:s for s in self.statuses()};result=[];professors={}
        for session in sessions:
            value=session.get('professor','').strip()
            if value:professors.setdefault(session['course_id'],set()).add(value)
        if section_id==1:
            kinds=self.included()
            for e in events:
                key='event:'+e.key;record=records.get(key,{})
                if e.manual or e.kind not in kinds and not record and not trash:continue
                if bool(record.get('trashed',0))!=trash:continue
                row=dict(id=key,section_id=1,source_key=e.key,title=e.title,due_at=e.due_at,category=e.course_name,role='',professor=' / '.join(sorted(professors.get(e.course_id,()))),status_id=4 if e.completed else 1,note=e.note,url=e.url,source_kind=e.kind,school_completed=e.completed)
                row.update({k:v for k,v in record.items() if v is not None});result.append(row)
        for r in records.values():
            if not r['source_key'] and bool(r['trashed'])==trash:result.append({**r,'url':'','source_kind':'manual'})
        for row in result:
            state=states.get(row['status_id'],states[1]);row.update(status_name=state['name'],status_color=state['color'],status_kind=state['kind'])
        return result
    def save(self,row,field,value):
        limits={'title':200,'category':100,'role':100,'professor':120,'note':20000}
        if field in limits:value=checked_text(value,limits[field],field=='title')
        elif field=='due_at':
            if value is not None and (not isinstance(value,str) or len(value)>50 or value and parse_datetime(value) is None):raise ValueError('기한을 확인하세요.')
        elif field=='status_id':
            if type(value) is not int or not any(s['id']==value for s in self.statuses()):raise ValueError('상태를 선택하세요.')
        else:raise ValueError('편집할 수 없는 항목입니다.')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO checklist_tasks(id,section_id,source_key,note) VALUES(?,?,?,?)',(row['id'],row['section_id'],row.get('source_key'),row.get('note','')))
            self.db.execute(f'UPDATE checklist_tasks SET {field}=? WHERE id=?',(value,row['id']))
    def add(self,section_id,title='새 할 일'):
        if type(section_id) is not int or not any(s['id']==section_id for s in self.sections()):raise ValueError('섹션을 선택하세요.')
        key=uuid4().hex
        with self.db:self.db.execute('INSERT INTO checklist_tasks(id,section_id,title,category,professor,status_id) VALUES(?,?,?,?,?,1)',(key,section_id,checked_text(title,200,True),'',''))
        return key
    def toggle(self,row,checked):
        if checked==(row['status_kind']=='done'):return
        status=4 if checked else row.get('previous_status') or 1
        previous=row['status_id'] if checked else row.get('previous_status')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO checklist_tasks(id,section_id,source_key,note) VALUES(?,?,?,?)',(row['id'],row['section_id'],row.get('source_key'),row.get('note','')))
            self.db.execute('UPDATE checklist_tasks SET status_id=?,previous_status=? WHERE id=?',(status,previous,row['id']))
    def trash(self,rows,trashed=True):
        with self.db:
            for row in rows:
                self.db.execute('INSERT OR IGNORE INTO checklist_tasks(id,section_id,source_key,note) VALUES(?,?,?,?)',(row['id'],row['section_id'],row.get('source_key'),row.get('note','')))
                self.db.execute('UPDATE checklist_tasks SET trashed=? WHERE id=?',(int(trashed),row['id']))


def backup_state(store):
    repo=ChecklistStore(store)
    try:off_days=json.loads(store.get_meta('timetable_off_days','[]'))
    except ValueError:off_days=[]
    return dict(sections=repo.sections(),statuses=repo.statuses(),tasks=[dict(r) for r in store.db.execute('SELECT * FROM checklist_tasks')],sources=sorted(repo.included()),off_days=off_days)


def validate_state(value):
    if not isinstance(value,dict):raise ValueError('체크리스트 백업 형식을 확인하세요.')
    def rows(key,limit):
        result=value.get(key)
        if not isinstance(result,list) or len(result)>limit or any(not isinstance(r,dict) for r in result):raise ValueError('체크리스트 백업 항목을 확인하세요.')
        return result
    def integer(v):
        if type(v) is not int or not 0<v<2**53:raise ValueError('체크리스트 번호를 확인하세요.')
        return v
    sections={};statuses={};tasks={};sources=set();names=set()
    for row in rows('sections',5):
        key=integer(row['id']);name=checked_text(row['name'],32,True)
        if key in sections or name.casefold() in names:raise ValueError('섹션이 중복됩니다.')
        sections[key]=row;names.add(name.casefold())
    names=set()
    for row in rows('statuses',50):
        key=integer(row['id']);name=checked_text(row['name'],24,True)
        if key in statuses or name.casefold() in names or not normalize_color(row['color']) or row['kind'] not in ('open','done','cancel'):raise ValueError('상태를 확인하세요.')
        statuses[key]=row;names.add(name.casefold())
    if 1 not in sections or not all(k in statuses for k in range(1,6)) or statuses[1]['kind']!='open' or statuses[4]['kind']!='done' or statuses[5]['kind']!='cancel':raise ValueError('기본 섹션과 상태가 없습니다.')
    for row in rows('tasks',20000):
        key=checked_text(row['id'],320,True);source=row.get('source_key')
        if key in tasks or integer(row['section_id']) not in sections:raise ValueError('할 일 번호를 확인하세요.')
        if source is not None:
            checked_text(source,300,True)
            if source in sources or key!='event:'+source or row['section_id']!=1:raise ValueError('학교 일정 연결이 올바르지 않습니다.')
            sources.add(source)
        for field,limit in [('title',200),('category',100),('role',100),('professor',120),('note',20000)]:
            if row.get(field) is not None:checked_text(row[field],limit,field=='title')
            elif field in ('role','note'):raise ValueError('할 일 내용을 확인하세요.')
        due=row.get('due_at')
        if due is not None and (not isinstance(due,str) or len(due)>50 or due and parse_datetime(due) is None):raise ValueError('기한을 확인하세요.')
        for field in ('status_id','previous_status'):
            if row.get(field) is not None and integer(row[field]) not in statuses:raise ValueError('할 일의 상태가 없습니다.')
        if type(row.get('trashed')) is not int or row['trashed'] not in (0,1):raise ValueError('휴지통 정보를 확인하세요.')
        tasks[key]=row
    for key,allowed in [('sources',{'assignment','movie'}),('off_days',set(range(7)))]:
        items=value.get(key)
        if not isinstance(items,list) or len(items)>7 or any(type(x) is not (str if key=='sources' else int) or x not in allowed for x in items) or len(set(items))!=len(items):raise ValueError('체크리스트 설정을 확인하세요.')
    return value


def restore_state(db,value):
    for table in ('checklist_tasks','checklist_statuses','checklist_sections'):db.execute('DELETE FROM '+table)
    for key,table,columns in [('sections','checklist_sections',('id','name')),('statuses','checklist_statuses',('id','name','color','kind')),('tasks','checklist_tasks',('id','section_id','source_key','title','due_at','category','role','professor','status_id','note','trashed','previous_status'))]:
        db.executemany(f'INSERT INTO {table}({",".join(columns)}) VALUES({",".join("?" for _ in columns)})',[tuple(r.get(c) for c in columns) for r in value[key]])
    for key,field in [('checklist_sources','sources'),('timetable_off_days','off_days')]:db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',(key,json.dumps(value[field])))
