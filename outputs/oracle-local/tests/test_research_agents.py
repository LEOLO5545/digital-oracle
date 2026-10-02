import json, threading, unittest
from research_agents import validate_note
from report_split import generate_report

class ResearchAgentsTests(unittest.TestCase):
 def test_reject_unknown_and_failed_evidence(self):
  for ids in (['missing'],[],[None]):
   with self.assertRaises(ValueError):validate_note({'findings':[{'claim':'c','implication':'i','signal_ids':ids}],'gaps':[]},{'gold'})

 def run_report(self,call,**kw):
  rows=[{'id':'gold','provider':'yahoo','status':'ok','tier':'core','layer':'核心','data':{}}]
  return generate_report('q','now',{},rows,{},{},{},call,{'signals':[]},lambda r,rows:r,lambda r:r,agent_settings={'enabled':True},**kw)[0]

 def test_parallel_roles_feed_synthesis_and_resume(self):
  barrier=threading.Barrier(3);saved={};seen=[]
  def call(kind,label,prompt):
   seen.append(kind)
   if kind=='agent':
    barrier.wait(timeout=2)
    return json.dumps({'findings':[{'claim':label,'signal_ids':['gold'],'implication':'有待綜合'}],'gaps':[]})
   if kind=='synthesis':
    self.assertEqual(seen.count('agent'),3)
    for name in ('direct','cross_market','challenge'):self.assertIn(name,prompt)
   return '{}'
  report=self.run_report(call,checkpoint=lambda p:saved.update(p))
  self.assertEqual(len(report['research_agents']),3)
  self.run_report(lambda *a:self.fail('Cached roles and synthesis should be reused'),saved_parts=saved)

 def test_failed_role_is_disclosed_and_not_cached(self):
  saved={}
  def call(kind,label,prompt):
   if kind=='agent':return '{"findings":[],"gaps":[]}'
   return '{}'
  report=self.run_report(call,checkpoint=lambda p:(saved.clear(),saved.update(p)))
  self.assertTrue(all(v['status']=='error' for v in report['research_agents'].values()))
  self.assertEqual(len(report['limitations']),3)
  self.assertFalse(any(k.startswith('agent:') for k in saved))

 def test_draft_does_not_wait_for_background_in_multi_agent_mode(self):
  published=threading.Event()
  rows=[{'id':i,'provider':'yahoo','status':'ok','tier':tier,'layer':i,'data':{}} for i,tier in [('gold','core'),('spy','background')]]
  def call(kind,label,prompt):
   if kind=='agent':return '{"findings":[],"gaps":["缺少直接定價"]}'
   if label=='分層：宏觀背景':self.assertTrue(published.wait(2))
   return '{}'
  generate_report('q','now',{},rows,{},{},{},call,{'signals':[]},lambda r,rows:r,lambda r:r,
                  publish_draft=lambda r:published.set(),agent_settings={'enabled':True})
  self.assertTrue(published.is_set())

if __name__=='__main__':unittest.main()
