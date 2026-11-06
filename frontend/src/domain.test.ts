import { expect, it } from 'vitest';
import { count, emptyState } from './domain';
it('표시 인원은 서버 count를 사용하며 본인 신청을 다시 합산하지 않는다',()=>{
  const state=emptyState();
  state.courses=[{id:'course-2',code:'CS102',name:'프로그래밍 기초',professor:'박지훈',department:'컴퓨터공학',capacity:40,enrolledCount:40,reservedCount:39}];
  state.enrollments=[{id:'enrollment',userId:'user',courseId:'course-2'}];
  expect(count(state,'course-2')).toBe(40);
  expect(emptyState().courses).toEqual([]);
});
