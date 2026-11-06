import { describe, expect, it } from 'vitest';
import { seed, register, cancel, count } from './domain';
const ready = () => ({...seed(), currentUserId:'student-1', open:true, admitted:true});
describe('수강신청 정합성', () => {
  it('로그인 및 입장 전 신청 차단', () => { expect(()=>register(seed(),'course-2')).toThrow(); expect(()=>register({...ready(),admitted:false},'course-2')).toThrow(); });
  it('마감 강의 차단', () => {expect(()=>register(ready(),'course-1')).toThrow('정원');});
  it('신청과 중복 차단, 취소 후 정원 복구 및 재신청', () => {
    const original=ready(); const before=count(original,'course-2');
    const registered=register(original,'course-2');
    expect(count(registered,'course-2')).toBe(before+1);
    expect(()=>register(registered,'course-2')).toThrow('이미');
    const cancelled=cancel(registered,'course-2');
    expect(count(cancelled,'course-2')).toBe(before);
    expect(()=>cancel(cancelled,'course-2')).toThrow('없습니다');
    expect(register(cancelled,'course-2').enrollments).toHaveLength(1);
  });
  it('마지막 한 자리를 다른 계정이 중복 점유하지 않음', () => {
    const first=register(ready(),'course-2');
    const second={...first,currentUserId:'student-2'};
    expect(second.enrollments.filter(e=>e.userId===second.currentUserId)).toHaveLength(0);
    expect(()=>register(second,'course-2')).toThrow('정원');
    expect(()=>cancel(second,'course-2')).toThrow('없습니다');
    expect(first.enrollments).toHaveLength(1);
  });
});
