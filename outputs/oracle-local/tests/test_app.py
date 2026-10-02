import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import validate_plan, allowed_request
from sources import normalize, validate_data
class AppTests(unittest.TestCase):
 def test_plan_rejects_arbitrary_sources(self):
  with self.assertRaises(ValueError):validate_plan({'sources':['shell'],'search':'x','ticker':'SPY'})
 def test_plan_rejects_unsafe_ticker(self):
  with self.assertRaises(ValueError):validate_plan({'sources':['yahoo'],'search':'x','ticker':'../secret'})
 def test_csrf_rejects_external_origin_and_wrong_token(self):
  self.assertFalse(allowed_request('127.0.0.1:8765','https://evil.test','abc','abc'))
  self.assertFalse(allowed_request('evil.test',None,'abc','abc'))
  self.assertFalse(allowed_request('127.0.0.1:8765',None,'wrong','abc'))
  self.assertTrue(allowed_request('127.0.0.1:8765','http://127.0.0.1:8765','abc','abc'))
 def test_zero_quote_not_accepted(self):
  with self.assertRaises(ValueError):validate_data('eastmoney',{'quote':{'last':0}})
 def test_raw_payload_is_removed_and_sample_explicit(self):
  self.assertEqual(normalize({'raw':{'hidden':1},'x':list(range(30))})['x']['total'],30)
  self.assertNotIn('raw',normalize({'raw':123,'name':'hello'}))

 def test_event_outcomes_are_not_sampled_away(self):
  markets=[{'question':str(i)} for i in range(30)]
  result=normalize({'markets':markets})
  self.assertEqual(len(result['markets']),30)
  self.assertEqual(result['markets'][15]['question'],'15')
