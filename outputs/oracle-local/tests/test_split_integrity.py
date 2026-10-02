import unittest
from report_split import compact_row,event_data,clean_layer
class IntegrityTests(unittest.TestCase):
 def test_rules_and_low_volume_deadline_are_not_dropped(self):
  rules='Important settlement clause. '*100
  markets=[{'id':str(i),'description':rules,'volume':1000000-i,'endDate':'2026-12-31'} for i in range(13)]
  markets.append({'id':'exact-deadline','description':rules,'volume':1,'endDate':'2026-11-30'})
  row={'provider':'polymarket','data':[{'title':'event','markets':markets}]}
  result=compact_row(row,200)
  self.assertIn('exact-deadline',str(result));self.assertIn(rules,str(result))
 def test_model_cannot_replace_observed_price(self):
  row={'id':'gold','provider':'yahoo','data':{'symbol':'GC=F','statistics':{'last_close':100,'last_date':'2026-09-29'}}}
  layer=clean_layer({'rows':[{'signal_id':'gold','observation':'999999','interpretation':'test'}]},'gold',[row])
  self.assertNotIn('999999',layer['rows'][0]['observation'])
  self.assertIn('100',layer['rows'][0]['observation'])

 def test_draft_does_not_wait_for_macro_summary(self):
  import json,threading
  from report_split import generate_report
  from test_analysis import report
  published=threading.Event()
  rows=[{'id':'gold','provider':'yahoo','status':'ok','layer':'避險','tier':'core','data':{}},{'id':'spy','provider':'yahoo','status':'ok','layer':'股市','tier':'background','data':{}}]
  def call(kind,label,prompt):
   if kind=='synthesis':return json.dumps(report())
   if label=='分層：宏觀背景':
    if not published.wait(2):raise AssertionError('Background blocked draft')
   return json.dumps({'title':label,'summary':'s','horizon':'h','weight':'w','rows':[]})
  def publish(draft):
   self.assertIn('仍在處理',draft['layers'][1]['summary']);published.set()
  final,_=generate_report('q','now',{},rows,{},{},{},call,{'signals':[]},lambda r,rows:r,lambda r:r,publish_draft=publish)
  self.assertTrue(published.is_set());self.assertEqual(final['layers'][1]['summary'],'s')

 def test_promoted_macro_signal_receives_detailed_analysis(self):
  from report_split import group_layers,layer_payload
  rows=[{'id':sid,'provider':'yahoo','status':'ok','layer':'宏觀背景','tier':tier,'data':{}} for sid,tier in [('vix','promoted'),('spy','background')]]
  groups=dict(group_layers(rows,{'signals':[]}))
  self.assertEqual([r['id'] for r in groups['異常宏觀訊號']],['vix'])
  self.assertEqual([r['id'] for r in groups['宏觀背景']],['spy'])
  self.assertNotIn('此層只輸出summary',layer_payload('q',{},'異常宏觀訊號',groups['異常宏觀訊號']))

 def test_complete_contract_rules_are_not_rejected_by_character_budget(self):
  from report_split import layer_payload
  rules='Settlement condition. '*1500
  row={'id':'event','provider':'polymarket','status':'ok','data':[{'markets':[{'id':'x','description':rules}]}]}
  prompt=layer_payload('q',{},'事件定價',[row])
  self.assertGreater(len(prompt),25000);self.assertIn(rules,prompt)

class CheckpointTests(unittest.TestCase):
 def test_resume_reuses_matching_synthesis_and_layers(self):
  import json
  from report_split import generate_report
  from test_analysis import report
  rows=[{'id':'gold','provider':'yahoo','status':'ok','layer':'避險','tier':'core','data':{}}]
  saved={};calls=[]
  def call(kind,label,prompt):
   calls.append(label)
   return json.dumps(report() if kind=='synthesis' else {'summary':'s'})
  args=('q','stable time',{},rows,{},{},{},call,{'signals':[]},lambda r,rows:r,lambda r:r)
  generate_report(*args,checkpoint=lambda p:saved.update(p))
  self.assertEqual(len(calls),2)
  generate_report(*args,saved_parts=saved)
  self.assertEqual(len(calls),2)
  changed=list(args);changed[0]='different question'
  generate_report(*changed,saved_parts=saved)
  self.assertEqual(len(calls),4)
