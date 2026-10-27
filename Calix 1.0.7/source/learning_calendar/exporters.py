"""RFC 5545 iCalendar export without external dependencies."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from .models import Event


def _text(value: str) -> str:
    return str(value).replace('\\','\\\\').replace('\r\n','\n').replace('\r','\n').replace('\n','\\n').replace(';','\\;').replace(',','\\,')


def _fold(line: str) -> list[str]:
    """Fold content lines at <= 75 UTF-8 octets per RFC 5545."""
    if not line:
        return ['']
    output=[]
    cur=''
    byte_len=0
    for char in line:
        char_len=len(char.encode('utf-8'))
        if byte_len+char_len>75:
            output.append(cur)
            cur=' '
            byte_len=1
        cur+=char
        byte_len+=char_len
    output.append(cur)
    return output


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def export_ics(events: list[Event], filepath: str | Path, include_completed: bool = True) -> int:
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Calix//KO',
           'CALSCALE:GREGORIAN','METHOD:PUBLISH','X-WR-CALNAME:Calix']
    count=0
    stamp=_utc(datetime.now(timezone.utc))
    for item in events:
        due=item.due
        if due is None or (item.completed and not include_completed):
            continue
        uid=sha256(item.key.encode('utf-8')).hexdigest()[:32]+'@bufs-learningcalendar.local'
        label=item.type_label
        description='\n'.join(filter(None,[f'과목: {item.course_name}',
            f'상태: {"완료" if item.completed else "미완료"}',item.week,item.note]))
        lines.extend(['BEGIN:VEVENT',f'UID:{uid}',f'DTSTAMP:{stamp}',
                      f'DTSTART:{_utc(due)}',f'DTEND:{_utc(due+timedelta(minutes=1))}',
                      f'SUMMARY:{_text(f"[{label}] {item.title}")}',
                      f'DESCRIPTION:{_text(description)}',
                      f'CATEGORIES:{_text(item.type_label if item.manual else "학습 동영상" if item.kind=="movie" else "일반 과제")}'])
        if item.url:
            lines.append('URL:'+item.url)
        lines.append('END:VEVENT')
        count+=1
    lines.append('END:VCALENDAR')
    text='\r\n'.join(part for raw in lines for part in _fold(raw))+'\r\n'
    Path(filepath).write_bytes(text.encode('utf-8'))
    return count
