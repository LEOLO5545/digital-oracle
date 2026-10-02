"""Loopback-only local prototype, no public deployment or trading operations."""
import concurrent.futures, time, datetime, hashlib, hmac, json, os, re, secrets, shutil, subprocess, sys, threading, uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from sources import CATALOG,ROOT,STATE
from quant import cross_market, evidence_for_model
from language import traditional, report_language
from routing import route_plan, preset_plan
from liquidity import liquidity_anchors
from evaluation import audit_and_revise, assess
from probability import materialize
from answer_types import route_answer, materialize_answer
from coverage import signal_counts, coverage_text
from compact import report_evidence, report_quant, report_plan
from telemetry import measurement, prompt_parts
from signal_policy import apply_policy, config, trim_to_budget
from fetch_cache import cache_key, usable
from anomaly import classify
from report_split import synthesis_context, restore_observations, generate_report, compact_row
PORT=8765
METHOD_VERSION='2026-09-30-layered-v4'
BUILD_ID=hashlib.sha256(b''.join((ROOT/f).read_bytes() for f in ('server.py','analysis.py','quant.py','sources.py','derivatives.py','routing.py','liquidity.py','language.py','coverage.py','evaluation.py','compact.py','report_split.py','signal_policy.py','anomaly.py','fetch_cache.py','telemetry.py','config/analysis.json','probability.py','answer_types.py','target_data.py','hk_data.py'))).hexdigest()[:12]
TOKEN=secrets.token_urlsafe(32)
LOCK=threading.RLock();JOBS={};STATUS={};BUSY=False
# Stopping an analysis. Only one job runs at a time (BUSY), so one flag and one process registry suffice.
CANCEL=threading.Event();ACTIVE=set();ACTIVE_LOCK=threading.Lock()
STOP_MESSAGE='已停止分析（由你手動停止）。已取得的市場數據已保存，可稍後接續報告。'
class Cancelled(RuntimeError):
 def __init__(self):super().__init__(STOP_MESSAGE)
def check_cancel():
 if CANCEL.is_set():raise Cancelled()
def run_tracked(cmd,input_text,timeout,env=None):
 """subprocess.run equivalent whose child (and its own children) can be stopped by cancel_job."""
 check_cancel()
 p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,start_new_session=True)
 with ACTIVE_LOCK:ACTIVE.add(p)
 try:
  try:out,err=p.communicate(input_text,timeout=timeout)
  except subprocess.TimeoutExpired:
   stop_process(p);out,err=p.communicate()
   raise subprocess.TimeoutExpired(cmd,timeout,output=out,stderr=err)
 finally:
  with ACTIVE_LOCK:ACTIVE.discard(p)
 check_cancel()
 return subprocess.CompletedProcess(cmd,p.returncode,out,err)
def stop_process(p):
 import signal
 for sig in (signal.SIGTERM,signal.SIGKILL):
  if p.poll() is not None:return
  try:os.killpg(p.pid,sig)
  except (ProcessLookupError,PermissionError):
   try:p.send_signal(sig)
   except ProcessLookupError:return
  try:p.wait(timeout=3)
  except subprocess.TimeoutExpired:continue
def stop_children():
 """Children run in their own sessions (so a stop can reach them); the server must end them itself on exit."""
 CANCEL.set()
 with ACTIVE_LOCK:procs=list(ACTIVE)
 for p in procs:stop_process(p)
def cancel_job(jid):
 if not re.fullmatch(r'[a-f0-9]{32}',jid or ''):raise ValueError('無效工作編號')
 with LOCK:
  job=JOBS.get(jid)
  if not job:raise ValueError('找不到工作')
  if job.get('status')!='running':raise RuntimeError('這項分析已經結束')
  CANCEL.set();job['cancel_requested_at']=now()
 with ACTIVE_LOCK:procs=list(ACTIVE)
 for p in procs:stop_process(p)
class PlanningFailed(RuntimeError):pass
class NoMarketData(RuntimeError):
 def __init__(self):super().__init__('呢條問題搵唔到可以反映佢嘅金融市場數據（例如個人行程、私人事件），所以冇辦法用市場推算。可以改問同市場有關嘅問題，例如相關行業、匯率、商品價格或事件合約。')
def plain_error(exc):
 """Turn internal failure text into something a reader can act on."""
 text=str(exc)
 m=re.search(r'模型回覆逾時（(\d+)秒）',text)
 if m:return f'Codex 喺 {m.group(1)} 秒內冇完成呢一步，可能係用量接近上限或者伺服器繁忙。請稍後再試；已取得的市場數據已保存，可接續報告。'
 if 'Codex 未完成回覆' in text:return 'Codex 未能完成回覆，可能係登入已過期、用量已達上限或者連線中斷。請檢查 Codex 登入及用量後再試。'
 return text[:250]
