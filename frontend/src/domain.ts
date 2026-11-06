export interface Student { id: string; name: string; email: string }
export interface Course { id: string; code: string; name: string; professor: string; department: string; capacity: number; enrolledCount: number; reservedCount: number }
export interface Enrollment { id: string; userId: string; courseId: string }
export interface WindowState { open: boolean; serverTime: string; localControls: boolean }
export interface State { user: Student | null; courses: Course[]; enrollments: Enrollment[]; open: boolean; admitted: boolean; localControls: boolean }
export interface RegistrationRepository {
  load(): Promise<State>;
  signup(name: string, email: string, password: string): Promise<void>;
  login(email: string, password: string): Promise<void>;
  logout(): Promise<void>;
  enter(): Promise<void>;
  setOpen(open: boolean): Promise<void>;
  enroll(courseId: string): Promise<void>;
  cancel(id: string): Promise<void>;
}
export function emptyState(): State { return {user:null,courses:[],enrollments:[],open:false,admitted:false,localControls:false}; }
export function count(state: State, id: string): number { return state.courses.find(c=>c.id===id)?.enrolledCount ?? 0; }
