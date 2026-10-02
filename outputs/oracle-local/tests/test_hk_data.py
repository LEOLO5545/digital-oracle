"""HKMA and southbound adapters: parsing, future-date exclusion, and routing off blocked web search."""
import sys,unittest,datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hk_data import parse_hkma,parse_southbound,HKMA_SERIES
from signal_policy import apply_policy,reroute_hk
from analysis import validate_plan
from quant import quality_summary,cross_market

AS_OF=datetime.date(2026,10,2)
def liquidity(n=30):
 days=[AS_OF-datetime.timedelta(days=i) for i in range(n)]
 recs=[{'end_of_date':d.isoformat(),'hibor_overnight':3.1+i/100,'hibor_fixing_1m':3.5+i/200,'closing_balance':54000+i*10,'cu_weakside':7.85,'cu_strongside':7.75} for i,d in enumerate(days)]
 recs.insert(0,{'end_of_date':'2026-10-09','hibor_overnight':9.9,'hibor_fixing_1m':9.9,'closing_balance':1})  # future-dated must be ignored
 recs.append({'end_of_date':'2026-08-01','hibor_overnight':None,'hibor_fixing_1m':None,'closing_balance':None})
 return {'header':{'success':True,'err_code':'0000'},'result':{'datasize':len(recs),'records':recs}}
# Real response captured 2026-10-02 from datacenter-web.eastmoney.com (MUTUAL_TYPE 006 = 002 + 004)
REAL_SB=[('2026-09-30',6863.61,69926.87),('2026-09-29',14.629999999999,64015.07),('2026-09-28',-6553.87,75387.97)]
def southbound(extra=0):
 rows=[{'MUTUAL_TYPE':'006','TRADE_DATE':d+' 00:00:00','NET_DEAL_AMT':v,'DEAL_AMT':t} for d,v,t in REAL_SB]
 rows+=[{'MUTUAL_TYPE':'006','TRADE_DATE':(datetime.date(2026,9,27)-datetime.timedelta(days=i)).isoformat()+' 00:00:00','NET_DEAL_AMT':100.0,'DEAL_AMT':1.0} for i in range(extra)]
 rows.append({'MUTUAL_TYPE':'002','TRADE_DATE':'2026-09-30 00:00:00','NET_DEAL_AMT':5094.33})
 return {'success':True,'code':0,'result':{'data':rows,'count':len(rows)}}

def plan(signals):
 return {'core_variable':'香港樓價','horizon':'12個月','priceability':'代理','signals':signals}
def web(i,search,label='x'):
 return {'id':i,'source':'web','search':search,'label':label,'layer':'資金','reason':'r','horizon':'h'}

