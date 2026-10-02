import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from test_analysis import signal,plan,report
def fake_model(planned):
 """Answer by prompt type: calls now run in parallel, so a fixed response order no longer applies."""
 from report_split import LAYER_PROMPT,SYNTH_OVERRIDE
 from evaluation import AUDITOR
 def answer(prompt,effort='medium',timeout=480):
  if prompt.startswith(LAYER_PROMPT):
   payload=json.loads(prompt[len(LAYER_PROMPT)+1:])
   return json.dumps({'title':payload['layer'],'summary':'s','horizon':'h','weight':'w','rows':[{'signal_id':x['id'],'observation':'o','interpretation':'i','caveat':'c'} for x in payload['signals']]})
  if SYNTH_OVERRIDE in prompt:
   from test_probability import calculated_report
   r=calculated_report();r.pop('layers');return json.dumps(r)
  if prompt.startswith(AUDITOR):return json.dumps({'findings':[]})
  if 'DISCONFIRM' in prompt:raise ValueError('invalid supplement')
  return json.dumps(planned)
 return answer
class WorkflowTests(unittest.TestCase):
 def test_optional_supplement_failure_does_not_discard_good_evidence(self):
  with tempfile.TemporaryDirectory() as folder:
   job='a'*32
   server.JOBS[job]={'id':job,'question':'test','status':'running','sources':[]}
   row={'id':'gold','provider':'yahoo','status':'ok','data':{},'name':'Gold'}
   with patch.object(server,'STATE',Path(folder)),patch.object(server,'model',side_effect=fake_model(plan([signal()]))),patch.object(server,'query_signal',return_value=row):
    server.run_job(job,'test')
   saved=json.loads((Path(folder)/'reports'/(job+'.json')).read_text())
   self.assertEqual(saved['status'],'done');self.assertIn('review_warning',saved)
   self.assertEqual(saved['sources'][0]['id'],'gold');self.assertTrue(saved['completed_at'])
   server.JOBS.pop(job,None)
 def test_health_check_preserves_last_research(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);sentinel={'report':{'title':'previous research'}}
   (root/'last-report.json').write_text(json.dumps(sentinel))
   job='b'*32;server.JOBS[job]={'id':job,'status':'running','sources':[]}
   def response(s):return {'id':s['id'],'provider':s['source'],'status':'ok','data':{}}
   with patch.object(server,'STATE',root),patch.object(server,'query_signal',side_effect=response):server.run_job(job,'health',True)
   self.assertEqual(json.loads((root/'last-report.json').read_text()),sentinel)
   self.assertEqual(server.JOBS[job]['status'],'done');server.JOBS.pop(job,None)
 def test_model_failure_is_archived_for_diagnosis(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);job='c'*32;server.JOBS[job]={'id':job,'status':'running','sources':[]}
   with patch.object(server,'STATE',root),patch.object(server,'model',side_effect=RuntimeError('test timeout')):server.run_job(job,'test')
   saved=json.loads((root/'reports'/(job+'.json')).read_text())
   self.assertEqual(saved['status'],'error');self.assertIn('test timeout',saved['error']);self.assertFalse(server.BUSY)
   server.JOBS.pop(job,None)

 def test_report_is_built_from_parallel_layer_and_synthesis_calls(self):
  from report_split import generate_report
  from analysis import validate_report
  rows=[{'id':'gold','provider':'yahoo','status':'ok','layer':'避險','data':{}},{'id':'oil','provider':'yahoo','status':'ok','layer':'能源','data':{}},{'id':'bad','provider':'yahoo','status':'error','layer':'能源','error':'x'}]
  planned={'signals':[{'id':'gold'},{'id':'oil'},{'id':'bad'}]}
  kinds=[]
  answer=fake_model(planned)
  def call(kind,label,prompt):
   kinds.append(kind)
   if label=='分層：能源':raise RuntimeError('模型回覆逾時（180秒）')
   return answer(prompt)
  r,_=generate_report('q','now',{},rows,{},{},{},call,planned,validate_report,lambda v:v)
  self.assertEqual(sorted(kinds),['layer','layer','synthesis'])
  self.assertEqual([l['title'] for l in r['layers']],['避險','能源'])
  self.assertEqual(r['layers'][1]['rows'][0]['signal_id'],'oil')
  self.assertTrue(any('能源' in x for x in r['limitations']))