def record_failure(job,exc,stage='未完成'):
 # A validated draft is useful even when a later model step fails.
 draft=JOBS[job].get('generated_report')
 if draft:update(job,report=draft,answer=draft.get('conclusion',''),preview=True)
 if CANCEL.is_set() or isinstance(exc,Cancelled):
  update(job,status='error',cancelled=True,stage='已停止',error=STOP_MESSAGE)
 elif isinstance(exc,(PlanningFailed,NoMarketData)):
  update(job,status='error',stage=stage,error=str(exc)[:400],no_market_data=isinstance(exc,NoMarketData))
 else:
  update(job,status='error',stage=stage,error=plain_error(exc) if isinstance(exc,RuntimeError) else '分析核對未完成：'+str(exc)[:160])

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
from analysis import PLANNER, REPORT, parse_json, validate_plan, validate_report, signal_key, prepare_supplement
def allowed_request(host,origin,token,expected):
 hosts={f'127.0.0.1:{PORT}',f'localhost:{PORT}'}
 return host in hosts and (not origin or origin==f'http://{host}') and hmac.compare_digest(token or '',expected)
def persist(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2));tmp.chmod(0o600);tmp.replace(path)
def saved_report(path):
 data=json.loads(path.read_text())
 audit=STATE/'audits'/(str(data.get('id'))+'.json')
 if audit.exists() and 'quality_audit' not in data:data['quality_audit']=json.loads(audit.read_text())
 return data
def job_view(rid):
 if not re.fullmatch(r'[a-f0-9]{32}',rid):return {'error':'無效工作編號'}
 if rid in JOBS:return JOBS[rid]
 path=STATE/'reports'/(rid+'.json')
 if not path.exists():return {'error':'找不到工作，請從本機研究紀錄重新開啟'}
 data=saved_report(path)
 if data.get('status')=='running':
  data.update(status='error',stage='服務中斷，數據已保存',models_active={},error='本機服務曾中斷；已保存的證據及草稿可接續。')
  if data.get('generated_report'):data.update(report=data['generated_report'],preview=True)
 return data

_CODEX=None
def merge_login_path():
 """Finder/Dock launches skip ~/.zshrc, so node/codex installed via Homebrew, npm or nvm are not on PATH.
 Borrow the PATH an interactive login shell would have (it also lets a node-based codex find node)."""
 try:out=subprocess.run(['/bin/zsh','-lic','print -r -- "__ORACLE_PATH__$PATH"'],capture_output=True,text=True,timeout=15,stdin=subprocess.DEVNULL).stdout
 except (OSError,subprocess.SubprocessError):return
 line=next((l for l in reversed(out.splitlines()) if l.startswith('__ORACLE_PATH__')),'')
 extra=[p for p in line[len('__ORACLE_PATH__'):].split(':') if p.startswith('/')]
 current=os.environ.get('PATH','').split(':')
 os.environ['PATH']=':'.join(current+[p for p in extra if p not in current])

def bundled_codex(roots=None):
 """The ChatGPT / Codex desktop apps ship the CLI inside the app bundle (e.g. Resources/codex-cli/bin/codex)."""
 home=os.path.expanduser('~')
 roots=roots or [a+'/Contents/Resources' for a in ('/Applications/ChatGPT.app','/Applications/Codex.app',home+'/Applications/ChatGPT.app',home+'/Applications/Codex.app')]
 hits=[]
 for root in roots:
  if not os.path.isdir(root):continue
  base=root.count(os.sep)
  for folder,dirs,files in os.walk(root):
   if folder.count(os.sep)-base>=4 or folder.endswith('.lproj'):dirs[:]=[]
   if 'codex' in files:
    path=os.path.join(folder,'codex')
    if os.access(path,os.X_OK):hits.append(path)
 # prefer a bin/ launcher over helper copies
 return sorted(hits,key=lambda p:('/bin/' not in p,len(p)))[0] if hits else None

def codex_binary():
 """Find the Codex CLI even when the server was started from Finder/Dock, where ~/.zshrc PATH is not loaded."""
 global _CODEX
 if _CODEX and os.path.exists(_CODEX):return _CODEX
 home=os.path.expanduser('~')
 if not shutil.which('codex'):merge_login_path()
 found=shutil.which('codex') or next((p for p in [os.environ.get('ORACLE_CODEX',''),'/opt/homebrew/bin/codex','/usr/local/bin/codex',home+'/.local/bin/codex',home+'/.npm-global/bin/codex',home+'/.bun/bin/codex',home+'/.volta/bin/codex','/Applications/Codex.app/Contents/Resources/codex'] if p and os.access(p,os.X_OK)),None)
 if not found:found=bundled_codex()
 if not found:raise RuntimeError('找不到 Codex 程式（codex）。請確認已安裝 Codex CLI；如安裝在特別位置，可在 start.command 設定 ORACLE_CODEX=完整路徑。')
 _CODEX=found;return found

