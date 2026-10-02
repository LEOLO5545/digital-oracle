import sys,unittest,datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from quant import paired,parse_fred,series_summary,cross_market,treasury_history
class QuantTests(unittest.TestCase):
 def test_common_dates_before_returns(self):
  dates=[(datetime.date(2026,1,1)+datetime.timedelta(days=i)).isoformat() for i in range(31)]
  a={d:100+i*i for i,d in enumerate(dates)};b={d:2*v for d,v in a.items() if d!=dates[8]}
  p=paired(a,b);self.assertAlmostEqual(p['return_correlation'],1);self.assertEqual(p['common_return_intervals'],29);self.assertAlmostEqual(p['relative_return_21_common_observations_pp'],0)
 def test_short_or_constant_series_not_correlated(self):
  self.assertIsNone(paired({'a':1},{'a':2}))
  dates=[(datetime.date(2025,1,1)+datetime.timedelta(days=i)).isoformat() for i in range(30)]
  p=paired({d:1 for d in dates},{d:2 for d in dates})
  self.assertIsNone(p['return_correlation'])
 def test_fred_missing_dates_and_units(self):
  p=parse_fred('observation_date,T10Y2Y\n2026-01-01,0.5\n2026-01-02,.\n2026-01-03,0.6\n','T10Y2Y')
  self.assertEqual(p['statistics']['observations'],2);self.assertEqual(p['units'],'percentage points');self.assertEqual(p['statistics']['latest'],0.6)
 def test_spread_is_difference_not_return(self):
  rows=[dict(id=s,provider='yahoo',status='ok',data={'symbol':t,'closes':{'2026-01-01':p,'2026-01-02':p+1}}) for s,t,p in [('brent','BZ=F',80),('wti','CL=F',75)]]
  q=cross_market(rows);self.assertEqual(q['derived_series'][0]['latest'],5);self.assertEqual(q['pair_count'],0)

 def test_treasury_selects_chronological_latest_not_last_row(self):
  from types import SimpleNamespace
  curves=[SimpleNamespace(date='09/29/2026',spread=lambda a,b:0.37),SimpleNamespace(date='01/02/2026',spread=lambda a,b:0.2)]
  latest,summary=treasury_history(curves)
  self.assertEqual(latest.date,'09/29/2026');self.assertEqual(summary['last_date'],'2026-09-29')
 def test_terminal_frequency_counts_endpoints_not_touch(self):
  from quant import terminal_return_baselines
  dates=[(datetime.date(2025,1,1)+datetime.timedelta(days=i)).isoformat() for i in range(120)]
  values={d:100 if i<60 else 50 for i,d in enumerate(dates)}
  b=terminal_return_baselines(values,-20,30,365)
  self.assertEqual(b['overlapping_historical_windows'],90)
  self.assertEqual(b['historical_hits'],30)
  self.assertEqual(b['non_overlapping_windows'],3)
  self.assertEqual(b['non_overlapping_hits'],1)
 def test_terminal_threshold_cannot_exceed_total_loss(self):
  from quant import terminal_return_baselines
  with self.assertRaises(ValueError):terminal_return_baselines({},-100,90)

 def test_walk_forward_prediction_has_no_future_price_leakage(self):
  import math
  from quant import rolling_terminal_backtest
  dates=[datetime.date(2024,1,1)+datetime.timedelta(days=i) for i in range(500)]
  prices=[100*math.exp(.001*i+.03*math.sin(i)) for i in range(500)]
  original=list(zip(dates,prices))
  changed=[(d,p if i<=252 else p*.5) for i,(d,p) in enumerate(original)]
  a=rolling_terminal_backtest(original,-20,30,365);b=rolling_terminal_backtest(changed,-20,30,365)
  self.assertEqual(a['points'][0]['predicted_pct'],b['points'][0]['predicted_pct'])
  self.assertNotEqual(a['points'][0]['outcome'],b['points'][0]['outcome'])
  self.assertEqual(a['points'][0]['historical_frequency_benchmark_pct'],b['points'][0]['historical_frequency_benchmark_pct'])

 def test_partial_current_day_is_not_in_correlations(self):
  today=datetime.datetime.now(datetime.timezone.utc).date()
  a={(today-datetime.timedelta(days=i)).isoformat():100+i*i for i in range(31)}
  p=paired(a,{d:v*2 for d,v in a.items()})
  self.assertEqual(p['to'],(today-datetime.timedelta(days=1)).isoformat())
  self.assertEqual(p['common_return_intervals'],29)

 def test_negative_yields_use_changes_not_log_returns(self):
  import math
  from quant import change_return_pair
  dates=[(datetime.date(2025,1,1)+datetime.timedelta(days=i)).isoformat() for i in range(31)]
  levels={d:-2+.001*i*i for i,d in enumerate(dates)}
  prices={d:100*math.exp(.001*i*i) for i,d in enumerate(dates)}
  p=change_return_pair(levels,prices)
  self.assertAlmostEqual(p['change_return_correlation'],1)
  self.assertEqual(p['common_return_intervals'],30)

 def test_coin_cross_quote_inconsistency_is_visible_not_arbitrage(self):
  from quant import coin_quote_consistency
  prices=[{'symbol':'BTC','price_usd':'100'},{'symbol':'ETH','price_usd':'10','price_btc':'0.12'}]
  check=coin_quote_consistency(prices)[0]
  self.assertTrue(check['flagged']);self.assertAlmostEqual(check['difference_pct'],20)
  prices[1]['price_btc']='0.10';self.assertFalse(coin_quote_consistency(prices)[0]['flagged'])
