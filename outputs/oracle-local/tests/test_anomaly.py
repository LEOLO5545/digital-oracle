import unittest,json
from pathlib import Path
from anomaly import triggers,series_metrics,classify
from unittest.mock import patch
class AnomalyTests(unittest.TestCase):
 def test_saved_spread_and_ratio_are_promoted(self):
  fixture=Path(__file__).resolve().parents[2]/'ukraine-acceptance-live-snapshot.json'
  d=json.loads(fixture.read_text());q=d['quantitative'];wanted=[s for s in q['derived_series'] if 'Brent' in s['name'] or '軍工' in s['name']]
  self.assertEqual(len(wanted),2)
  self.assertTrue(all(triggers(s) for s in wanted))
  self.assertEqual([round(s['sample_percentile'],1) for s in wanted],[98.8,0.8])
  for row in d['sources']:row['tier']='background'
  with patch('anomaly.series_metrics',side_effect=lambda values:series_metrics(values,cutoff=d['created_at'][:10])):
   p=classify(d['sources'],q,'ukraine')
  self.assertTrue(all(any(x['name']==s['name'] for x in p) for s in wanted))
 def test_no_fake_sigma_from_short_history(self):
  s=series_metrics({'2025-01-01':1,'2025-01-02':2});self.assertNotIn('change_21_std',s)
 def test_middle_percentile_not_promoted(self):self.assertEqual(triggers({'sample_percentile':50}),[])