def model(prompt,effort="medium",timeout=480):
 folder=STATE/'model';folder.mkdir(parents=True,exist_ok=True)
 out=folder/(uuid.uuid4().hex+'.txt')
 # No shell, apps, subagents or web search in the model process. Input data is untrusted.
 cmd=[codex_binary(),'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','-s','read-only','--disable','shell_tool','--disable','apps','--disable','multi_agent','-c','web_search="disabled"','-c','model_reasoning_effort="'+effort+'"','-C',str(folder),'--json','-o',str(out),'-']
 env={k:v for k,v in os.environ.items() if k not in ('COINGECKO_DEMO_API_KEY','EDGAR_USER_EMAIL')}
 try:
  p=run_tracked(cmd,prompt,timeout,env=env)
  if p.returncode or not out.exists():raise RuntimeError('Codex 未完成回覆，請檢查登入或用量後再試')
  return out.read_text().strip()
 except subprocess.TimeoutExpired as exc:
  events={}
  for line in (exc.stdout or b'').decode('utf-8','replace').splitlines() if isinstance(exc.stdout,bytes) else (exc.output or exc.stdout or '').splitlines():
   try:
    kind=json.loads(line).get('type','unknown');events[kind]=events.get(kind,0)+1
   except ValueError:pass
  persist(STATE/'model-failures'/(out.stem+'.json'),{'time':now(),'reason':f'{timeout}-second timeout','event_counts':events,'output_file_existed':out.exists(),'prompt_characters':len(prompt)})
  raise RuntimeError(f'模型回覆逾時（{timeout}秒）；市場數據已保存，可接續報告')
 finally:out.unlink(missing_ok=True)
def get_source(name,plan):
 settings=config()['fetch'];cached=STATE/'provider-cache'/(cache_key(name,plan)+'.json')
 # Resource observatory checks always make a fresh request.
 cache_allowed=plan.get('layer')!='連通測試'
 if cache_allowed and cached.exists():
  try:
   row=json.loads(cached.read_text())
   if usable(row,settings['cache_seconds'],now()):return {**row,'cache_hit':True,'request_attempts':[]}
  except (ValueError,OSError):pass
 attempts=[]
 for attempt in range(settings['max_retries']+1):
  started=time.monotonic();begin=now();timed_out=False
  if CANCEL.is_set():
   return {'id':name,'name':CATALOG[name][0],'url':CATALOG[name][2],'status':'error','error':'分析已停止，未取數','checked_at':now(),'cache_hit':False,'request_attempts':attempts}
  try:
   p=run_tracked([sys.executable,str(ROOT/'sources.py'),name],json.dumps(plan),settings['timeout_seconds'])
   if p.returncode:raise ValueError('資料程序未成功完成')
   row=json.loads(p.stdout)
  except subprocess.TimeoutExpired:
   timed_out=True;row={'id':name,'name':CATALOG[name][0],'url':CATALOG[name][2],'status':'error','error':str(settings['timeout_seconds'])+'秒逾時','checked_at':now()}
  except Exception:row={'id':name,'name':CATALOG[name][0],'url':CATALOG[name][2],'status':'error','error':'取數失敗','checked_at':now()}
  attempts.append({'started_at':begin,'ended_at':now(),'seconds':round(time.monotonic()-started,3),'retry':attempt>0,'timed_out':timed_out,'status':row['status']})
  if row['status']=='ok':break
 row.update(cache_hit=False,request_attempts=attempts)
 with LOCK:
  STATUS[name]={k:v for k,v in row.items() if k!='data'}
  persist(STATE/'status.json',STATUS)
  if cache_allowed and row['status']=='ok':persist(cached,row)
 return row

def update(job,**kw):
 with LOCK:
  JOBS[job].update(kw)
  persist(STATE/'reports'/(job+'.json'),JOBS[job])
def record_timing(job,kind,entry):
 with LOCK:
  timing=JOBS[job].setdefault('timing',{'version':1,'started_at':JOBS[job].get('resume_started_at',JOBS[job].get('created_at')),'unit':'Unicode characters','stages':[],'models':[],'providers':[]})
  timing[kind].append(entry)
  print(json.dumps({'event':'analysis_timing','job':job,'kind':kind,**entry},ensure_ascii=False),flush=True)
  persist(STATE/'reports'/(job+'.json'),JOBS[job])

def stage_timing(job,name):
 return measurement(lambda kind,e:record_timing(job,kind,e),'stages',name)

def measured_signal(job,signal):
 deadline=JOBS[job].get('deadline_at')
 if deadline and datetime.datetime.fromisoformat(deadline)<=datetime.datetime.now(datetime.timezone.utc):
  return {'id':signal['id'],'name':signal.get('label',signal['id']),'provider':signal['source'],'status':'error','error':'本輪時間預算已用完，尚未發出此取數請求','checked_at':now(),'tier':signal.get('tier'),'layer':signal.get('layer'),'data':{}}
 with LOCK:
  retry=any(e.get('signal_id')==signal['id'] for e in JOBS[job].get('timing',{}).get('providers',[]))
 with measurement(lambda kind,e:record_timing(job,kind,e),'providers',signal['source'],signal_id=signal['id'],retry=retry,timeout_seconds=config()['fetch']['timeout_seconds']) as entry:
  row=query_signal(signal)
  entry.update(status=row['status'],timed_out=any(x['timed_out'] for x in row.get('request_attempts',[])),retry=retry or any(x['retry'] for x in row.get('request_attempts',[])),cache_hit=row.get('cache_hit',False),attempts=row.get('request_attempts',[]))
  row['request_timing']=entry
  return row

