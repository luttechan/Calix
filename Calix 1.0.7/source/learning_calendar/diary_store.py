"""Ordinary personal diaries, independent of university account changes."""
import sqlite3
from uuid import uuid4


class DiaryStore:
    def __init__(self,path):
        self.db=sqlite3.connect(path);self.db.row_factory=sqlite3.Row
        self.db.execute('CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY,date TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL)');self.db.commit()
        if 'html' not in {r['name'] for r in self.db.execute('PRAGMA table_info(entries)')}:
            self.db.execute("ALTER TABLE entries ADD COLUMN html TEXT NOT NULL DEFAULT ''");self.db.commit()
    def summaries(self):return [dict(row) for row in self.db.execute('SELECT id,date,title FROM entries ORDER BY date DESC,id')]
    def read(self,key):
        row=self.db.execute('SELECT date,title,body,html FROM entries WHERE id=?',(key,)).fetchone()
        if row is None:raise ValueError('일기를 찾지 못했습니다.')
        return dict(row)
    def save(self,value,item_id=None):
        # Kept separate so ordinary diary startup never loads the crypto runtime.
        from datetime import date
        date.fromisoformat(value['date'])
        if len(value['title'])>200 or len(value['body'])>200000 or len(value.get('html',''))>1000000:raise ValueError('일기가 너무 깁니다.')
        key=item_id or uuid4().hex
        with self.db:self.db.execute('INSERT OR REPLACE INTO entries(id,date,title,body,html) VALUES(?,?,?,?,?)',(key,value['date'],value['title'],value['body'],value.get('html','')))
        return key
    def remove(self,key):
        with self.db:self.db.execute('DELETE FROM entries WHERE id=?',(key,))
    def close(self):self.db.close()
