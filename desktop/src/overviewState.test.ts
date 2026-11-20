import {expect,test} from 'vitest';
import {deadlineGroup,orderByDeadline} from './overviewState';
import type {EventItem} from './types';
const event=(due_at:string|null,completed=false)=>({title:'과제',due_at,completed}) as EventItem;
test('deadline groups handle completed, missing, invalid and day boundaries',()=>{
 const now=new Date('2026-11-20T12:00:00');
 expect(deadlineGroup(event('2026-11-20T11:59:00'),now)).toBe('overdue');
 expect(deadlineGroup(event('2026-11-20T23:59:59'),now)).toBe('today');
 expect(deadlineGroup(event('2026-11-21T00:00:00'),now)).toBe('week');
 expect(deadlineGroup(event('2026-11-27T12:00:00'),now)).toBe('week');
 expect(deadlineGroup(event('2026-11-27T12:00:01'),now)).toBe('later');
 expect(deadlineGroup(event('2026-11-28T00:00:00'),now)).toBe('later');
 expect(deadlineGroup(event(null),now)).toBe('undated');
 expect(deadlineGroup(event('invalid'),now)).toBe('undated');
 expect(deadlineGroup(event(null,true),now)).toBe('completed');
});
test('sort keeps missing dates last without changing original order',()=>{
 const input=[event(null),event('2026-11-21'),event('2026-11-20')];
 expect(orderByDeadline(input)).toEqual([input[2],input[1],input[0]]);
 expect(input[0].due_at).toBeNull();
});
