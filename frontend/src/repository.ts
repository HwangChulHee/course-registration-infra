import { emptyState, type Course, type Enrollment, type RegistrationRepository, type State, type Student, type WindowState } from './domain';
const TOKEN = 'registration-session-token';
const ADMITTED = 'registration-admitted-user';
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}
export class HttpRepository implements RegistrationRepository {
  private token: string | null = null;
  private admittedUserId: string | null = null;
  constructor() {
    // Session storage only retains this tab's bearer token/UI admission, never enrollments.
    try { this.token = sessionStorage.getItem(TOKEN); this.admittedUserId=sessionStorage.getItem(ADMITTED); } catch { /* Memory-only if storage is blocked. */ }
  }
  private remember(token: string | null) {
    this.token=token; this.admittedUserId=null;
    try { if(token) sessionStorage.setItem(TOKEN,token); else sessionStorage.removeItem(TOKEN); sessionStorage.removeItem(ADMITTED); } catch { /* Memory-only session. */ }
  }
  private async request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`/api/v1${path}`, {method, headers:{...(body!==undefined?{'Content-Type':'application/json'}:{}),...(this.token?{Authorization:`Bearer ${this.token}`}:{})},...(body!==undefined?{body:JSON.stringify(body)}:{}), signal:AbortSignal.timeout(15000)});
    } catch { throw new ApiError(0,'NETWORK','서버에 연결할 수 없습니다. 연결 상태를 확인 후 다시 시도해 주세요.'); }
    if(!response.ok) {
      if(response.status===401 && path!=='/auth/login') this.remember(null);
      const error = await response.json().catch(()=>({}));
      throw new ApiError(response.status,error.code || 'HTTP_ERROR',error.message || '요청 처리에 실패했습니다. 다시 시도해 주세요.');
    }
    if(response.status===204) return undefined as T;
    return response.json() as Promise<T>;
  }
  async load(): Promise<State> {
    const window = await this.request<WindowState>('/registration/window');
    const state={...emptyState(),open:window.open,localControls:window.localControls};
    if(!this.token) return state;
    let user: Student;
    try { user=await this.request<Student>('/auth/me'); }
    catch(e) { if(e instanceof ApiError && e.status===401) return state; throw e; }
    const [courses,enrollments]=await Promise.all([this.request<Course[]>('/courses'),this.request<Enrollment[]>('/enrollments/me')]);
    if(!window.open) this.admittedUserId=null;
    const admitted=window.open && this.admittedUserId===user.id;
    return {...state,user,courses,enrollments,admitted};
  }
  async signup(name: string,email: string,password: string) { await this.request('/auth/signup','POST',{name,email,password}); }
  async login(email: string,password: string) {
    const auth=await this.request<{token:string}>('/auth/login','POST',{email,password}); this.remember(auth.token);
  }
  async logout() { await this.request('/auth/logout','POST'); this.remember(null); }
  async enter() {
    const window=await this.request<WindowState>('/registration/window');
    if(!window.open) throw new ApiError(409,'NOT_OPEN','수강신청 기간이 아닙니다.');
    const user=await this.request<Student>('/auth/me');
    this.admittedUserId=user.id;
    try { sessionStorage.setItem(ADMITTED,user.id); } catch { /* App keeps admission in memory as well. */ }
  }
  async setOpen(open: boolean) { await this.request('/local/registration/window','PUT',{open}); this.admittedUserId=null; try {sessionStorage.removeItem(ADMITTED);} catch { /* UI flag only. */ } }
  async enroll(courseId: string) { await this.request('/enrollments','POST',{courseId}); }
  async cancel(id: string) { await this.request(`/enrollments/${encodeURIComponent(id)}`,'DELETE'); }
}
