import unittest,json
from pathlib import Path
from anomaly import triggers,series_metrics,classify
from unittest.mock import patch
class AnomalyTests(unittest.TestCase):
 def test_saved_spread_and_ratio_are_promoted(self):
  # Synthetic regression fixture; never require a private saved report.
  from datetime import date,timedelta
  rows=[];derived=[]
  for prefix,name,mode,last,percentile in [('oil','Brent-WTI','spread',246.5,98.8),('defense','ITA/SPY','ratio',1.5,0.8)]:
   values=list(range(1,250))+[last]
   dates=[str(date(2020,1,1)+timedelta(days=i)) for i in range(250)]
   a,b=prefix+'_a',prefix+'_b'
   rows.extend([{'id':a,'name':a,'status':'ok','tier':'background','data':{'closes':dict(zip(dates,[v+1 if mode=='spread' else v for v in values]))}},
                {'id':b,'name':b,'status':'ok','tier':'background','data':{'closes':dict.fromkeys(dates,1)}}])
   derived.append({'name':name,'mode':mode,'signals':[a,b],'sample_percentile':percentile})
  self.assertTrue(all(triggers(s) for s in derived))
  promotions=classify(rows,{'derived_series':derived},'ukraine')
  self.assertTrue(all(any(x['name']==s['name'] for x in promotions) for s in derived))
  self.assertTrue(all(row['tier']=='promoted' for row in rows))
 def test_no_fake_sigma_from_short_history(self):
  s=series_metrics({'2025-01-01':1,'2025-01-02':2});self.assertNotIn('change_21_std',s)
 def test_middle_percentile_not_promoted(self):self.assertEqual(triggers({'sample_percentile':50}),[])
