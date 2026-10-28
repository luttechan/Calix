"""Versioned encrypted diary. Only authenticated ciphertext reaches SQLite.

Argon2id parameters follow RFC 9106's second recommended profile. AES-GCM
wraps a random data key; changing a password never decrypts entries to disk.
"""
from __future__ import annotations
import json
import os
import sqlite3
import struct
from datetime import date
from uuid import uuid4
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

KEY_AAD=b'Calix/private-diary/v1/data-key'
ENTRY_AAD=b'Calix/private-diary/v1/entry/'
PENDING_AAD=b'Calix/private-diary/v1/pending'


class VaultError(ValueError):pass


def wipe(value):
    """Best effort only: Python/Qt and the OS may retain other memory copies."""
    if isinstance(value,bytearray):value[:]=b'\0'*len(value)


def _derive(password,salt):
    if not isinstance(password,str) or len(password)>1024:raise VaultError('암호를 확인하세요.')
    return bytearray(Argon2id(salt=salt,length=32,iterations=3,lanes=4,memory_cost=65536).derive(password.encode('utf-8')))


def wrap_key(password,key):
    if len(password)<12:raise VaultError('암호는 12자 이상으로 정하세요.')
    salt=os.urandom(16);nonce=os.urandom(12);kek=_derive(password,salt)
    try:cipher=AESGCM(bytes(kek)).encrypt(nonce,bytes(key),KEY_AAD)
    finally:wipe(kek)
    return json.dumps(dict(version=1,kdf='argon2id-64m-3-4',salt=salt.hex(),nonce=nonce.hex(),key=cipher.hex()),separators=(',',':')).encode('ascii')


def new_material(password):
    key=bytearray(os.urandom(32))
    try:return key,wrap_key(password,key)
    except Exception:wipe(key);raise


def unlock_material(header,password):
    kek=None
    try:
        if len(header)>1024:raise ValueError()
        value=json.loads(header)
        if value['version']!=1 or value['kdf']!='argon2id-64m-3-4':raise ValueError()
        salt=bytes.fromhex(value['salt']);nonce=bytes.fromhex(value['nonce']);cipher=bytes.fromhex(value['key'])
        if len(salt)!=16 or len(nonce)!=12 or len(cipher)!=48:raise ValueError()
        kek=_derive(password,salt);key=AESGCM(bytes(kek)).decrypt(nonce,cipher,KEY_AAD)
        if len(key)!=32:raise ValueError()
        return bytearray(key)
    except (InvalidTag,ValueError,KeyError,TypeError,UnicodeError):
        raise VaultError('암호가 맞지 않거나 저장소가 손상되었습니다.') from None
    finally:wipe(kek)


def validate_entry(value):
    if not isinstance(value,dict):raise VaultError('일기 형식을 확인하세요.')
    title=value.get('title','');body=value.get('body','');day=value.get('date','')
    if not isinstance(title,str) or len(title)>200 or not isinstance(body,str) or len(body)>200000:raise VaultError('일기가 너무 깁니다.')
    try:date.fromisoformat(day)
    except (ValueError,TypeError):raise VaultError('날짜를 확인하세요.') from None
    result=dict(date=day,title=title,body=body)
    if 'html' in value:
        if not isinstance(value['html'],str) or len(value['html'])>1000000:raise VaultError('일기 서식이 너무 큽니다.')
        result['html']=value['html']
    return result


