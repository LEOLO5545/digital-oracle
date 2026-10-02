"""Planning retries once, explains failures plainly, and exposes waiting Codex calls to the page."""
import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import server

_TMP=Path(tempfile.mkdtemp(prefix='oracle-retry-test-'));(_TMP/'reports').mkdir()

GOOD=json.dumps({'core_variable':'x','horizon':'2026-09-30 至 2026-12-30','priceability':'p','forecast':None,
 'signals':[{'id':'gold','source':'yahoo','ticker':'GC=F','label':'黃金','layer':'避險','reason':'r','horizon':'h'}]})
EMPTY=json.dumps({'core_variable':'x','horizon':'h','priceability':'none','forecast':None,'signals':[]})

class Base(unittest.TestCase):
 def setUp(self):
  self.state=patch.object(server,'STATE',_TMP);self.state.start();server.CANCEL.clear()
  self.job='f'*32
  with server.LOCK:server.JOBS[self.job]={'id':self.job,'question':'q','status':'running','stage':'x','sources':[],'created_at':server.now()}
 def tearDown(self):self.state.stop();server.CANCEL.clear()

class PlanningRetry(Base):
 def test_timeout_then_success_retries_once(self):
  calls=[]
  def fake(job,phase,prompt,**kw):
   calls.append(phase)
   if len(calls)==1:raise RuntimeError('模型回覆逾時（240秒）；市場數據已保存，可接續報告')
   return GOOD
  with patch.object(server,'measured_model',side_effect=fake):
   plan=server.plan_with_retry(self.job,'黃金未來三個月走勢？')
  self.assertEqual(len(calls),2);self.assertEqual(plan['signals'][0]['id'],'gold')
  self.assertEqual(server.JOBS[self.job]['planning_retry'],1)
 def test_two_failures_give_a_plain_message(self):
  with patch.object(server,'measured_model',side_effect=RuntimeError('模型回覆逾時（240秒）；市場數據已保存，可接續報告')) as m:
   with self.assertRaises(server.PlanningFailed) as ctx:server.plan_with_retry(self.job,'q')
  self.assertEqual(m.call_count,2)
  self.assertIn('Codex',str(ctx.exception));self.assertIn('自動重試',str(ctx.exception))
 def test_invalid_json_is_retried(self):
  with patch.object(server,'measured_model',side_effect=['not json',GOOD]) as m:
   server.plan_with_retry(self.job,'黃金？')
  self.assertEqual(m.call_count,2)
 def test_no_market_data_is_explained_without_wasting_a_retry(self):
  with patch.object(server,'measured_model',return_value=EMPTY) as m:
   with self.assertRaises(server.NoMarketData) as ctx:server.plan_with_retry(self.job,'我去印度嘅機率')
  self.assertEqual(m.call_count,1);self.assertIn('市場數據',str(ctx.exception))
 def test_stop_during_planning_is_not_retried(self):
  def fake(*a,**k):server.CANCEL.set();raise server.Cancelled()
  with patch.object(server,'measured_model',side_effect=fake) as m:
   with self.assertRaises(server.Cancelled):server.plan_with_retry(self.job,'q')
  self.assertEqual(m.call_count,1)

class WaitingCalls(Base):
 def test_active_calls_are_listed_and_cleared(self):
  seen={}
  def fake_model(prompt,effort,timeout):
   seen.update(server.JOBS[self.job].get('models_active',{}));return 'ok'
  with patch.object(server,'model',side_effect=fake_model):
   server.measured_model(self.job,'訊號規劃','p',effort='low',timeout=240)
  entry=list(seen.values())[0]
  self.assertEqual(entry['phase'],'訊號規劃');self.assertEqual(entry['timeout_seconds'],240);self.assertIn('started_at',entry)
  self.assertEqual(server.JOBS[self.job]['models_active'],{})
 def test_failed_calls_are_cleared_too(self):
  with patch.object(server,'model',side_effect=RuntimeError('x')):
   with self.assertRaises(RuntimeError):server.measured_model(self.job,'綜合結論','p',timeout=360)
  self.assertEqual(server.JOBS[self.job]['models_active'],{})

class PlainErrors(Base):
 def test_later_stage_timeout_is_explained(self):
  server.record_failure(self.job,RuntimeError('模型回覆逾時（360秒）；市場數據已保存，可接續報告'))
  e=server.JOBS[self.job]['error'];self.assertIn('Codex',e);self.assertIn('360',e)
 def test_codex_failure_is_explained(self):
  server.record_failure(self.job,RuntimeError('Codex 未完成回覆，請檢查登入或用量後再試'))
  self.assertIn('登入',server.JOBS[self.job]['error'])

if __name__=='__main__':unittest.main()
