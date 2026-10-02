import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis import validate_plan,validate_report,price_statistics,prepare_supplement
from digital_oracle.providers.prices import PriceBar,PriceHistory

def signal(sid='gold',ticker='GC=F'):
 return dict(id=sid,source='yahoo',ticker=ticker,label='黃金',layer='避險',reason='測試避險需求',horizon='三個月')
def plan(signals):return dict(core_variable='風險',horizon='三個月',priceability='代理',signals=signals)
def report():
 return dict(title='t',conclusion='c',coverage='3',probability=dict(kind='主觀情境估計',range=[20,40],estimate=30,assumptions=['假設'],sensitivity=[dict(case='移除一層',estimate=20,reason='原因'),dict(case='另一解釋',estimate=40,reason='原因')],event='e',horizon='h',confidence='低',basis='b',limitations='l'),layers=[dict(title='a',summary='s',horizon='h',weight='w',rows=[dict(signal_id='gold',observation='1',interpretation='i',caveat='c')])],analysis=dict(agreement=['a'],divergence=['d'],time_horizons=['t']),scenarios=[dict(name='a',probability=30,basis='b',trigger='t'),dict(name='b',probability=70,basis='b',trigger='t')],sub_conclusions=[dict(dimension='d',judgment='j',confidence='c',evidence='e')],logic_chain=['a'],limitations=['l'],monitor=[])
class AnalysisTests(unittest.TestCase):
 def test_preserves_multiple_assets_same_provider(self):
  p=validate_plan(plan([signal(),signal('oil','CL=F')]))
  self.assertEqual(len(p['signals']),2)
 def test_deduplicates_identical_queries(self):
  self.assertEqual(len(validate_plan(plan([signal(),signal('gold_again')]))['signals']),1)
 def test_rejects_unsafe_or_unknown_query(self):
  for s in [signal(ticker='../secret'),{**signal(),'source':'shell'},{**signal(),'source':'kalshi','series':'INVENTED'}]:
   with self.assertRaises(ValueError):validate_plan(plan([s]))
 def test_statistics_uses_sorted_full_series(self):
  bars=tuple(PriceBar(f'2026-01-{i:02}',100,100,100,c) for i,c in enumerate([100,110,120,90,100,110],1))
  stats=price_statistics(PriceHistory('X','d',bars[::-1]))
  self.assertAlmostEqual(stats['return_5_observations_pct'],10)
  self.assertAlmostEqual(stats['max_drawdown_pct'],-25)
  self.assertEqual(stats['last_date'],'2026-01-06')
  self.assertIsNone(stats['return_21_observations_pct'])
 def test_report_rejects_false_citation_and_bad_probabilities(self):
  rows=[dict(id='gold',status='ok')]
  self.assertEqual(validate_report(report(),rows)['title'],'t')
  for change in ('range','sum','citation'):
   r=report()
   if change=='range':r['probability']['range']=[80,20]
   if change=='sum':r['scenarios'][0]['probability']=50
   if change=='citation':r['layers'][0]['rows'][0]['signal_id']='invented'
   with self.assertRaises(ValueError):validate_report(r,rows)
 def test_unknown_probability_allowed_without_fake_number(self):
  r=report();r['probability']['range']=None;r['probability']['estimate']=None
  for case in r['probability']['sensitivity']:case['estimate']=None
  for s in r['scenarios']:s['probability']=None
  validate_report(r,[dict(id='gold',status='ok')])

 def test_failed_same_query_is_retried_without_duplicate_signal(self):
  initial=validate_plan(plan([signal()]))
  revised,requests=prepare_supplement(initial,[dict(id='gold',status='error')],[signal('retry_gold')])
  self.assertEqual(len(revised['signals']),1);self.assertEqual([s['id'] for s in requests],['gold'])
 def test_successful_query_is_not_refetched(self):
  initial=validate_plan(plan([signal()]))
  revised,requests=prepare_supplement(initial,[dict(id='gold',status='ok')],[signal('duplicate')])
  self.assertEqual(requests,[])

 def test_narrative_citation_must_exist(self):
  r=report();r['analysis']['agreement']=['沒有此資料 [imaginary]']
  with self.assertRaises(ValueError):validate_report(r,[dict(id='gold',status='ok')])
 def test_unquantified_report_cannot_hide_numeric_scenarios(self):
  r=report();r['probability']['range']=None;r['probability']['estimate']=None
  for case in r['probability']['sensitivity']:case['estimate']=None
  with self.assertRaises(ValueError):validate_report(r,[dict(id='gold',status='ok')])

 def test_partial_day_volume_cannot_be_compared_to_full_day_average(self):
  import datetime
  today=datetime.datetime.now(datetime.timezone.utc).date()
  bars=tuple(PriceBar((today-datetime.timedelta(days=25-i)).isoformat(),100,100,100,100+i,1000 if i<25 else 50) for i in range(26))
  stats=price_statistics(PriceHistory('BTC-USD','d',bars))
  self.assertTrue(stats['latest_bar_may_be_incomplete'])
  self.assertIsNone(stats['latest_volume_vs_prior_21_ratio'])
  self.assertEqual(stats['complete_volume_vs_previous_21_ratio'],1)
  self.assertEqual(stats['volatility_last_date'],(today-datetime.timedelta(days=1)).isoformat())

 def test_unidentified_example_has_no_preferred_center(self):
  r=report();r['probability']['kind']='假設情境示例（非數據識別）';r['probability']['estimate']=None
  for case in r['scenarios']:case['probability']=None
  validate_report(r,[dict(id='gold',status='ok')])
  r['probability']['kind']='市場隱含'
  with self.assertRaises(ValueError):validate_report(r,[dict(id='gold',status='ok')])