def phase(job,index,detail=''):
 check_cancel()
 with LOCK:
  steps=JOBS[job].setdefault('pipeline',[])
  stamp=now()
  for item in steps:
   if item['status']=='running':
    item.update(status='done',ended_at=stamp,seconds=round((datetime.datetime.fromisoformat(stamp)-datetime.datetime.fromisoformat(item['started_at'])).total_seconds(),3))
  item={'index':index,'status':'running' if index<7 else 'done','started_at':stamp,'detail':detail}
  if index==7:item.update(ended_at=stamp,seconds=0)
  steps.append(item)
  update(job,pipeline=steps)

def query_signal(signal):
 row=get_source(signal['source'],signal)
 if signal['source']=='web' and row.get('status')=='ok':row={**row,'status':'lead','note':'只有線索／無可用數據'}
 return {**row,'provider':signal['source'],'id':signal['id'],'name':signal['label'],'layer':signal['layer'],'reason':signal['reason'],'horizon':signal['horizon'],'tier':signal.get('tier','background'),'query':{k:v for k,v in signal.items() if k in ('ticker','series','commodity','search')}}

def run_job(job,question,health=False):
 global BUSY
 try:
  if health:
   plan={'signals':[{'id':n,'source':n,'label':CATALOG[n][0],'layer':'連通測試','reason':'代表性請求','horizon':'目前回應','search':'Fed decision','ticker':'600519' if n=='eastmoney' else 'SPY','series':'BAMLH0A0HYM2' if n=='fred' else 'HIBOR_1M' if n=='hkma' else 'KXFEDDECISION'} for n in CATALOG if n!='coingecko']}
  else:
   phase(job,1)
   update(job,stage='01 理解問題及規劃多維訊號',step=1)
   preset=preset_plan(question,now())
   with stage_timing(job,'signal_planning'):
    plan=validate_plan(preset) if preset else plan_with_retry(job,question)
  if not health:
   plan=validate_plan(trim_to_budget(route_answer(question,apply_policy(question,plan))))
   phase(job,2)
  update(job,stage='02 並行取得市場訊號',step=2,plan=plan)
  rows=[]
  with stage_timing(job,'data_collection'):
   with concurrent.futures.ThreadPoolExecutor(max_workers=config()['fetch']['workers']) as pool:
    futures={pool.submit(measured_signal,job,signal):signal['id'] for signal in plan['signals']}
    for f in concurrent.futures.as_completed(futures):
     rows.append(f.result());update(job,sources=rows.copy(),stage=f'02 取得訊號 {len(rows)} / {len(futures)}')
  if not health:
   phase(job,3)
   update(job,stage='03 計算跨市場關係，檢查證據缺口',step=3)
   with stage_timing(job,'statistics'):
    quantitative=cross_market(rows);update(job,quantitative=quantitative)
   refinement="""Inspect the actual financial data coverage and gaps below. Return ONLY JSON {"assessment":"繁體中文：目前最重要缺口、需要補甚麼及為何", "signals":[up to6 new signals using the exact planner schema]}.
Find evidence that could DISCONFIRM the initial story. Prefer numerical series and independent financial channels, not more similar stocks. If current coverage is adequate return signals: []. Never use analyst/news/social opinions. Existing successful queries must not repeat. You may retry a failed query once; reuse the same query parameters. Do not invent APIs. Max total40. Use FRED credit/real yields instead of unverified web snippets, and independent risk channels or matching event queries as needed. This is one bounded second collection round, not ongoing monitoring. Assess data gaps only; do not dictate the final probability. The final report may offer an explicitly subjective estimate with assumptions even when a calibrated mapping is unavailable."""
   requests=[]
   try:
    core_ok=[r for r in rows if r.get('tier')=='core'];core_ok=bool(core_ok) and all(r.get('status')=='ok' for r in core_ok)
    if plan.get('preset'):review={'assessment':'依固定區域訊號清單完成交叉核對；缺失資料如實保留，不以重複規劃延長流程。','signals':[]}
    elif core_ok:review={'assessment':'核心訊號全部取得；略過補查以縮短分析時間，缺口如實保留。','signals':[]}
    else:
     review=traditional(parse_json(measured_model(job,'補查規劃',PLANNER+'\n'+refinement+'\n'+json.dumps({'now':now(),'question':question,'existing_plan':plan,'data':[compact_row(r,200) for r in evidence_for_model(rows)]},ensure_ascii=False),effort='low',timeout=180)))
    additions=review.get('signals',[])
    if not isinstance(additions,list) or len(additions)>6:raise ValueError('補查數目超出範圍')
    if additions:plan,requests=prepare_supplement(plan,rows,additions)
   except (ValueError,TypeError,KeyError,AttributeError,RuntimeError) as exc:
    review={'assessment':'補查規劃未通過核對；本次只使用第一輪已取得的證據，缺口保留。'}
    update(job,review_warning=str(exc)[:200])
   check_cancel()
   if requests:
    row_by_id={r['id']:r for r in rows}
    update(job,plan=plan,review=review.get('assessment',''),stage='03 補查反證及重試缺失訊號',supplemental_queries=[{'id':s['id'],'kind':'retry' if s['id'] in row_by_id else 'new'} for s in requests])
    with concurrent.futures.ThreadPoolExecutor(max_workers=config()['fetch']['workers']) as pool:
     for row in pool.map(lambda signal:measured_signal(job,signal),requests):
      previous=row_by_id.get(row['id'])
      if previous:
       row['previous_attempt']={k:v for k,v in previous.items() if k not in ('data','reason','horizon')}
       rows=[r for r in rows if r['id']!=row['id']]
      rows.append(row);update(job,sources=rows.copy())
   else:update(job,review=review.get('assessment',''))
   with stage_timing(job,'statistics'):
    quantitative=cross_market(rows);update(job,quantitative=quantitative)
  if not health:
   with stage_timing(job,'anomaly_detection'):
    promotions=classify(rows,quantitative,plan.get('routing_profile','general'))
    update(job,promotions=promotions)
  # Retain plan order in final report, irrespective of network completion order.
  order={s['id']:i for i,s in enumerate(plan['signals'])};rows.sort(key=lambda r:order[r['id']]);update(job,sources=rows)
  if health:update(job,status='done',stage='資源檢查完成',answer='來源連通檢查完成。此檢查只代表目前代表性請求，並非全部資料與商用授權通過。')
  elif not any(r['status']=='ok' for r in rows):update(job,status='done',stage='資料不足',answer='今次未取得可用資料，未生成預測。請查看來源錯誤並重試。')
  else:
   finish_report(job,question,plan,rows,quantitative)
  with LOCK:
   if JOBS[job].get('report'):persist(STATE/'last-report.json',JOBS[job])
 except Exception as e:record_failure(job,e)
 finally:
  with LOCK:
   JOBS[job]['completed_at']=now()
   if JOBS[job].get('timing'):
    JOBS[job]['timing']['completed_at']=JOBS[job]['completed_at']
   persist(STATE/'reports'/(job+'.json'),JOBS[job])
   if JOBS[job].get('report'):persist(STATE/'last-report.json',JOBS[job])
   BUSY=False