class HkDataTests(unittest.TestCase):
 def test_hkma_series_parse_and_future_excluded(self):
  d=parse_hkma('HIBOR_1M',liquidity(),AS_OF)
  self.assertEqual(d['statistics']['last_date'],'2026-10-02');self.assertEqual(d['statistics']['latest'],3.5)
  self.assertNotIn('2026-10-09',d['observations'])
  agg=parse_hkma('AGG_BALANCE',liquidity(),AS_OF);self.assertEqual(agg['peg_band']['cu_weakside'],7.85);self.assertEqual(agg['units'],'港元百萬')
 def test_hkma_failure_and_unknown_series(self):
  with self.assertRaises(ValueError):parse_hkma('HIBOR_1M',{'header':{'success':False,'err_msg':'x'}},AS_OF)
  with self.assertRaises(ValueError):parse_hkma('HIBOR_1M',{'result':{'records':[]}},AS_OF)
  with self.assertRaises(ValueError):parse_hkma('LIBOR',liquidity(),AS_OF)
 def test_hibor_fixing_endpoint_fields(self):
  recs=[{'end_of_day':(AS_OF-datetime.timedelta(days=i)).isoformat(),'ir_3m':3.9-i/100} for i in range(10)]
  d=parse_hkma('HIBOR_3M',{'result':{'records':recs}},AS_OF);self.assertEqual(d['statistics']['latest'],3.9)
 def test_southbound_real_sample(self):
  d=parse_southbound(southbound(25),AS_OF)
  self.assertEqual(d['statistics']['last_date'],'2026-09-30');self.assertAlmostEqual(d['statistics']['latest'],6863.61)
  self.assertAlmostEqual(d['cumulative_net_buy']['last_5_days'],6863.61+14.63-6553.87+200,places=1)
  self.assertEqual(d['latest_turnover'],69926.87)
  with self.assertRaises(ValueError):parse_southbound({'success':False},AS_OF)
  with self.assertRaises(ValueError):parse_southbound(southbound(0),AS_OF)  # fewer than 5 days
 def test_quality_dates(self):
  self.assertEqual(quality_summary('hkma',parse_hkma('HIBOR_1M',liquidity(),AS_OF),AS_OF)['observation_date'],'2026-10-02')
 def test_web_requests_rerouted_to_structured_sources(self):
  # Exactly what the planner produced in the failed 2026-10-02 property run.
  p=reroute_hk(plan([web('hibor_overnight','HKMA overnight HIBOR fixing latest'),web('hibor_one_month','HKMA 1 month HIBOR fixing'),web('hibor_three_month','3-month HIBOR Hong Kong'),web('hkma_aggregate_balance','HKMA aggregate balance latest'),web('southbound_flow','Stock Connect southbound net buying'),web('hk_ccl','Centaline City Leading Index'),web('hk_residential_price','Hong Kong RVD private domestic price index latest')]))
  got={s['id']:(s['source'],s.get('series')) for s in p['signals']}
  self.assertEqual(got['hibor_overnight'],('hkma','HIBOR_ON'));self.assertEqual(got['hibor_one_month'],('hkma','HIBOR_1M'))
  self.assertEqual(got['hibor_three_month'],('hkma','HIBOR_3M'));self.assertEqual(got['hkma_aggregate_balance'],('hkma','AGG_BALANCE'))
  self.assertEqual(got['southbound_flow'][0],'southbound');self.assertEqual(got['hk_housing_baseline'][0],'rvd_hk_housing');self.assertEqual(got['hk_ccl'][0],'web')
 def test_hk_policy_adds_hkma_once_and_plan_validates(self):
  p=apply_policy('香港樓價未來12個月會升還是跌？',plan([web('h1','1 month HIBOR')]))
  hk=[(s['source'],s.get('series')) for s in p['signals'] if s['source'] in ('hkma','southbound')]
  self.assertEqual(len(hk),len(set(hk)));self.assertIn(('hkma','AGG_BALANCE'),hk);self.assertIn(('hkma','HIBOR_1M'),hk)
  v=validate_plan(p);self.assertTrue(any(s['source']=='southbound' for s in v['signals']))
  self.assertEqual({s['id'] for s in v['signals'] if s['source']=='hkma' and s['series']=='HIBOR_1M'},{'h1'})
 def test_peg_question_uses_hk_profile(self):
  p=apply_policy('港元同美元幾時會脫鈎',plan([web('x','USD HKD spot')]));self.assertEqual(p['routing_profile'],'hk_market')
 def test_unknown_hkma_series_rejected_not_fatal(self):
  v=validate_plan(plan([{'id':'a','source':'hkma','series':'LIBOR','label':'x','layer':'l','reason':'r','horizon':'h'},{'id':'b','source':'hkma','series':'HIBOR_1M','label':'x','layer':'l','reason':'r','horizon':'h'}]))
  self.assertEqual([s['id'] for s in v['signals']],['b'])
 def test_hibor_feeds_rate_to_price_pairs(self):
  closes={(AS_OF-datetime.timedelta(days=i)).isoformat():100+i%7 for i in range(1,60)}
  hib=parse_hkma('HIBOR_1M',liquidity(60),AS_OF)
  rows=[{'id':'h','provider':'hkma','status':'ok','data':hib},{'id':'hsi','provider':'yahoo','status':'ok','data':{'symbol':'^HSI','closes':closes}}]
  pairs=cross_market(rows)['rate_change_price_return_pairs'];self.assertEqual([(p['a'],p['b']) for p in pairs],[('h','hsi')])

 def test_fetch_uses_shared_cache_and_falls_back_to_bulletin(self):
  import tempfile,hk_data
  from unittest.mock import patch
  bulletin={'header':{'success':True},'result':{'records':[{'end_of_day':(AS_OF-datetime.timedelta(days=30+i)).isoformat(),'ir_overnight':4.0,'ir_1m':2.85-i/100,'ir_3m':3.0} for i in range(10)]}}
  calls=[]
  def fake(url,params,timeout=15,headers=None):
   calls.append(url)
   if 'liquidity' in url:raise TimeoutError('timed out')
   return bulletin
  with tempfile.TemporaryDirectory() as tmp,patch.object(hk_data,'state_dir',return_value=Path(tmp)),patch.object(hk_data,'_get_json',side_effect=fake):
   d=hk_data.fetch_hkma('HIBOR_1M')
   self.assertEqual(d['statistics']['latest'],2.85);self.assertIn('滯後',d['fallback'])
   hk_data.fetch_hkma('HIBOR_3M')  # same bulletin payload is reused from cache
   self.assertEqual(sum('ir-daily' in u for u in calls),1)
   with self.assertRaisesRegex(ValueError,'金管局'):hk_data.fetch_hkma('AGG_BALANCE')  # no fallback for the balance