class Vault:
    def __init__(self,path):
        self.db=sqlite3.connect(path);self.db.execute('PRAGMA secure_delete=ON')
        self.db.executescript('CREATE TABLE IF NOT EXISTS vault(id INTEGER PRIMARY KEY CHECK(id=1),header BLOB NOT NULL);CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY,nonce BLOB NOT NULL,cipher BLOB NOT NULL);')
        self.key=None

    @property
    def initialized(self):return self.db.execute('SELECT 1 FROM vault').fetchone() is not None
    @property
    def unlocked(self):return self.key is not None
    def header(self):
        row=self.db.execute('SELECT header FROM vault WHERE id=1').fetchone()
        if row is None:raise VaultError('먼저 암호를 설정하세요.')
        return row[0]
    def initialize(self,key,header):
        if self.initialized:raise VaultError('이미 설정된 저장소입니다.')
        with self.db:self.db.execute('INSERT INTO vault VALUES(1,?)',(header,))
        self.activate(key)
    def activate(self,key):
        if len(key)!=32:raise VaultError('암호화 키를 확인하세요.')
        self.lock();self.key=bytearray(key)
    def lock(self):wipe(self.key);self.key=None
    def _cipher(self):
        if self.key is None:raise VaultError('비밀 일기가 잠겨 있습니다.')
        return AESGCM(bytes(self.key))
    def seal_pending(self,item_id,value):
        raw=json.dumps(dict(id=item_id,value=value),ensure_ascii=True,separators=(',',':')).encode('ascii')
        packed=struct.pack('>I',len(raw))+raw;packed+=os.urandom((-len(packed))%4096)
        nonce=os.urandom(12)
        return nonce,self._cipher().encrypt(nonce,packed,PENDING_AAD)
    def open_pending(self,pending):
        try:
            plain=self._cipher().decrypt(pending[0],pending[1],PENDING_AAD)
            size=struct.unpack('>I',plain[:4])[0]
            if size>len(plain)-4:raise ValueError()
            value=json.loads(plain[4:4+size])
            if not isinstance(value,dict) or not isinstance(value['value'],dict):raise ValueError()
            return value['id'],value['value']
        except (InvalidTag,ValueError,TypeError,KeyError,UnicodeError,struct.error):
            raise VaultError('임시 내용을 복구하지 못했습니다.') from None
    def save(self,value,item_id=None):
        value=validate_entry(value);cipher=self._cipher();item_id=item_id or uuid4().hex
        if len(item_id)!=32 or any(c not in '0123456789abcdef' for c in item_id):raise VaultError('일기 번호를 확인하세요.')
        raw=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        # Pad to 4 KiB blocks. Dates, titles and exact text lengths stay encrypted.
        packed=struct.pack('>I',len(raw))+raw;packed+=os.urandom((-len(packed))%4096)
        nonce=os.urandom(12);data=cipher.encrypt(nonce,packed,ENTRY_AAD+item_id.encode('ascii'))
        with self.db:self.db.execute('INSERT OR REPLACE INTO entries VALUES(?,?,?)',(item_id,nonce,data))
        return item_id
    def read(self,item_id):
        cipher=self._cipher();row=self.db.execute('SELECT nonce,cipher FROM entries WHERE id=?',(item_id,)).fetchone()
        if row is None:raise VaultError('일기를 찾지 못했습니다.')
        try:
            if len(row[1])>3000000:raise ValueError()
            plain=cipher.decrypt(row[0],row[1],ENTRY_AAD+item_id.encode('ascii'))
            size=struct.unpack('>I',plain[:4])[0]
            if size>len(plain)-4:raise ValueError()
            return validate_entry(json.loads(plain[4:4+size]))
        except (InvalidTag,ValueError,TypeError,UnicodeError,struct.error):raise VaultError('일기 내용을 확인하지 못했습니다. 암호화 데이터가 손상되었을 수 있습니다.') from None
    def summaries(self):
        self._cipher();result=[]
        for (key,) in self.db.execute('SELECT id FROM entries'):
            value=self.read(key);result.append(dict(id=key,date=value['date'],title=value['title']))
        return result
    def remove(self,item_id):
        self._cipher()
        with self.db:self.db.execute('DELETE FROM entries WHERE id=?',(item_id,))
    def replace_header(self,header):
        self._cipher()
        with self.db:self.db.execute('UPDATE vault SET header=? WHERE id=1',(header,))
    def close(self):self.lock();self.db.close()
