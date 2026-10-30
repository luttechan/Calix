import {describe,it,expect} from 'vitest';
import {dateKey,monthGrid,remaining,status} from './dates';
import type {EventItem} from './types';
const event=(values:Partial<EventItem>={}):EventItem=>({key:'a',course_id:1,course_name:'수업',kind:'assignment',title:'과제',due_at:'2026-11-01T23:59:00+09:00',completed:false,url:'',note:'',type_id:null,type_name:'',type_color:'',manual:false,completion_verified:true,week:'',source_title:'',...values});
describe('calendar dates',()=>{
 it('uses Korea dates at the UTC midnight boundary',()=>expect(dateKey('2026-10-30T16:00:00Z')).toBe('2026-10-31'));
 it('keeps Monday-first dates aligned when the month starts on Sunday',()=>{const cells=monthGrid('2026-11');expect(cells).toHaveLength(42);expect(cells[0]).toBe('2026-10-26');expect(cells[6]).toBe('2026-11-01');expect(new Set(cells).size).toBe(42);});
 it('does not include past or completed schedules in remaining counts',()=>{const now=new Date('2026-10-30T12:00:00+09:00').getTime();expect(remaining([event({key:'past',due_at:'2026-10-29T12:00:00+09:00'}),event({key:'done',completed:true}),event({key:'future'}),event({key:'none',due_at:null})],now).map(e=>e.key)).toEqual(['future','none']);});
 it('marks overdue unsubmitted assignments and keeps unverified videos distinct',()=>{const now=new Date('2026-11-02T12:00:00+09:00').getTime();expect(status(event(),now)).toBe('미완료');expect(status(event({kind:'movie',completion_verified:false}),now)).toBe('시청 미확인');expect(status(event({kind:'movie',completed:true}),now)).toBe('시청 완료');});
});
