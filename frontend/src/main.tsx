import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { count, emptyState } from './domain';
import { ApiError, HttpRepository } from './repository';
import './style.css';
const repository = new HttpRepository();
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
  const [state, setState] = useState(emptyState);
  const [notice, setNotice] = useState({ text: '', error: false });
  const [signup, setSignup] = useState(false);
  const [search, setSearch] = useState('');
  const [department, setDepartment] = useState('전체');
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [tab, setTab] = useState<'all' | 'mine'>('all');
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const user = state.user;
  const mine = state.enrollments.filter(e => e.userId === user?.id);
  function message(text: string, error = false) { setNotice({text, error}); }
  useEffect(() => {
    let active = true;
    repository.load().then(next => { if(active) {setState(next);setReady(true);} })
      .catch(e => { if(active) {message((e as Error).message,true);setReady(true);} });
    return () => {active=false;};
  }, []);
  async function run(action: () => Promise<void>, success = '', enter = false) {
    if(busy) return;
    setBusy(true);
    try {
      await action();
      const next = await repository.load();
      setState(enter ? {...next,admitted:true} : next);
      message(success);
    } catch(e) {
      // A conflicting request can change occupancy; refresh authoritative data on failure.
      try { setState(await repository.load()); } catch { /* Preserve view; never fall back to mock data. */ }
      if(e instanceof ApiError && e.status===401 && e.code!=='INVALID_CREDENTIALS') setState(emptyState());
      message((e as Error).message,true);
    } finally {setBusy(false);}
  }
  function authenticate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const email = String(data.get('email')).trim().toLowerCase();
    const name = String(data.get('name') || '').trim();
    const password = String(data.get('password'));
    if(signup) {
      void run(async () => {await repository.signup(name,email,password);setSignup(false);},'가입이 완료되었습니다. 로그인해 주세요.');
    } else void run(() => repository.login(email,password));
  }
  function act(id: string, remove = false) {
    const enrollment=mine.find(e=>e.courseId===id);
    void run(() => remove && enrollment ? repository.cancel(enrollment.id) : repository.enroll(id),remove?'신청 취소가 완료되었습니다.':'수강신청이 완료되었습니다.');
  }
  const query = search.trim().toLowerCase();
  const filtered = state.courses.filter(c => (tab !== 'mine' || mine.some(e => e.courseId === c.id)) && (department === '전체' || department === c.department) && (!onlyAvailable || count(state,c.id) < c.capacity) && `${c.name} ${c.code} ${c.professor}`.toLowerCase().includes(query));
  return <><fieldset className="application-shell" disabled={busy || !ready}><div className="demo-bar"><span>LOCAL TEST ENVIRONMENT / SEED DATA</span> 로컬 테스트 환경{busy ? ' · 처리 중' : ''}</div>
    <header><a className="brand" href="#" onClick={e => e.preventDefault()}>한국대학교<span className="brand-sub">수강신청</span></a><div className="header-actions">{user && <><span>{user.name} 님</span><button className="text-button" onClick={() => { void run(() => repository.logout()); setSearch(''); setTab('all'); }}>로그아웃</button></>}</div></header>
    <main><div className="page-heading"><div className="eyebrow">2026 FALL SEMESTER · 가상 학기</div><h1>수강신청 시스템</h1></div>

    {!user ? <div className="auth-layout"><section className="intro"><span className="pill">수강신청 안내</span><h2>수강신청 이용 안내</h2><div className="steps"><div><b>01</b> 데모 계정 로그인</div><div><b>02</b> 수강신청 오픈 후 입장</div><div><b>03</b> 강의 신청 및 내역 확인</div></div></section><section className="panel auth-panel"><div className="tabs"><button className={!signup?'selected':''} onClick={() => {setSignup(false);message('');}}>로그인</button><button className={signup?'selected':''} onClick={() => {setSignup(true);message('');}}>회원가입</button></div><h2>{signup?'회원가입':'로그인'}</h2><p className="muted">{signup?'가상 이름과 이메일로 가입해 주세요.':'데모 계정 정보를 입력해 주세요.'}</p><form onSubmit={authenticate} key={String(signup)}>{signup && <label>이름<input name="name" required maxLength={30} autoComplete="off" placeholder="가상 이름"/></label>}<label>이메일<input name="email" type="email" required maxLength={100} defaultValue={signup?'':'haneul@example.com'} autoComplete="off" placeholder="student@example.com"/></label><label>비밀번호<input name="password" type="password" required minLength={signup ? 8 : undefined} maxLength={72} autoComplete="off"/></label><button className="primary wide">{signup?'데모 회원가입':'로그인 →'}</button></form><div className="demo-accounts"><b>바로 체험할 수 있는 계정</b><p>김하늘 · haneul@example.com<br/>이바다 · bada@example.com</p><p>시드 계정 비밀번호: 로컬 .env의 LOCAL_SEED_PASSWORD<br/>실제 계정 정보를 사용하지 마세요.</p></div></section></div>
    : !state.admitted || !state.open ? <section className="panel gate"><span className="pill">{state.open?'입장 가능':'오픈 대기 중'}</span><h2>{state.open?'수강신청 접수 중':'수강신청 시작 전'}</h2><p>수강신청 시작 <strong>10:00</strong> · 가상 일정</p><button className="primary enter" disabled={!state.open} onClick={() => { void run(() => repository.enter(),'',true); }}>수강신청 입장 →</button></section>
    : <><div className="summary"><div><span className="live-dot"/> 수강신청 진행 중 <small>2026학년도 2학기</small></div><div>내 신청 <strong>{mine.length}</strong> 과목</div></div><section className="panel courses"><div className="course-heading"><div><h2>수강신청</h2></div><div className="tabs course-tabs"><button className={tab==='all'?'selected':''} onClick={() => setTab('all')}>전체 강의 <b>24</b></button><button className={tab==='mine'?'selected':''} onClick={() => setTab('mine')}>내 신청 내역 <b>{mine.length}</b></button></div></div><div className="filters"><label className="search"><span className="sr-only">강의명, 코드, 교수 검색</span><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="강의명, 강의 코드, 교수명 검색"/></label><label><span className="sr-only">분야</span><select value={department} onChange={e=>setDepartment(e.target.value)}>{['전체','컴퓨터공학','경영·경제','자연과학','교양'].map(d=><option key={d}>{d}</option>)}</select></label><label className="checkbox"><input type="checkbox" checked={onlyAvailable} onChange={e=>setOnlyAvailable(e.target.checked)}/>신청 가능만</label></div><div className="result-count">총 <strong>{filtered.length}</strong>개 강의 </div><div className="table-wrap"><table><thead><tr><th>강의 정보</th><th>교수 / 분야</th><th>신청 인원 / 정원</th><th>상태</th><th><span className="sr-only">신청 관리</span></th></tr></thead><tbody>{filtered.map(c=>{const enrolled=count(state,c.id), own=mine.some(e=>e.courseId===c.id), full=enrolled>=c.capacity;return <tr key={c.id}><td><span className="course-code">{c.code}</span><strong className="course-name">{c.name}</strong></td><td>{c.professor}<span className="cell-sub">{c.department}</span></td><td><strong>{enrolled}</strong><span className="muted"> / {c.capacity}</span><div className="capacity"><i style={{width:`${enrolled/c.capacity*100}%`}} className={full?'full':''}/></div></td><td><span className={`status ${own?'enrolled':full?'closed':'available'}`}>{own?'신청 완료':full?'정원 마감':`잔여 ${c.capacity-enrolled}석`}</span></td><td>{own?<button className="secondary cancel" aria-label={`${c.name} 신청 취소`} onClick={()=>act(c.id,true)}>신청 취소</button>:<button className="primary" disabled={full} aria-label={`${c.name} ${full?'정원 마감':'신청'}`} onClick={()=>act(c.id)}>{full?'마감':'신청 +'}</button>}</td></tr>;})}</tbody></table></div>{!filtered.length && <div className="empty"><span>⌕</span><h3>{tab==='mine' && mine.length===0?'신청 내역이 없습니다':'검색 결과가 없습니다'}</h3><p>전체 강의를 조회하거나 검색 조건을 변경해 주세요.</p><button className="secondary" onClick={()=>{setSearch('');setDepartment('전체');setOnlyAvailable(false);setTab('all');}}>전체 강의 보기</button></div>}</section></>}
    <footer><b>한국대학교</b><span>수강신청 프론트엔드 프로토타입</span><span>로컬 PostgreSQL 연동</span></footer>{state.localControls && user && <details className="demo-tools"><summary>개발자용 시연 설정</summary><div className="demo-tools-content"><div><strong>개발·시연용 제어</strong><p>시작 상태를 변경하거나 데모 데이터를 초기화할 수 있습니다.</p></div><div className="demo-tools-actions"><button className="secondary" onClick={() => { void run(() => repository.setOpen(!state.open)); }}>{state.open?'오픈 전으로 변경':'지금 오픈하기'}</button><button className="text-button" onClick={() => message('전체 초기화는 저장소 루트에서 docker compose down -v 실행 후 docker compose up -d --build로 진행합니다. 모든 로컬 DB 데이터가 삭제되므로 필요한 데이터를 먼저 보관하세요.',true)}>데모 초기화 ↺</button></div></div></details>}</main></fieldset><FeedbackModal text={notice.text} error={notice.error} onClose={() => message('')}/></>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