def measured_model(job,phase,prompt,components=None,effort='medium',timeout=480):
 deadline=JOBS[job].get('deadline_at')
 if deadline:
  remaining=(datetime.datetime.fromisoformat(deadline)-datetime.datetime.now(datetime.timezone.utc)).total_seconds()
  if remaining<=0:raise RuntimeError('本輪分析時間預算已用完；已完成的草稿及證據已保存，可接續未完成部分。')
  timeout=min(timeout,max(.1,remaining))
 # Every Codex call in flight is listed (layers run in parallel) so the page can warn about long waits.
 key=uuid.uuid4().hex[:8];stamp=now()
 with LOCK:
  active=dict(JOBS[job].get('models_active') or {});active[key]={'phase':phase,'started_at':stamp,'timeout_seconds':timeout}
  update(job,model_phase=phase,model_phase_started_at=stamp,models_active=active)
 try:
  with measurement(lambda kind,e:record_timing(job,kind,e),'models',phase,input_characters=len(prompt),output_characters=None,components=components or {'unclassified':len(prompt)}) as entry:
   raw=model(prompt,effort=effort,timeout=timeout)
   entry['output_characters']=len(raw)
   return raw
 finally:
  with LOCK:
   active=dict(JOBS[job].get('models_active') or {});active.pop(key,None);update(job,models_active=active)

PLANNING_TIMEOUT=int(os.environ.get('ORACLE_PLANNING_TIMEOUT','240'))  # override only for local testing
def plan_with_retry(job,question):
 """Plan the signals; one automatic retry if Codex times out, fails, or returns an unusable plan."""
 last=None
 for attempt in (1,2):
  check_cancel()
  if attempt==2:update(job,stage='01 規劃未成功，自動重試（第 2 次）',planning_retry=1,planning_first_error=plain_error(last))
  try:
   raw=measured_model(job,'訊號規劃' if attempt==1 else '訊號規劃（自動重試）',PLANNER+'\nToday: '+now()+'\nQuestion: '+json.dumps(question,ensure_ascii=False),effort='low',timeout=PLANNING_TIMEOUT)
   proposed=route_plan(question,traditional(parse_json(raw)))
   if isinstance(proposed,dict) and isinstance(proposed.get('signals'),list) and not proposed['signals']:raise NoMarketData()
   return validate_plan(proposed)
  except (Cancelled,NoMarketData):raise
  except (RuntimeError,ValueError,TypeError,KeyError,AttributeError) as exc:
   if CANCEL.is_set():raise Cancelled()
   last=exc
 raise PlanningFailed('Codex 規劃分析時未成功（已自動重試一次）：'+plain_error(last))

