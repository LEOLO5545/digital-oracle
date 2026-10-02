import unittest,datetime,copy
from target_data import parse_hk_housing
from answer_types import route_answer,materialize_answer
from test_answer_types import numeric
from test_analysis import plan,signal
class HousingTests(unittest.TestCase):
 def test_monthly_all_classes_and_future_exclusion(self):
  csv='Title\nMonth,Class A,All Classes,All Classes - Remarks\n08-2025,999,300,\n08-2026,999,320.5,P\n12-2027,999,900,\n'
  d=parse_hk_housing(csv,datetime.date(2026,10,2))
  self.assertEqual(d['baseline']['value'],320.5);self.assertEqual(d['baseline']['period'],'2026-08')
  self.assertAlmostEqual(d['change_12_months_pct'],6.833333333)
  self.assertTrue(d['baseline']['provisional'])
 def test_change_forecast_uses_percent_changes_not_index_plus_percent(self):
  r=numeric();c=r['answer']['calculation'];c['method']='percentage_change';c['adjustments'][0]['delta']=-2;c['adjustments'][1]['delta']=.5
  rows=[{'id':'gold','status':'ok','provider':'rvd_hk_housing','data':{'baseline':{'value':320.5,'period':'2026-08'}}}]
  a=materialize_answer(r,rows)['answer'];self.assertEqual(a['estimate'],-1.5);self.assertAlmostEqual(a['calculation']['implied_index'],315.6925)
 def test_route_housing_adds_official_target(self):
  p=route_answer('香港樓價未來12個月會升還是跌？推算方向與幅度',plan([signal()]))
  self.assertEqual(p['answer_spec']['quantity'],'percentage_change')
  self.assertIn('rvd_hk_housing',[s['source'] for s in p['signals']])
 def test_missing_baseline_still_rejected(self):
  r=numeric();r['answer']['calculation']['method']='percentage_change'
  with self.assertRaises(ValueError):materialize_answer(r,[])
 def test_resume_fetches_only_new_baseline(self):
  import server,tempfile
  from pathlib import Path
  from unittest.mock import patch
  job='8'*32;old={'id':'existing','status':'ok','data':{}}
  new={'id':'hk_housing_baseline','source':'rvd_hk_housing'}
  with tempfile.TemporaryDirectory() as tmp,patch.object(server,'STATE',Path(tmp)),patch.object(server,'measured_signal',return_value={'id':new['id'],'status':'ok','data':{}}) as fetch,patch.object(server,'cross_market',return_value={}),patch.object(server,'finish_report') as finish:
   server.JOBS[job]={'id':job,'question':'香港樓價','sources':[old],'plan':{'signals':[{'id':'existing'},new]}}
   try:
    server.resume_report_job(job)
    fetch.assert_called_once_with(job,new)
    self.assertEqual(len(finish.call_args.args[3]),2)
    self.assertEqual(finish.call_args.args[3][0],old)
   finally:server.JOBS.pop(job,None)
