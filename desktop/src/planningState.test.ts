import {expect,test} from 'vitest';
import {freeSlots,studyPlan,busyDates,sessionLanes} from './planningState';
import type {Session,EventItem} from './types';
const row=(id:number,start_time:string,end_time:string,is_online=0)=>({id,start_time,end_time,is_online,day:0}) as Session;
test('free slots merge overlaps, ignore online sessions and honor off days',()=>{
 const sessions=[row(1,'09:00','11:00'),row(2,'10:00','12:00'),row(3,'13:00','14:00'),row(4,'15:00','17:00',1)];
 expect(freeSlots(sessions,[],60).filter(s=>s.day===0)).toEqual([{day:0,start:720,end:780},{day:0,start:840,end:1080}]);
 expect(freeSlots(sessions,[0],60)[0]).toEqual({day:0,start:540,end:1080});
});
test('overlapping courses are separate and adjacent courses reuse a lane',()=>{
 const result=sessionLanes([row(1,'09:00','11:00'),row(2,'10:00','12:00'),row(3,'12:00','13:00')]);
 expect(result.get(1)).toEqual({lane:0,count:2});expect(result.get(2)).toEqual({lane:1,count:2});expect(result.get(3)).toEqual({lane:0,count:1});
});
test('study plan respects available time and excludes completed and expired work',()=>{
 const now=new Date('2026-11-20T12:00:00');const events=Array.from({length:3},(_,i)=>({key:String(i),title:String(i),due_at:'2026-11-21T12:00:00',completed:false}) as EventItem);
 expect(studyPlan(events,now,60,30)).toHaveLength(2);expect(busyDates(events,now)).toHaveLength(1);
 events[0].completed=true;events[1].due_at='2026-11-19T12:00:00';expect(studyPlan(events,now,60,30)).toHaveLength(1);expect(busyDates(events,now)).toHaveLength(0);
});