def measured_review(job,prompt):
 from evaluation import AUDITOR
 phase='最後複核' if '最後複核' in JOBS[job].get('stage','') else '內容核對' if prompt.startswith(AUDITOR) else '欄位修正'
 separator=prompt.find('\n{')
 components={'instructions':separator+1,'context_and_report':len(prompt)-separator-1} if separator>=0 else None
 return measured_model(job,phase,prompt,components,effort='low',timeout=240)

def finish_report(job,question,plan,rows,quantitative):
 phase(job,4)
 update(job,stage='04 綜合反證、機率敏感度及完整報告',step=4)
 with stage_timing(job,'liquidity_anchor'):
  counts=signal_counts(plan,rows)
  anchors=liquidity_anchors(rows,question,now(),plan['horizon']);update(job,liquidity_anchors=anchors,counts=counts)
 if JOBS[job].get('generated_report'):
  report=validate_report(report_language(JOBS[job]['generated_report'],rows),rows)
 else:
  from research_agents import settings as research_settings
  agent_settings=research_settings()
  settings={'agent':('low',max(1,min(180,int(agent_settings.get('timeout_seconds',90))))),'layer':('low',180),'synthesis':('medium',360),'repair':('low',180)}
  def call(kind,label,prompt):
   effort,timeout=settings[kind]
   return measured_model(job,label,prompt,{'total':len(prompt)},effort=effort,timeout=timeout)
  update(job,stage='04 多角色研究：直接證據、跨市場及反證' if agent_settings.get('enabled') else '04 平行分析各層及綜合結論')
  def publish_draft(draft):
   phase(job,5);update(job,generated_report=draft,draft_ready_at=now())
   phase(job,6);update(job,stage='06 草稿已完成 · 宏觀背景與核對')
  report,synth_prompt=generate_report(question,JOBS[job].get('created_at',now()),report_plan(plan),rows,quantitative,counts,anchors,call,plan,lambda value,rs:validate_report(materialize_answer(materialize(value,rs,required=plan.get('answer_spec',{}).get('type','probability')=='probability',anchors=anchors),rs,plan.get('answer_spec')),rs),lambda value:report_language(restore_observations(value,rows),rows),publish_draft=publish_draft,saved_parts=JOBS[job].get('report_parts'),checkpoint=lambda parts:update(job,report_parts=parts),agent_settings=agent_settings)
  persist(STATE/'prompts'/(job+'.json'),{'prompt':synth_prompt})
  update(job,report_prompt_hash=hashlib.sha256(synth_prompt.encode()).hexdigest(),prompt_characters=len(synth_prompt))
 if not JOBS[job].get('draft_ready_at'):
  phase(job,5);update(job,generated_report=report,draft_ready_at=now());phase(job,6)
 else:update(job,generated_report=report,draft_revision=JOBS[job].get('draft_revision',0)+1)
 report,audit,revisions=audit_and_revise(report,rows,synthesis_context(question,now(),report_plan(plan),rows,quantitative,counts,anchors),lambda p:measured_review(job,p),lambda value,rs:validate_report(materialize_answer(materialize(value,rs,required=bool(report.get('probability',{}).get('calculation')),anchors=anchors),rs,plan.get('answer_spec')),rs),lambda value:report_language(restore_observations(value,rows),rows),lambda stage:update(job,stage=stage),lambda checkpoint:update(job,**checkpoint),JOBS[job].get('prior_audit'),focused=True)
 report['timing']=JOBS[job].get('timing',{})
 report['coverage_analysis']=report['coverage']
 report['coverage']=coverage_text(counts)
 audit['structural']=assess({**JOBS[job],'report':report})
 update(job,quality_audit=audit,revisions=revisions)
 phase(job,7)
 update(job,status='done',stage='分析完成',step=7,report=report,answer=report['conclusion'])

def resume_report_job(job):
 global BUSY
 try:
  d=JOBS[job]
  existing={r['id'] for r in d['sources']}
  missing=[s for s in d['plan']['signals'] if s['id'] not in existing]
  if missing:
   phase(job,2);update(job,stage='補取新增的目標基準，沿用已保存的其他證據')
   for signal in missing:
    row=measured_signal(job,signal)
    update(job,sources=[*JOBS[job]['sources'],row])
   update(job,quantitative=cross_market(JOBS[job]['sources']))
  finish_report(job,d['question'],d['plan'],d['sources'],d.get('quantitative') or cross_market(d['sources']))
 except Exception as exc:record_failure(job,exc,'報告未完成；數據已保存')
 finally:
  with LOCK:
   JOBS[job]['completed_at']=now()
   if JOBS[job].get('timing'):
    JOBS[job]['timing']['completed_at']=JOBS[job]['completed_at']
   persist(STATE/'reports'/(job+'.json'),JOBS[job])
   if JOBS[job].get('report'):persist(STATE/'last-report.json',JOBS[job])
   BUSY=False

