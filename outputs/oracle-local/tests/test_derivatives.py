import sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from derivatives import choose_expiration,option_quote
from analysis import validate_plan
from test_analysis import signal,plan
class DerivativeTests(unittest.TestCase):
 def test_selects_target_horizon_not_first_daily_expiry(self):
  ex=['2026-10-01','2026-12-25','2027-01-29']
  self.assertEqual(choose_expiration(ex,'2026-12-30','2026-09-30'),'2026-12-25')
  self.assertEqual(choose_expiration(ex,'2027-03-01','2026-09-30'),'2027-01-29')
  with self.assertRaises(ValueError):choose_expiration(['2026-09-30'],'2026-12-30','2026-09-30')
 def test_preserves_different_option_expirations(self):
  a={**signal('short','SPY'),'source':'options','expiration':'2026-10-16'}
  b={**a,'id':'long','expiration':'2026-12-18'}
  self.assertEqual(len(validate_plan(plan([a,b]))['signals']),2)
 def test_no_bid_not_reported_as_tradeable_mid(self):
  instrument=SimpleNamespace(instrument_name='BTC-test-P',strike=60000,option_type='put')
  book=SimpleNamespace(raw={'mark_iv':60},best_bid=0,best_ask=0.1,timestamp_ms=1,state='open',index_price=80000,open_interest=12)
  q=option_quote(book,instrument,'test');self.assertFalse(q['two_sided_quote']);self.assertIsNone(q['mid_coin']);self.assertIsNone(q['spread_pct_of_mid'])
  book.best_bid=0.08;q=option_quote(book,instrument,'test')
  self.assertTrue(q['two_sided_quote']);self.assertAlmostEqual(q['spread_pct_of_mid'],200/9)

 def test_tail_quotes_preserve_strikes_around_the_requested_threshold(self):
  from derivatives import equity_tail_quotes
  from digital_oracle.providers.yfinance_provider import OptionsChain,OptionContract
  puts=tuple(OptionContract('T'+str(k),'put','2027-03-19',k,bid=1,ask=1.2) for k in (50,60,65,70,75,100))
  chain=OptionsChain('T','2027-03-19',100,(),puts)
  result=equity_tail_quotes(chain,-30)
  self.assertEqual(result['target_strike'],70)
  self.assertTrue(result['target_bracketed'])
  self.assertEqual([q['strike'] for q in result['quotes']],[65,70,75])
  self.assertTrue(all(q['two_sided_quote'] for q in result['quotes']))
