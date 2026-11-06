import { seed, type RegistrationRepository, type State } from './domain';
const KEY = 'campus-registration-demo-v1';
export class LocalRepository implements RegistrationRepository {
  load(): State {
    const raw = localStorage.getItem(KEY);
    if (!raw) return seed();
    try {
      const value = JSON.parse(raw) as State;
      if (value.version !== 1 || !Array.isArray(value.students) || !Array.isArray(value.courses) || !Array.isArray(value.enrollments) || typeof value.open !== 'boolean' || typeof value.admitted !== 'boolean') throw new Error();
      // Seed data remains authoritative; only demo students and enrollments persist.
      const initial = seed();
      if (!value.students.every(s => typeof s.id === 'string' && typeof s.name === 'string' && typeof s.email === 'string')) throw new Error();
      const seen = new Set<string>();
      initial.students = value.students;
      for (const e of value.enrollments) {
        const key = `${e.userId}:${e.courseId}`;
        const course = initial.courses.find(c => c.id === e.courseId);
        if (!course || !initial.students.some(s => s.id === e.userId) || seen.has(key) || course.baseline + initial.enrollments.filter(x => x.courseId === e.courseId).length >= course.capacity) throw new Error();
        seen.add(key); initial.enrollments.push(e);
      }
      initial.currentUserId = initial.students.some(s => s.id === value.currentUserId) ? value.currentUserId : null;
      initial.open = value.open;
      initial.admitted = !!initial.currentUserId && value.open && value.admitted;
      return initial;
    } catch { throw new Error('저장된 데모 데이터가 손상되었습니다. 새 상태로 시작했습니다.'); }
  }
  save(state: State) { localStorage.setItem(KEY, JSON.stringify(state)); }
}
