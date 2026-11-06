import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { cancel, count, DEMO_PASSWORD, register, seed, type State } from './domain';
import { LocalRepository } from './repository';
import './style.css';
const repository = new LocalRepository();
function bootstrap() { try { return { state: repository.load(), error: '' }; } catch (e) { return { state: seed(), error: (e as Error).message }; } }
const initial = bootstrap();
function FeedbackModal({ text, error, onClose }: { text: string; error: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    if (text && element && !element.open) element.showModal();
    if (!text && element?.open) element.close();
  }, [text]);
  return <dialog ref={dialog} className="feedback-modal" aria-labelledby="feedback-title" aria-describedby="feedback-description" onCancel={onClose} onClose={onClose}>
    <div className={`feedback-icon ${error ? 'feedback-error' : ''}`} aria-hidden="true">{error ? '!' : '✓'}</div>
    <h2 id="feedback-title">{error ? '확인이 필요합니다' : '작업 완료'}</h2>
    <p id="feedback-description">{text}</p>
    <form method="dialog"><button className="primary wide" autoFocus>확인</button></form>
  </dialog>;
}
function App() {
  const [state, setState] = useState(initial.state);
  const [notice, setNotice] = useState({ text: initial.error, error: !!initial.error });
  const [signup, setSignup] = useState(false);
  const [search, setSearch] = useState('');
  const [department, setDepartment] = useState('전체');
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [tab, setTab] = useState<'all' | 'mine'>('all');
  const user = state.students.find(s => s.id === state.currentUserId);
  const mine = state.enrollments.filter(e => e.userId === user?.id);
  function message(text: string, error = false) { setNotice({text, error}); }
  function commit(next: State) {
    setState(next);
    try { repository.save(next); return true; } catch { message('브라우저 저장이 불가능합니다. 현재 화면에서는 사용할 수 있지만 새로고침 시 변경 사항이 사라집니다.', true); return false; }
  }
  function authenticate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const email = String(data.get('email')).trim().toLowerCase();
    const name = String(data.get('name') || '').trim();
    if (String(data.get('password')) !== DEMO_PASSWORD) return message(`시연용 공통 비밀번호 ${DEMO_PASSWORD}를 입력해 주세요.`, true);
    if (signup) {
      if (!name || name.length > 30) return message('이름을 1~30자로 입력해 주세요.', true);
      if (state.students.some(s => s.email === email)) return message('이미 가입된 이메일입니다. 로그인해 주세요.', true);
      if (commit({...state, students: [...state.students, {id: crypto.randomUUID(), name, email}]})) message('데모 가입이 완료되었습니다. 같은 이메일로 로그인해 주세요.');
      setSignup(false);
    } else {
      const student = state.students.find(s => s.email === email);
      if (!student) return message('등록된 데모 계정이 없습니다. 먼저 가입해 주세요.', true);
      if (commit({...state, currentUserId: student.id, admitted: false})) message('');
    }
  }
  function act(id: string, remove = false) {
    try { const next = remove ? cancel(state, id) : register(state, id); if (commit(next)) message(remove ? '신청 취소가 완료되었습니다.' : '수강신청이 완료되었습니다.'); }
    catch(e) { message((e as Error).message, true); }
  }
  const query = search.trim().toLowerCase();
  const filtered = state.courses.filter(c => (tab !== 'mine' || mine.some(e => e.courseId === c.id)) && (department === '전체' || department === c.department) && (!onlyAvailable || count(state,c.id) < c.capacity) && `${c.name} ${c.code} ${c.professor}`.toLowerCase().includes(query));
  return <><div className="demo-bar"><span>DEMO / MOCK DATA</span> 가상 데이터로 체험하는 수강신청 · 실제 인증 및 서버 저장 없음</div>
    <header><a className="brand" href="#" onClick={e => e.preventDefault()}>한국대학교<span className="brand-sub">수강신청</span></a><div className="header-actions">{user && <><span>{user.name} 님</span><button className="text-button" onClick={() => { if (commit({...state,currentUserId:null,admitted:false})) message('로그아웃되었습니다.'); setSearch(''); setTab('all'); }}>로그아웃</button></>}</div></header>
    <main><div className="page-heading"><div className="eyebrow">2026 FALL SEMESTER · 가상 학기</div><h1>수강신청 시스템</h1></div>
    <FeedbackModal text={notice.text} error={notice.error} onClose={() => message('')}/>
    {!user ? <div className="auth-layout"><section className="intro"><span className="pill">수강신청 안내</span><h2>수강신청 이용 안내</h2><div className="steps"><div><b>01</b> 데모 계정 로그인</div><div><b>02</b> 수강신청 오픈 후 입장</div><div><b>03</b> 강의 신청 및 내역 확인</div></div></section><section className="panel auth-panel"><div className="tabs"><button className={!signup?'selected':''} onClick={() => {setSignup(false);message('');}}>로그인</button><button className={signup?'selected':''} onClick={() => {setSignup(true);message('');}}>회원가입</button></div><h2>{signup?'회원가입':'로그인'}</h2><p className="muted">{signup?'가상 이름과 이메일로 가입해 주세요.':'데모 계정 정보를 입력해 주세요.'}</p><form onSubmit={authenticate} key={String(signup)}>{signup && <label>이름<input name="name" required maxLength={30} autoComplete="off" placeholder="가상 이름"/></label>}<label>이메일<input name="email" type="email" required maxLength={100} defaultValue={signup?'':'haneul@example.com'} autoComplete="off" placeholder="student@example.com"/></label><label>시연용 비밀번호<input name="password" type="password" required defaultValue={DEMO_PASSWORD} autoComplete="off"/></label><button className="primary wide">{signup?'데모 회원가입':'로그인 →'}</button></form><div className="demo-accounts"><b>바로 체험할 수 있는 계정</b><p>김하늘 · haneul@example.com<br/>이바다 · bada@example.com</p><p>모든 계정 공통 비밀번호: <code>{DEMO_PASSWORD}</code><br/>실제 비밀번호를 입력하지 마세요. 비밀번호는 저장하지 않습니다.</p></div></section></div>
    : !state.admitted || !state.open ? <section className="panel gate"><span className="pill">{state.open?'입장 가능':'오픈 대기 중'}</span><h2>{state.open?'수강신청 접수 중':'수강신청 시작 전'}</h2><p>수강신청 시작 <strong>10:00</strong> · 가상 일정</p><button className="primary enter" disabled={!state.open} onClick={() => { if(commit({...state,admitted:true})) message(''); }}>수강신청 입장 →</button></section>
    : <><div className="summary"><div><span className="live-dot"/> 수강신청 진행 중 <small>2026학년도 2학기</small></div><div>내 신청 <strong>{mine.length}</strong> 과목</div></div><section className="panel courses"><div className="course-heading"><div><h2>수강신청</h2></div><div className="tabs course-tabs"><button className={tab==='all'?'selected':''} onClick={() => setTab('all')}>전체 강의 <b>24</b></button><button className={tab==='mine'?'selected':''} onClick={() => setTab('mine')}>내 신청 내역 <b>{mine.length}</b></button></div></div><div className="filters"><label className="search"><span className="sr-only">강의명, 코드, 교수 검색</span><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="강의명, 강의 코드, 교수명 검색"/></label><label><span className="sr-only">분야</span><select value={department} onChange={e=>setDepartment(e.target.value)}>{['전체','컴퓨터공학','경영·경제','자연과학','교양'].map(d=><option key={d}>{d}</option>)}</select></label><label className="checkbox"><input type="checkbox" checked={onlyAvailable} onChange={e=>setOnlyAvailable(e.target.checked)}/>신청 가능만</label></div><div className="result-count">총 <strong>{filtered.length}</strong>개 강의 </div><div className="table-wrap"><table><thead><tr><th>강의 정보</th><th>교수 / 분야</th><th>신청 인원 / 정원</th><th>상태</th><th><span className="sr-only">신청 관리</span></th></tr></thead><tbody>{filtered.map(c=>{const enrolled=count(state,c.id), own=mine.some(e=>e.courseId===c.id), full=enrolled>=c.capacity;return <tr key={c.id}><td><span className="course-code">{c.code}</span><strong className="course-name">{c.name}</strong></td><td>{c.professor}<span className="cell-sub">{c.department}</span></td><td><strong>{enrolled}</strong><span className="muted"> / {c.capacity}</span><div className="capacity"><i style={{width:`${enrolled/c.capacity*100}%`}} className={full?'full':''}/></div></td><td><span className={`status ${own?'enrolled':full?'closed':'available'}`}>{own?'신청 완료':full?'정원 마감':`잔여 ${c.capacity-enrolled}석`}</span></td><td>{own?<button className="secondary cancel" aria-label={`${c.name} 신청 취소`} onClick={()=>act(c.id,true)}>신청 취소</button>:<button className="primary" disabled={full} aria-label={`${c.name} ${full?'정원 마감':'신청'}`} onClick={()=>act(c.id)}>{full?'마감':'신청 +'}</button>}</td></tr>;})}</tbody></table></div>{!filtered.length && <div className="empty"><span>⌕</span><h3>{tab==='mine' && mine.length===0?'신청 내역이 없습니다':'검색 결과가 없습니다'}</h3><p>전체 강의를 조회하거나 검색 조건을 변경해 주세요.</p><button className="secondary" onClick={()=>{setSearch('');setDepartment('전체');setOnlyAvailable(false);setTab('all');}}>전체 강의 보기</button></div>}</section></>}
    <footer><b>한국대학교</b><span>수강신청 프론트엔드 프로토타입</span><span>단일 브라우저 데모 · 다중 사용자 동시성 보장 없음</span></footer><details className="demo-tools"><summary>개발자용 시연 설정</summary><div className="demo-tools-content"><div><strong>개발·시연용 제어</strong><p>시작 상태를 변경하거나 데모 데이터를 초기화할 수 있습니다.</p></div><div className="demo-tools-actions"><button className="secondary" onClick={() => { if(commit({...state,open:!state.open,admitted:false})) message(''); }}>{state.open?'오픈 전으로 변경':'지금 오픈하기'}</button><button className="text-button" onClick={() => { if (window.confirm('가입 계정과 모든 신청 내역을 초기화할까요?')) { if (commit(seed())) message('데모를 초기화했습니다.'); setSearch(''); setDepartment('전체'); setOnlyAvailable(false); setTab('all'); setSignup(false); } }}>데모 초기화 ↺</button></div></div></details></main></>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
