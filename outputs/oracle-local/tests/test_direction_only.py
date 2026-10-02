"""A numeric forecast whose target level could not be fetched must still publish an honest
direction-only answer instead of failing the whole analysis (2026-10-02 HK property regression)."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from answer_types import materialize_answer
from analysis import validate_report
from evaluation import assess
from test_answer_types import numeric, ROWS

MISSING=ROWS+[{'id':'hk_residential_price','status':'lead','provider':'web','data':None}]
SPEC={'type':'numeric_forecast','unit':'%'}

def direction_only():
 r=numeric();a=r['answer'];a['calculation']=None
 a['basis']='地產、融資及銀行渠道合併後負面訊號略佔優勢，方向偏跌。未取得官方住宅價格數值，不能建立基準加調整的計算。'
 r['headline_summary']='未來12個月樓價方向偏跌；官方樓價缺漏，無法量化幅度。'
 r['scenarios']=[{'name':'較弱情景','estimate':None,'unit':'%','basis':'港元偏弱[gold]','trigger':'官方指數連跌'},{'name':'較強情景','estimate':None,'unit':'%','basis':'銀行強勢[gold]','trigger':'官方指數連升'}]
 return r

class DirectionOnlyTests(unittest.TestCase):
 def test_missing_target_baseline_publishes_direction_only(self):
  r=validate_report(materialize_answer(direction_only(),MISSING,SPEC),MISSING)
  a=r['answer']
  self.assertTrue(a['direction_only']);self.assertIsNone(a['estimate']);self.assertIsNone(a['range'])
  self.assertIn('未計算數值',a['kind']);self.assertEqual(a['text'],r['headline_summary'])
  self.assertIn('hk_residential_price',a['limitations'])
  self.assertTrue(all(s['estimate'] is None for s in r['scenarios']))
 def test_idempotent(self):
  once=materialize_answer(direction_only(),MISSING,SPEC)
  self.assertEqual(materialize_answer(once,MISSING,SPEC)['answer'],once['answer'])
 def test_audit_accepts_direction_only(self):
  r=validate_report(materialize_answer(direction_only(),MISSING,SPEC),MISSING)
  checks=assess({'report':r,'sources':MISSING,'quantitative':{'pair_count':1}})['checks']
  self.assertTrue(checks['quantified_estimate_or_explicit_scenarios']);self.assertTrue(checks['sensitivity_cases'])
 def test_not_allowed_when_every_signal_succeeded(self):
  # All data arrived: skipping the calculation would be lazy, not honest.
  with self.assertRaises(ValueError):materialize_answer(direction_only(),ROWS,SPEC)
 def test_scenario_levels_without_baseline_rejected(self):
  r=direction_only();r['scenarios'][0]['estimate']=-5
  with self.assertRaises(ValueError):materialize_answer(r,MISSING,SPEC)
 def test_broken_calculation_still_rejected(self):
  r=direction_only();r['answer']['calculation']={'method':'baseline_adjustments','baseline':{'signal_id':'hk_residential_price','path':['x']}}
  with self.assertRaises(ValueError):materialize_answer(r,MISSING,SPEC)

if __name__=='__main__':unittest.main()