if __name__=='__main__':unittest.main()

class BudgetTests(unittest.TestCase):
 def test_required_signals_never_push_plan_over_forty(self):
  from signal_policy import trim_to_budget
  from answer_types import route_answer
  sig=lambda i,src='yahoo':{'id':f's{i}','source':src,'ticker':f'T{i}','search':f'q {i}','label':'x','layer':'l','reason':'r','horizon':'h'}
  p=plan([sig(i,'web' if i%5==0 else 'yahoo') for i in range(36)])
  q='香港樓價未來12個月會升還是跌？請推算方向與幅度'
  full=route_answer(q,apply_policy(q,p));self.assertGreater(len(full['signals']),40)
  with self.assertRaises(ValueError):validate_plan(full)  # the old failure
  v=validate_plan(trim_to_budget(full));self.assertEqual(len(v['signals']),40)
  ids={s['id'] for s in v['signals']}
  self.assertIn('hk_housing_baseline',ids);self.assertTrue(all(s['id'] in ids for s in full['signals'] if s.get('tier')=='core'))
  self.assertFalse(any(s['source']=='web' for s in v['signals']))  # web leads dropped first

class CodexPathTests(unittest.TestCase):
 def test_codex_found_from_login_shell_path_when_launched_from_finder(self):
  import server,tempfile,os,stat
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp:
   fake=os.path.join(tmp,'codex');open(fake,'w').write('#!/bin/sh\n');os.chmod(fake,0o755)
   class R:stdout='Welcome banner\n__ORACLE_PATH__/usr/bin:'+tmp+'\n'
   with patch.dict(os.environ,{'PATH':'/usr/bin:/bin'}),patch.object(server,'_CODEX',None),patch.object(server.subprocess,'run',return_value=R()):
    self.assertEqual(server.codex_binary(),fake)
    self.assertIn(tmp,os.environ['PATH'])
 def test_missing_codex_gives_readable_error(self):
  import server,os
  from unittest.mock import patch
  class R:stdout=''
  with patch.dict(os.environ,{'PATH':'/nonexistent','ORACLE_CODEX':''}),patch.object(server,'_CODEX',None),patch.object(server.subprocess,'run',return_value=R()),patch.object(server.os,'access',return_value=False):
   with self.assertRaisesRegex(RuntimeError,'找不到 Codex'):server.codex_binary()
 def test_codex_found_inside_chatgpt_app_bundle(self):
  import server,tempfile,os
  with tempfile.TemporaryDirectory() as tmp:
   for rel in ('codex-cli/bin','codex-cli/codex-path','en.lproj'):os.makedirs(os.path.join(tmp,rel))
   for rel in ('codex-cli/bin/codex','codex-cli/codex-path/codex'):
    p=os.path.join(tmp,rel);open(p,'w').write('#!/bin/sh\n');os.chmod(p,0o755)
   self.assertEqual(server.bundled_codex([tmp]),os.path.join(tmp,'codex-cli/bin/codex'))
   self.assertIsNone(server.bundled_codex([os.path.join(tmp,'missing')]))