def resume_job(rid):
 global BUSY
 if not re.fullmatch(r'[a-f0-9]{32}',rid):raise ValueError('無效工作編號')
 with LOCK:
  if BUSY:raise RuntimeError('已有工作進行中')
  path=STATE/'reports'/(rid+'.json')
  if not path.exists():raise ValueError('找不到已保存數據')
  d=json.loads(path.read_text())
  if (d.get('status')=='done' and d.get('quality_audit',{}).get('passed',True)) or not d.get('plan') or not any(r.get('status')=='ok' for r in d.get('sources',[])):raise ValueError('沒有可接續的資料')
  job=uuid.uuid4().hex
  if d.get('revisions') and d['revisions'][0].get('audit'):d['prior_audit']=d['revisions'][0]['audit']
  for key in ('error','completed_at','model_timings','timing','pipeline','draft_ready_at','report','quality_audit','revisions'):d.pop(key,None)
  if d['plan'].get('core_variable'):d['plan']=route_answer(d['question'],d['plan'])
  d.pop('preview',None)
  d.update(id=job,resumed_from=rid,status='running',stage='沿用已保存數據，接續報告',deadline_at=analysis_deadline(),resume_started_at=now(),method_version=METHOD_VERSION,build_id=BUILD_ID)
  JOBS[job]=d;BUSY=True;CANCEL.clear();persist(STATE/'reports'/(job+'.json'),d)
  threading.Thread(target=resume_report_job,args=(job,),daemon=True).start()
  return job


def analysis_deadline():
 return (datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=config().get('workflow',{}).get('max_seconds',600))).isoformat()

def new_job(question,health=False):
 global BUSY
 with LOCK:
  if BUSY:raise RuntimeError('已有一項工作進行中，請等候完成')
  BUSY=True;CANCEL.clear();job=uuid.uuid4().hex
  if len(JOBS)>30:
   oldest=next(iter(JOBS));JOBS.pop(oldest,None)
  JOBS[job]={'id':job,'question':question,'status':'running','stage':'準備中','sources':[],'deadline_at':analysis_deadline(),'created_at':now(),'method_version':METHOD_VERSION,'build_id':BUILD_ID}
 threading.Thread(target=run_job,args=(job,question,health),daemon=True).start();return job

def read_reports():
 """Saved jobs, newest first. A damaged file is skipped instead of breaking the page."""
 out=[]
 for path in sorted((STATE/'reports').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True):
  try:out.append(json.loads(path.read_text()))
  except (OSError,ValueError):continue
 return out

