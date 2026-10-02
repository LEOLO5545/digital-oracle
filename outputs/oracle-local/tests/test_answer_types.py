import copy,datetime,json,unittest
from answer_types import route_answer,materialize_answer
from analysis import validate_report
from test_analysis import report,plan,signal
from target_data import parse_hk_unemployment

ROWS=[{'id':'gold','status':'ok','provider':'censtatd_hk_unemployment','data':{'baseline':{'value':3.7,'period':'2025'}}}]
def numeric():
 r=report();r.pop('probability');r['answer']={'type':'numeric_forecast','target':'失業率','horizon':'2027全年','unit':'%','confidence':'低','kind':'研究預測','basis':'基準與金融渠道','limitations':'未回測','assumptions':['幅度為研究判斷'],'calculation':{'method':'baseline_adjustments','baseline':{'signal_id':'gold','path':['baseline','value']},'baseline_reason':'年度基準','adjustments':[{'name':'需求','delta':.3,'signal_ids':['gold'],'reason':'測試'}, {'name':'資金','delta':-.1,'signal_ids':['gold'],'reason':'測試'}],'alternatives':[{'case':'較弱','delta':.5,'reason':'測試'}, {'case':'較強','delta':0,'reason':'測試'}]}}
 r['scenarios']=[];return r
class AnswerTypeTests(unittest.TestCase):
 def test_routing_preserves_question_intent(self):
  for q,kind in [('香港2027年失業率估計','numeric_forecast'),('美國加息嘅機率','probability'),('美國會唔會加息','binary'),('比較黃金與股票','comparison'),('點解金價上升','explanation')]:
   self.assertEqual(route_answer(q,plan([signal()]))['answer_spec']['type'],kind)
  p=route_answer('香港2027年失業率估計',plan([signal()]))
  self.assertEqual(p['horizon'],'2027-01-01至2027-12-31');self.assertEqual(p['answer_spec']['unit'],'%')
  self.assertIn('censtatd_hk_unemployment',[s['source'] for s in p['signals']])
 def test_level_recomputed_from_real_baseline_and_pp(self):
  r=validate_report(numeric(),ROWS);self.assertNotIn('probability',r)
  self.assertEqual(r['answer']['estimate'],3.9);self.assertEqual(r['answer']['range'],[3.7,4.2])
  self.assertTrue(all('probability' not in s for s in r['scenarios']))
 def test_missing_failed_nonfinite_baseline_rejected(self):
  for rows in [[],[{**ROWS[0],'status':'error'}],[{**ROWS[0],'data':{'baseline':{'value':None}}}]]:
   with self.assertRaises(ValueError):materialize_answer(numeric(),rows)
  r=numeric();r['answer']['calculation']['adjustments'][0]['delta']=float('nan')
  with self.assertRaises(ValueError):materialize_answer(r,ROWS)
 def test_type_units_and_bounds_checked(self):
  for spec in [{'type':'binary'},{'type':'numeric_forecast','unit':'USD'},{'type':'numeric_forecast','unit':'%','bounds':[0,3]}]:
   with self.assertRaises(ValueError):materialize_answer(numeric(),ROWS,spec)
  with self.assertRaises(ValueError):materialize_answer(report(),ROWS,{'type':'numeric_forecast'})
 def test_binary_and_explanation_need_no_probability(self):
  for kind in ['binary','comparison','explanation']:
   r=numeric();a=r['answer'];a.update(type=kind,text='直接回答',decision=True);a.pop('calculation')
   result=validate_report(r,ROWS);self.assertNotIn('probability',result)
  r['answer'].update(type='binary',decision='yes')
  with self.assertRaises(ValueError):validate_report(r,ROWS)
 def test_null_probability_omitted_for_typed_report(self):
  r=numeric();r['probability']=None
  self.assertEqual(validate_report(r,ROWS)['answer']['estimate'],3.9)
 def test_target_history_reaches_synthesis_and_layer(self):
  from report_split import _stats_digest,layer_payload,synthesis_context
  data={**ROWS[0]['data'],'units':'%','annual_history':[{'period':'2025','value':3.7}]}
  self.assertEqual(_stats_digest(data),data)
  row={**ROWS[0],'data':data,'name':'官方基準'}
  self.assertIn('baseline',layer_payload('q',{},'基準',[row]))
  self.assertIn('baseline',json.dumps(synthesis_context('q','now',{},[row],{},{},{})))
 def test_completed_price_baseline_is_available_to_validator(self):
  r=numeric();r['answer']['unit']='USD';r['answer']['calculation']['baseline']['path']=['completed_statistics','last_close']
  rows=[{'id':'gold','status':'ok','provider':'yahoo','data':{'statistics':{'volatility_last_date':'2026-09-29'},'closes':{'2026-09-28':100,'2026-09-29':105,'2026-09-30':999}}}]
  value=materialize_answer(r,rows)['answer']
  self.assertEqual(value['estimate'],105.2);self.assertEqual(value['calculation']['baseline_period'],'2026-09-29')
 def test_official_history_not_sampled_in_download(self):
  from sources import normalize
  values=[{'period':str(y),'value':3} for y in range(1985,2026)]
  self.assertEqual(normalize({'annual_history':values})['annual_history'],values)
 def test_limitations_list_normalizes_without_model_retry(self):
  r=numeric();r['answer']['limitations']=['甲','乙']
  self.assertEqual(validate_report(r,ROWS)['answer']['limitations'],'甲；乙')
 def test_legacy_unchanged(self):
  r=report();self.assertEqual(materialize_answer(r,ROWS),r)
 def test_official_history_excludes_future_and_separates_frequency(self):
  data=[{'SEX':'','freq':'Y','sv':'UR','period':str(y),'figure':3+y/10000} for y in range(2018,2028)]
  data += [{'SEX':'','freq':'M3M','sv':'SAUR','period':'202608','figure':3.8},{'SEX':'M','freq':'Y','sv':'UR','period':'2025','figure':99}]
  parsed=parse_hk_unemployment({'header':{'status':{'code':0}},'dataSet':data},datetime.date(2026,9,30))
  self.assertEqual(parsed['baseline']['period'],'2025');self.assertEqual(parsed['recent_rolling_adjusted'][-1]['value'],3.8)
  self.assertFalse(parsed['baseline']['seasonally_adjusted'])

class EventTimingRoutingTests(unittest.TestCase):
 def test_event_date_is_not_numeric_level_forecast(self):
  p=plan([signal()]);p['answer_spec']={'type':'numeric_forecast','target':'脫鈎時間','unit':'日期或日期區間','aggregation':'event'}
  got=route_answer('幫我預測一下港元同美元幾時會脫鈎',p)
  self.assertEqual(got['answer_spec']['type'],'probability')
  self.assertEqual(got['answer_spec']['unit'],'')
  self.assertTrue(got['answer_spec']['timing_question'])
