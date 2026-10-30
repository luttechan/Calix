import type {EventItem} from './types';
export const weekdays=['월','화','수','목','금','토','일'];
export function dateKey(value:Date|string=new Date()):string{return new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));}
export function monthGrid(month:string):string[]{const [year,m]=month.split('-').map(Number);const first=new Date(Date.UTC(year,m-1,1));first.setUTCDate(first.getUTCDate()-(first.getUTCDay()+6)%7);return Array.from({length:42},(_,i)=>{const d=new Date(first);d.setUTCDate(d.getUTCDate()+i);return d.toISOString().slice(0,10);});}
export function shiftMonth(month:string,step:number){const [y,m]=month.split('-').map(Number);return new Date(Date.UTC(y,m-1+step,1)).toISOString().slice(0,7);}
export function localInput(value:string|null){return value?new Date(new Date(value).getTime()+9*3600000).toISOString().slice(0,16):'';}
export function dueText(value:string|null){return value?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value)):'기한 없음';}
export function status(event:EventItem,now=Date.now()):string{
 if(!event.completion_verified&&!event.manual)return event.kind==='movie'?'시청 미확인':'제출 미확인';
 if(event.completed)return event.kind==='movie'?'시청 완료':'완료';if(!event.due_at)return '기한 없음';
 const diff=new Date(event.due_at).getTime()-now;if(diff<=0)return event.kind==='assignment'?'미완료':'기한 경과';
 if(diff<3600000)return `${Math.max(1,Math.ceil(diff/60000))}분 전`;if(diff<86400000)return `${Math.ceil(diff/3600000)}시간 전`;return `${Math.max(1,Math.floor(diff/86400000))}일 전`;
}
export function remaining(events:EventItem[],now=Date.now()){return events.filter(e=>!e.completed&&(!e.due_at||new Date(e.due_at).getTime()>now));}