def recoverable():
 reports=read_reports()
 resolved={d.get('resumed_from') for d in reports if d.get('status')=='done'}
 with LOCK:running={j['id'] for j in JOBS.values() if j.get('status')=='running'}
 for d in reports:
  if d.get('id') in resolved or d.get('no_market_data'):continue
  # A 'running' file with no live worker was interrupted (server closed); a live one is not "unfinished".
  if d.get('status')=='running' and d.get('id') in running:continue
  if (d.get('status') in ('error','running') or (d.get('status')=='done' and d.get('quality_audit',{}).get('passed') is False)) and d.get('plan') and any(r.get('status')=='ok' for r in d.get('sources',[])):
   return {k:d.get(k) for k in ('id','question','created_at','stage')}
 return {}

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def send(self,data,status=200,ctype='application/json; charset=utf-8'):
  body=json.dumps(data,ensure_ascii=False).encode() if isinstance(data,(dict,list)) else data
  self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");self.end_headers();self.wfile.write(body)
 def valid(self):return allowed_request(self.headers.get('Host'),self.headers.get('Origin'),self.headers.get('X-Oracle-Token',''),TOKEN)
 def do_GET(self):
  try:return self.get()
  except (BrokenPipeError,ConnectionResetError):pass
  except Exception as exc:
   print('GET failed:',self.path,repr(exc),file=sys.stderr,flush=True)
   try:self.send({'error':'伺服器處理請求時出錯，請重新整理；如持續出現請重新啟動數字先知。'},500)
   except OSError:pass
 def get(self):
  if self.headers.get('Host') not in {f'127.0.0.1:{PORT}',f'localhost:{PORT}'}:return self.send({'error':'Invalid host'},403)
  route=urlparse(self.path).path
  static={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
  if route in static:
   p=ROOT/'static'/static[route];body=p.read_bytes()
   if route=='/':body=body.replace(b'__CSRF_TOKEN__',TOKEN.encode())
   return self.send(body,ctype={'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}[route])
  if not self.valid():return self.send({'error':'頁面授權失效，請重新整理'},403)
  if route=='/api/status':
   with LOCK:
    conf=json.loads((STATE/'config.json').read_text()) if (STATE/'config.json').exists() else {}
    return self.send({'sources':[{'id':k,'name':v[0],'description':v[1],'url':v[2],**STATUS.get(k,{'status':'unchecked'})} for k,v in CATALOG.items()],'busy':BUSY,'active_job':next((j['id'] for j in JOBS.values() if j['status']=='running'),None),'coingecko_configured':bool(conf.get('COINGECKO_DEMO_API_KEY')),'model':'Codex · 現有 ChatGPT 登入','cme':'disabled'})
  if route=='/api/last':return self.send(saved_report(STATE/'last-report.json') if (STATE/'last-report.json').exists() else {})
  if route=='/api/recoverable':return self.send(recoverable())
  if route=='/api/history':
   return self.send([{k:d.get(k) for k in ('id','question','created_at','completed_at','revision_of')} for d in read_reports()[:40] if d.get('report')])
  if route.startswith('/api/pdf/'):
   from pdf_export import export_pdf
   rid=route.split('/')[-1]
   if not re.fullmatch(r'[a-f0-9]{32}',rid):return self.send({'error':'無效報告編號'},400)
   with LOCK:
    current=JOBS.get(rid)
    data=json.loads(json.dumps(current)) if current else None
   path=STATE/'reports'/(rid+'.json')
   if data is None and path.exists():data=saved_report(path)
   if not data:return self.send({'error':'報告不存在'},404)
   if not data.get('report') and data.get('generated_report'):
    data={**data,'report':data['generated_report'],'preview':True}
   if not data.get('report'):return self.send({'error':'報告尚未產生，請等待草稿完成'},409)
   try:content=export_pdf(data,PORT)
   except (ValueError,RuntimeError) as exc:return self.send({'error':str(exc)},503)
   self.send_response(200);self.send_header('Content-Type','application/pdf');self.send_header('Content-Disposition','attachment; filename="digital-oracle-'+rid[:8]+'.pdf"');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(content);return
  if route.startswith('/api/reports/'):
   rid=route.split('/')[-1]
   if not re.fullmatch(r'[a-f0-9]{32}',rid):return self.send({'error':'無效報告編號'},400)
   path=STATE/'reports'/(rid+'.json')
   if not path.exists():return self.send({'error':'報告不存在'},404)
   return self.send(saved_report(path))
  if route.startswith('/api/jobs/'):
   with LOCK:
    view=job_view(route.split('/')[-1])
    if view.get('status')=='running' and 'brief=1' in urlparse(self.path).query:
     view={**{k:v for k,v in view.items() if k!='report_parts'},'sources':[{k:v for k,v in r.items() if k!='data'} for r in view.get('sources',[])]}
    return self.send(view)
  return self.send({'error':'Not found'},404)
 def do_POST(self):
  if not self.valid():return self.send({'error':'Invalid origin or token'},403)
  if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.send({'error':'需要 JSON'},415)
  try:
   size=int(self.headers.get('Content-Length','0')) if (self.headers.get('Content-Length') or '0').isdigit() else -1
   if not 0<size<=8192:raise ValueError('請求過大或無內容')
   body=json.loads(self.rfile.read(size));route=urlparse(self.path).path
   if not isinstance(body,dict):raise ValueError('需要JSON物件')
   if route=='/api/resume':return self.send({'id':resume_job(body.get('id',''))},202)
   if route=='/api/cancel':cancel_job(body.get('id',''));return self.send({'stopping':True},202)
   if route=='/api/ask':
    q=body.get('question','')
    if not isinstance(q,str) or not 3<=len(q.strip())<=1200:raise ValueError('請輸入 3 至 1200 字的問題')
    return self.send({'id':new_job(q.strip())},202)
   if route=='/api/check':return self.send({'id':new_job('資源連通檢查',True)},202)
   if route=='/api/key':
    key=body.get('key','').strip()
    if not re.fullmatch(r'[A-Za-z0-9_\-]{10,160}',key):raise ValueError('API key 格式不正確')
    with LOCK:
     if BUSY:raise RuntimeError('請先等候目前分析完成')
     conf=json.loads((STATE/'config.json').read_text()) if (STATE/'config.json').exists() else {}
     conf['COINGECKO_DEMO_API_KEY']=key;persist(STATE/'config.json',conf)
    row=get_source('coingecko',{'ticker':'BTC','search':'bitcoin'})
    return self.send({'status':row['status'],'message':'已安全保存在本機，現價及行情實測成功。' if row['status']=='ok' else '已保存在本機，但接口仍未通過：'+row.get('error','')})
   return self.send({'error':'Not found'},404)
  except json.JSONDecodeError:return self.send({'error':'輸入格式不正確，請檢查後再試'},400)
  except ValueError as e:return self.send({'error':str(e) or '輸入格式不正確，請檢查後再試'},400)
  except TypeError:return self.send({'error':'輸入格式不正確，請檢查後再試'},400)
  except RuntimeError as e:return self.send({'error':str(e)},409)

def main():
 STATE.mkdir(parents=True,exist_ok=True);STATE.chmod(0o700)
 if (STATE/'status.json').exists():STATUS.update(json.loads((STATE/'status.json').read_text()))
 try:print('Codex:',codex_binary(),flush=True)
 except RuntimeError as exc:print('警告：',exc,flush=True)
 print(f'Oracle ready: http://127.0.0.1:{PORT}',flush=True)
 import signal,atexit
 def shutdown(signum=None,frame=None):
  stop_children()
  raise SystemExit(0)
 # Ctrl+C, closing the Terminal window (SIGHUP) or kill (SIGTERM) also end any Codex/data processes.
 for sig in (signal.SIGTERM,signal.SIGHUP):signal.signal(sig,shutdown)
 atexit.register(stop_children)
 try:ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
 except KeyboardInterrupt:stop_children()
if __name__=='__main__':main()
