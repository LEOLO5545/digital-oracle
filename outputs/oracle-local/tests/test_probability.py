import copy,unittest
from probability import compute,materialize

def calculated_report():
 from test_analysis import report
 r=report();r['probability']['calculation']={'method':'conditional_bridge','baseline_event':'B','baseline_pct':10,'baseline_origin':'analyst_prior','baseline_reason':'prior informed by [gold]','baseline_sources':['gold'],'target_given_baseline_pct':70,'target_without_baseline_pct':1,'conditional_reason':'Research choice supported by channels, not calibration.','channels':[{'name':n,'signal_ids':['gold'],'effect':'中性','reason':'Test explanation'} for n in ['a','b','c']],'alternatives':[{'case':'less','baseline_pct':10,'target_given_baseline_pct':50,'target_without_baseline_pct':0,'reason':'alternative [gold]'},{'case':'more','baseline_pct':10,'target_given_baseline_pct':90,'target_without_baseline_pct':2,'reason':'alternative [gold]'}]}
 r['scenarios'][0]['target_outcome']=True;r['scenarios'][1]['target_outcome']=False
 return r
class ProbabilityTests(unittest.TestCase):
 def test_formula_uses_both_branches_and_program_controls_result(self):
  r=calculated_report();original=copy.deepcopy(r)
  out=materialize(r,[{'id':'gold','status':'ok'}],required=True)
  self.assertEqual(r,original);self.assertAlmostEqual(out['probability']['estimate'],7.9)
  self.assertEqual(out['probability']['range'],[5,10.8]);self.assertEqual([x['probability'] for x in out['scenarios']],[7.9,92.1])
  self.assertFalse(out['probability']['calculation']['calibrated'])
 def test_bad_parameters_and_failed_sources_are_rejected(self):
  for value in [float('nan'),-1,101,True,None]:
   with self.assertRaises(ValueError):compute(value,50,1)
  with self.assertRaises(ValueError):materialize(calculated_report(),[{'id':'gold','status':'error'}])
 def test_legacy_reports_are_untouched_and_new_reports_require_calculation(self):
  from test_analysis import report
  r=report();self.assertEqual(materialize(r,[]),r)
  with self.assertRaises(ValueError):materialize(r,[],required=True)
 def test_no_fake_center_from_example_midpoint(self):
  from test_analysis import report
  r=report();r['probability'].update(estimate=None,range=[2,16],kind='假設情境示例')
  self.assertIsNone(materialize(r,[])['probability']['estimate'])
 def test_three_channels_and_complementary_outcomes_required(self):
  r=calculated_report();r['probability']['calculation']['channels']=[]
  with self.assertRaises(ValueError):materialize(r,[{'id':'gold','status':'ok'}])
  r=calculated_report();r['scenarios'][1]['target_outcome']=True
  with self.assertRaises(ValueError):materialize(r,[{'id':'gold','status':'ok'}])
 def test_small_nonzero_probability_is_not_rounded_to_zero(self):
  from probability import rounded
  self.assertEqual(rounded(.003456),.0035)
