import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { HttpRepository } from './repository';
const values=new Map<string,string>();
beforeEach(()=>{
  values.clear();
  vi.stubGlobal('sessionStorage',{getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>values.set(k,v),removeItem:(k:string)=>values.delete(k)});
  vi.stubGlobal('localStorage',{getItem:()=>{throw new Error('legacy storage must never be read');}});
});
afterEach(()=>vi.unstubAllGlobals());
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
it('이전 Mock 저장 데이터 없이 서버 사용자·강의·내역을 복원한다',async()=>{
  values.set('registration-session-token','test-token');
  const fetcher=vi.fn().mockResolvedValueOnce(json({open:true,localControls:true})).mockResolvedValueOnce(json({id:'u',name:'사용자',email:'u@example.com'})).mockResolvedValueOnce(json([{id:'course-2',enrolledCount:40}])).mockResolvedValueOnce(json([{id:'e',userId:'u',courseId:'course-2'}]));
  vi.stubGlobal('fetch',fetcher);
  const state=await new HttpRepository().load();
  expect(state.user?.id).toBe('u'); expect(state.courses[0].enrolledCount).toBe(40); expect(state.enrollments[0].id).toBe('e');
  expect(fetcher.mock.calls[1][1].headers.Authorization).toBe('Bearer test-token');
});
it('만료 토큰을 제거하고 로그인 화면으로 돌아간다',async()=>{
  values.set('registration-session-token','expired');
  vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(json({open:false,localControls:true})).mockResolvedValueOnce(json({code:'UNAUTHORIZED',message:'로그인이 필요합니다.'},401)));
  expect((await new HttpRepository().load()).user).toBeNull();
  expect(values.has('registration-session-token')).toBe(false);
});
it('네트워크 오류 시 Mock 결과로 대체하지 않는다',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new Error('offline')));
  await expect(new HttpRepository().load()).rejects.toThrow('서버에 연결할 수 없습니다');
});
