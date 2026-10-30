"""Read the rendered LearningX screen, without issuing video API requests."""
import re
from datetime import datetime
from urllib.parse import urlsplit
from .models import Course,Event,KST
from .parsers import CollectedEvents,safe_url,record_event

SNAPSHOT_SCRIPT=r'''JSON.stringify((()=>{
 const allowed=d=>{try{const u=new URL(d.URL);return u.protocol==='https:'&&u.hostname==='canvas.bufs.ac.kr'&&(!u.port||u.port==='443');}catch(e){return false;}};
 const docs=[];const walk=(d,depth)=>{if(depth>6||!allowed(d))return;docs.push(d);for(const f of d.querySelectorAll('iframe')){try{if(f.contentDocument)walk(f.contentDocument,depth+1);}catch(e){}}};walk(document,0);
 for(const d of docs){
  const root=d.querySelector('#root[data-canvas_course_id]');if(!root)continue;
  const builder=root.querySelector('.xn-module-builder');if(!builder)continue;
  const folded=[...builder.querySelectorAll('.xnmb-module-left-wrapper[aria-expanded="false"]')];
  if(folded.length){for(const b of folded)b.click();return {state:'expanding'};}
  const weeks=[...builder.querySelectorAll('.xnmb-module-title')];
  const expected=builder.querySelectorAll('.xnmb-link-container .xnmb-link').length;
  if(!weeks.length||weeks.length<expected)return {state:'loading'};
  const text=(el,selector)=>{const n=el.querySelector(selector);return n?n.textContent.trim():'';};
  const rows=[];
  for(const meta of builder.querySelectorAll('.xnmb-module_item-meta_data-wrapper')){
   const item=meta.closest('.xnmb-module_item-wrapper');if(!item)continue;
   const icon=item.querySelector('.xnmb-module_item-icon');
   const kind=icon?['movie','mp4','zoom','file','pdf','assignment'].find(k=>icon.classList.contains(k)):null;
   if(!['movie','mp4','zoom'].includes(kind))continue;
   const a=meta.querySelector('a.xnmb-module_item-left-title.link');
   const done=item.querySelector('.xnmb-module_item-completed');
   const attendance=meta.querySelector('.xnmb-module_item-meta_data-attendance_status');
   rows.push({title:a?a.textContent.trim():'',url:a?a.getAttribute('href'):'',kind,
    start:text(meta,'.xnlal-attendance-list-item-meta_data-lecture_periods-unlock_at'),
    due:text(meta,'.xnlal-attendance-list-item-meta_data-lecture_periods-due_at'),
    lock:text(meta,'.xnlal-attendance-list-item-meta_data-lecture_periods-lock_at'),
    week:text(meta,'.xnmb-module_item-meta_data-lesson_periods-week'),
    completed:done?(done.classList.contains('completed')?true:done.classList.contains('incomplete')?false:null):null,
    attendance:attendance?['attendance','late','excused','absent','none'].find(k=>attendance.classList.contains(k))||'':''});
  }
  return {state:'ready',course_id:root.getAttribute('data-canvas_course_id'),owner:root.getAttribute('data-user_id')||'',name:root.getAttribute('data-course_name')||'',term:root.getAttribute('data-term')||'',weeks:weeks.length,expected,items:rows};
 }
 for(const d of docs){for(const a of d.querySelectorAll('a[href]')){if(/주차학습|학습콘텐츠|강의콘텐츠|LearningX/i.test(a.textContent)){const u=new URL(a.getAttribute('href'),d.URL);if(u.protocol==='https:'&&u.hostname==='canvas.bufs.ac.kr'&&(!u.port||u.port==='443')&&/\/external_tools\//.test(u.pathname))return {state:'navigate',url:u.href};}}}
 return {state:'loading'};
})())'''


def screen_date(value,year):
    if value is None or value=='':return None
    if not isinstance(value,str):raise ValueError('날짜 형식 오류')
    value=' '.join(value.replace('\xa0',' ').split())
    match=re.search(r'(?:(\d{4})년\s*)?(\d{1,2})월\s*(\d{1,2})일\s*(오전|오후)?\s*(\d{1,2}):(\d{2})',value)
    if not match:raise ValueError('화면 날짜를 확인하지 못했습니다.')
    y,month,day,period,hour,minute=match.groups();hour=int(hour)
    if period:
        if not 0<=hour<=12:raise ValueError('시간 형식 오류')
        hour=hour%12+(12 if period=='오후' else 0)
    return datetime(int(y or year),int(month),int(day),hour,int(minute),tzinfo=KST).isoformat()


def parse_screen(course,snapshot):
    if not isinstance(snapshot,dict) or snapshot.get('state')!='ready':raise ValueError('주차학습 화면이 준비되지 않았습니다.')
    if str(snapshot.get('course_id'))!=str(course.id):raise ValueError('주차학습 과목이 일치하지 않습니다.')
    term=snapshot.get('term','');year=re.search(r'\b(20\d{2})(?:년|학년도)',term) if isinstance(term,str) else None
    if not year and isinstance(snapshot.get('name'),str):year=re.search(r'\b(20\d{2})\b',snapshot['name'])
    if not year:raise ValueError('강의 연도를 확인하지 못했습니다.')
    items=snapshot.get('items')
    if not isinstance(items,list) or len(items)>10000:raise ValueError('영상 목록 형식이 올바르지 않습니다.')
    weeks=snapshot.get('weeks');expected=snapshot.get('expected')
    if type(weeks) is not int or type(expected) is not int or not 0<weeks<=1000 or not 0<=expected<=weeks:
        raise ValueError('전체 주차학습을 확인하지 못했습니다.')
    events={};blocked=set();complete=True
    for row in items:
        try:
            if not isinstance(row,dict) or row.get('kind') not in ('movie','mp4','zoom'):raise ValueError('영상 형식 오류')
            url=safe_url(row.get('url'));match=re.fullmatch(rf'/courses/{course.id}/modules/items/(\d+)',urlsplit(url).path)
            title=row.get('title');week=row.get('week','')
            if not match or not isinstance(title,str) or not title.strip() or len(title)>1000 or not isinstance(week,str):raise ValueError('영상 정보 오류')
            due=screen_date(row.get('due'),int(year[1]));start=screen_date(row.get('start'),int(year[1]));lock=screen_date(row.get('lock'),int(year[1]))
            done=row.get('completed');attendance=row.get('attendance')
            if done is not True and done is not False:done=True if attendance in ('attendance','late','excused') else False if attendance in ('absent','none') else None
            key=f'movie:{course.id}:{match[1]}'
            event=Event(key,course.id,course.name,'movie',title.strip(),due,done is True,url=url,week=week,completion_verified=done is not None,start_at=start,lock_at=lock)
            if not record_event(events,blocked,event):complete=False
        except (ValueError,TypeError,OverflowError):complete=False
    return CollectedEvents(events.values(),complete=complete)
