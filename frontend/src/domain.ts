export interface Student { id: string; name: string; email: string }
export interface Course { id: string; code: string; name: string; professor: string; department: string; capacity: number; baseline: number }
export interface Enrollment { userId: string; courseId: string }
export interface State { version: 1; students: Student[]; courses: Course[]; enrollments: Enrollment[]; currentUserId: string | null; open: boolean; admitted: boolean }
export interface RegistrationRepository {
  load(): State;
  save(state: State): void;
}
export const DEMO_PASSWORD = 'demo1234';
export function seed(): State {
  const names = ['컴퓨터개론','프로그래밍 기초','자료구조','알고리즘','운영체제','데이터베이스','컴퓨터 네트워크','클라우드 컴퓨팅','소프트웨어 공학','웹 프로그래밍','인공지능 입문','정보보안 개론','경제학 원론','경영학 입문','마케팅의 이해','회계원리','미적분학','선형대수','통계학 입문','일반물리학','글쓰기와 사고','현대사회와 윤리','실용영어','디자인의 이해'];
  return { version: 1, students: [{ id: 'student-1', name: '김하늘', email: 'haneul@example.com' }, { id: 'student-2', name: '이바다', email: 'bada@example.com' }], courses: names.map((name, i) => ({ id: `course-${i+1}`, name, code: `${i < 12 ? 'CS' : i < 16 ? 'BA' : i < 20 ? 'SC' : 'GE'}${101+i}`, professor: ['김서연','박지훈','이수민','정도윤','최유진','한지우'][i%6], department: i < 12 ? '컴퓨터공학' : i < 16 ? '경영·경제' : i < 20 ? '자연과학' : '교양', capacity: 30 + (i%4)*10, baseline: i%5 === 0 ? 30+(i%4)*10 : i%5 === 1 ? 29+(i%4)*10 : 12+i%12 })), enrollments: [], currentUserId: null, open: false, admitted: false };
}
export function count(state: State, id: string): number {
  return state.courses.find(c => c.id === id)!.baseline + state.enrollments.filter(e => e.courseId === id).length;
}
export function register(state: State, courseId: string): State {
  if (!state.currentUserId || !state.open || !state.admitted) throw new Error('로그인 후 입장해 주세요.');
  const course = state.courses.find(c => c.id === courseId);
  if (!course) throw new Error('강의를 찾을 수 없습니다.');
  if (state.enrollments.some(e => e.userId === state.currentUserId && e.courseId === courseId)) throw new Error('이미 신청한 강의입니다.');
  if (count(state, courseId) >= course.capacity) throw new Error('정원이 마감된 강의입니다.');
  return { ...state, enrollments: [...state.enrollments, { userId: state.currentUserId, courseId }] };
}
export function cancel(state: State, courseId: string): State {
  if (!state.currentUserId || !state.open || !state.admitted) throw new Error('로그인 후 입장해 주세요.');
  if (!state.enrollments.some(e => e.userId === state.currentUserId && e.courseId === courseId)) throw new Error('취소할 신청 내역이 없습니다.');
  return { ...state, enrollments: state.enrollments.filter(e => !(e.userId === state.currentUserId && e.courseId === courseId)) };
}
