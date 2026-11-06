import http from 'k6/http';
import { sleep } from 'k6';
import exec from 'k6/execution';
import { Counter, Rate, Trend } from 'k6/metrics';
import { SharedArray } from 'k6/data';

const config=JSON.parse(open(__ENV.RUN_CONFIG));
const users=new SharedArray('independent sessions',()=>JSON.parse(open('/artifacts/fixtures.json')).users);
const base=__ENV.BASE_URL;
let runOffset=0;
if(base!=='http://frontend') throw new Error('Only the isolated Compose frontend is allowed');
const cap=config.high?1000:200;
if(config.users>10000 || config.rate>(config.high?1000:200) || config.vus>cap) throw new Error('Safety cap exceeded');
const counters=Object.fromEntries(['requests_started','responses_finished','http_2xx','created','canceled','full','duplicate','not_open','unauthorized','server_5xx','network_errors','unexpected','journeys_started','journeys_completed','scheduler_extra_iterations'].map(name=>[name,new Counter(name)]));
const latency=new Trend('measured_latency',true);
const journeyLatency=new Trend('journey_latency',true);
const starts=new Trend('iteration_start_ms');
const finishes=new Trend('response_finish_ms');
const wallStarts=new Trend('wall_iteration_start_ms');
const requestStarts=new Trend('request_start_ms');
const faults=new Rate('server_fault_rate');

export const options={
  scenarios:{measurement:{executor:'constant-arrival-rate',rate:config.rate,timeUnit:'1s',duration:`${config.seconds}s`,preAllocatedVUs:config.vus,maxVUs:config.vus,gracefulStop:'20s'}},
  setupTimeout:'30s',
  summaryTrendStats:['min','med','p(50)','p(95)','p(99)','max','avg','count'],
  systemTags:['status','method','name','scenario','expected_response'],
  thresholds:{
    server_fault_rate:[{threshold:'rate<0.02',abortOnFail:true,delayAbortEval:'3s'}],
    dropped_iterations:[{threshold:'count==0',abortOnFail:true,delayAbortEval:'2s'}],
    unexpected:['count==0'],
    measured_latency:[`p(95)<${config.observeP95Ms || 2000}`],
  },
};
http.setResponseCallback(http.expectedStatuses(200,201,204,409));
function params(user,name,phase='measurement') {return {headers:{Authorization:`Bearer ${user.token}`,'Content-Type':'application/json'},tags:{name,phase},timeout:'10s'};}
function control(openWindow) {
  return http.put(`${base}/api/v1/local/registration/window`,JSON.stringify({open:openWindow}),params(users[0],'control','control'));
}
export function setup() {
  for(let i=0;i<config.warmupMs/100;i++) {http.get(`${base}/api/v1/courses`,params(users[1],'warmup','warmup'));sleep(0.1);}
  let openedAt=null;
  if(config.scenario==='D') {
    if(control(false).status!==200) throw new Error('Unable to close benchmark window');
    const pre=http.post(`${base}/api/v1/enrollments`,JSON.stringify({courseId:'course-1'}),params(users[1],'preopen','control'));
    if(pre.status!==409 || pre.json('code')!=='NOT_OPEN') throw new Error('Pre-open check failed');
    if(control(true).status!==200) throw new Error('Unable to open benchmark window');
    openedAt=Date.now();
    console.log(`OPEN_MARKER ${openedAt}`);
  }
  return {openedAt,runOffset:exec.instance.currentTestRunDuration};
}
function request(method,path,user,body,name) {
  counters.requests_started.add(1);
  requestStarts.add(exec.instance.currentTestRunDuration-runOffset);
  const response=http.request(method,`${base}/api/v1${path}`,body===null?null:JSON.stringify(body),params(user,name));
  counters.responses_finished.add(1);
  latency.add(response.timings.duration,{operation:name});
  finishes.add(exec.instance.currentTestRunDuration-runOffset);
  const status=response.status;
  const code=status===409?response.json('code'):null;
  const classification=status>=200&&status<300?'http_2xx':status===409&&code==='FULL'?'full':status===409&&code==='DUPLICATE'?'duplicate':status===409&&code==='NOT_OPEN'?'not_open':status===401?'unauthorized':status>=500?'server_5xx':status===0?'network_errors':'unexpected';
  counters[classification].add(1);
  if(status===201 && name==='enroll') counters.created.add(1);
  if(status===204 && name==='cancel') counters.canceled.add(1);
  faults.add(status>=500 || status===0);
  if(classification==='unauthorized' || classification==='not_open') counters.unexpected.add(1);
  return response;
}
export default function (setupData) {
  runOffset=setupData.runOffset;
  const index=exec.scenario.iterationInTest;
  // k6 may schedule an endpoint-boundary iteration; keep the finite planned population.
  // Delayed iterations inside that population still execute and are reported as late.
  if(index>=config.rate*config.seconds) {counters.scheduler_extra_iterations.add(1);return;}
  if(config.scenario!=='A' && index>=config.users) throw new Error('Insufficient independent student inventory');
  const user=users[1+index%config.users];
  counters.journeys_started.add(1);
  starts.add(exec.instance.currentTestRunDuration-runOffset);
  wallStarts.add(Date.now()-exec.scenario.startTime);
  const begin=exec.instance.currentTestRunDuration;
  if(config.scenario==='A') {
    const result=request('GET','/courses',user,null,'courses');
    if(result.status===200) counters.journeys_completed.add(1);
  } else if(config.scenario==='B' || config.scenario.startsWith('C')) {
    const courseId=config.scenario==='B'?`course-${1+index%24}`:config.scenario==='C5'?`course-${1+index%5}`:'course-1';
    const result=request('POST','/enrollments',user,{courseId},'enroll');
    if(result.status===201 || (result.status===409 && result.json('code')==='FULL')) counters.journeys_completed.add(1);
  } else if(config.scenario==='D') {
    const listed=request('GET','/courses',user,null,'courses');
    const courseId=index%4===0?`course-${1+index%5}`:`course-${6+index%19}`;
    const enrolled=request('POST','/enrollments',user,{courseId},'enroll');
    let optionalOk=true;
    if(enrolled.status===201 && index%20===0) optionalOk=request('POST','/enrollments',user,{courseId},'duplicate-probe').status===409;
    if(enrolled.status===201 && index%10===0) optionalOk=request('DELETE',`/enrollments/${enrolled.json('id')}`,user,null,'cancel').status===204 && optionalOk;
    const history=request('GET','/enrollments/me',user,null,'history');
    if(listed.status===200 && history.status===200 && optionalOk && (enrolled.status===201 || (enrolled.status===409 && enrolled.json('code')==='FULL'))) counters.journeys_completed.add(1);
  }
  journeyLatency.add(exec.instance.currentTestRunDuration-begin);
}
export function teardown() { if(config.cooldownMs) sleep(config.cooldownMs/1000); }
export function handleSummary(data) {
  return {[`${__ENV.OUT_DIR}/k6-summary.json`]:JSON.stringify(data,null,2),stdout:`SUMMARY ${JSON.stringify({iterations:data.metrics.iterations?.values,created:data.metrics.created?.values,full:data.metrics.full?.values,drops:data.metrics.dropped_iterations?.values})}\n`};
}
