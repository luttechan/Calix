"""Small offline public holiday table, with durable per-date personal overrides."""
from pathlib import Path
from functools import lru_cache
from datetime import date
import json,sqlite3,sys

SOURCE_URL='https://www.data.go.kr/data/15012690/openapi.do'
SCHEMA='CREATE TABLE IF NOT EXISTS overrides(day TEXT PRIMARY KEY,name TEXT NOT NULL,enabled INTEGER NOT NULL CHECK(enabled IN (0,1)))'

@lru_cache(maxsize=1)
def baseline():
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
    return json.loads((root/'asset/calendar/kr_public_holidays.json').read_text(encoding='utf-8'))

@lru_cache(maxsize=1)
def catholic_baseline():
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
    return json.loads((root/'asset/calendar/catholic_feasts.json').read_text(encoding='utf-8'))

def validate_override(day,name,enabled):
    if not isinstance(day,str) or date.fromisoformat(day).isoformat()!=day:raise ValueError('날짜를 확인하세요.')
    if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('공휴일 이름은 1~80자로 입력하세요.')
    if type(enabled) is not int or enabled not in (0,1):raise ValueError('공휴일 표시 설정을 확인하세요.')
    return day,name.strip(),enabled

class HolidayCalendar:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(self.path,timeout=5);self.db.row_factory=sqlite3.Row
        self.db.execute(SCHEMA);self.db.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)');self.db.commit();self.reload()
    def reload(self):
        self.overrides={row['day']:dict(row) for row in self.db.execute('SELECT day,name,enabled FROM overrides')}
        row=self.db.execute("SELECT value FROM settings WHERE key='catholic'").fetchone();self.catholic_enabled=bool(row and row['value']=='1')
        row=self.db.execute("SELECT value FROM settings WHERE key='klone_birthday'").fetchone();self.birthday_enabled=bool(row and row['value']=='1')
    def set_catholic(self,enabled):
        with self.db:self.db.execute("INSERT INTO settings(key,value) VALUES('catholic',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",('1' if enabled else '0',))
        self.catholic_enabled=bool(enabled)
        if not enabled:catholic_baseline.cache_clear()
    def set_birthday(self,enabled):
        with self.db:self.db.execute("INSERT INTO settings(key,value) VALUES('klone_birthday',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",('1' if enabled else '0',))
        self.birthday_enabled=bool(enabled)
    def feasts(self,year):
        if not self.catholic_enabled:return {}
        return {date.fromisoformat(day):name for day,name in catholic_baseline()['years'].get(str(year),{}).items()}
    def special_dates(self,year):
        values=self.feasts(year)
        if self.birthday_enabled:
            day=date(year,6,27);values[day]=' / '.join(filter(None,('클로네 생일',values.get(day,''))))
        return values
    def defaults(self,year):return baseline()['years'].get(str(year),{})
    def has_year(self,year):return str(year) in baseline()['years']
    def year(self,year):
        values=dict(self.defaults(year))
        for day,row in self.overrides.items():
            if int(day[:4])!=year:continue
            if row['enabled']:values[day]=row['name']
            else:values.pop(day,None)
        return {date.fromisoformat(day):name for day,name in values.items()}
    def entries(self,year):
        defaults=self.defaults(year);keys=set(defaults)|{day for day in self.overrides if int(day[:4])==year};rows=[]
        for day in sorted(keys):
            custom=self.overrides.get(day);rows.append(dict(day=day,name=custom['name'] if custom else defaults[day],source='표시 안 함' if custom and not custom['enabled'] else '직접 설정' if custom else '기본',enabled=custom['enabled'] if custom else 1,custom=custom is not None))
        return rows
    def save(self,day,name,enabled=True):
        values=validate_override(day,name,int(enabled))
        with self.db:self.db.execute('INSERT INTO overrides(day,name,enabled) VALUES(?,?,?) ON CONFLICT(day) DO UPDATE SET name=excluded.name,enabled=excluded.enabled',values)
        self.reload()
    def reset(self,day):
        date.fromisoformat(day)
        with self.db:self.db.execute('DELETE FROM overrides WHERE day=?',(day,))
        self.reload()
    def close(self):self.db.close()
