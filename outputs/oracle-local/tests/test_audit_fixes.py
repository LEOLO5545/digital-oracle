"""Regression tests for the 2026-09-30 data-collection and probability audit."""
import copy, json, unittest

def poly_row(sid, markets):
 return {'id':sid,'provider':'polymarket','status':'ok','data':[{'title':'family','url':'https://polymarket.com/event/'+sid,'markets':markets}]}

def pm(q, bid, ask, end, vol=500000, desc='Resolves Yes if the event happens.'):
 return {'id':q,'question':q,'outcomes':'["Yes", "No"]','outcomePrices':json.dumps([str((bid+ask)/2),str(1-(bid+ask)/2)]),'bestBid':bid,'bestAsk':ask,'volume':str(vol),'liquidity':'20000','endDate':end,'closed':False,'description':desc}

class DeadlineFromHorizon(unittest.TestCase):
 """Finding 1: questions phrased as 'next N months' never got a market anchor."""
 def test_horizon_end_date_is_used_when_question_has_no_date(self):
  from liquidity import deadline
  self.assertEqual(deadline('未來三個月美國減息機會','2026-09-30T10:35:56+00:00 至 2026-12-30 23:59 香港時間'),'2026-12-31T00:00:00+08:00')
  self.assertEqual(deadline('香港2027年全年平均失業率估計','2027-01-01至2027-12-31'),'2028-01-01T00:00:00+08:00')
 def test_question_date_still_takes_priority(self):
  from liquidity import deadline
  self.assertEqual(deadline('截至2026年11月30日','2026-09-30 至 2027-03-01'),'2026-12-01T00:00:00+08:00')
 def test_no_date_anywhere_gives_none(self):
  from liquidity import deadline
  self.assertIsNone(deadline('黃金趨勢','最近一個月'))

class DirectMarketAnchors(unittest.TestCase):
 """Finding 5: contracts whose deadline matches the question are surfaced, including 'no event' complements."""
 def test_matching_deadline_and_complement_are_listed(self):
  from liquidity import liquidity_anchors
  rows=[poly_row('p1',[pm('Will no Fed rate cuts happen in 2026?',.964,.965,'2027-01-01T00:00:00Z',8_000_000),pm('Fed rate cut by March 2027 meeting?',.15,.30,'2027-04-08T03:59:00Z',400)])]
  out=liquidity_anchors(rows,'未來三個月美國減息機會','2026-09-30T10:35:56+00:00','2026-09-30 至 2026-12-30 23:59 香港時間')
  direct=out['direct']
  self.assertEqual(len(direct),1)
  d=direct[0];self.assertEqual(d['signal_id'],'p1')
  self.assertAlmostEqual(d['yes_mid_pct'],96.45,places=2);self.assertAlmostEqual(d['no_mid_pct'],3.55,places=2)
  self.assertLessEqual(abs(d['deadline_gap_days']),14)
 def test_illiquid_or_wide_markets_are_not_direct_anchors(self):
  from liquidity import liquidity_anchors
  rows=[poly_row('p1',[pm('thin',.01,.02,'2026-12-31T00:00:00Z',vol=500),pm('wide',.1,.4,'2026-12-31T00:00:00Z')])]
  self.assertEqual(liquidity_anchors(rows,'q','2026-09-30T00:00:00+00:00','至2026-12-30')['direct'],[])

class MarketQuoteIsVerified(unittest.TestCase):
 """Finding 3: a baseline claimed as a market quote must match a fetched quote (or its complement)."""
 def report(self,baseline,origin='market_quote',source='poly'):
  from test_probability import calculated_report
  r=calculated_report();c=r['probability']['calculation']
  c.update(baseline_pct=baseline,baseline_origin=origin,baseline_sources=[source])
  for x in c['channels']:x['signal_ids']=[source]
  return r
 def rows(self):return [poly_row('poly',[pm('Will no cut happen?',.964,.965,'2027-01-01T00:00:00Z')])]
 def test_quote_and_complement_are_accepted(self):
  from probability import materialize
  materialize(self.report(96.5),self.rows(),required=True)
  materialize(self.report(3.5),self.rows(),required=True)
 def test_misread_quote_is_rejected(self):
  from probability import materialize
  with self.assertRaisesRegex(ValueError,'市場報價'):materialize(self.report(12),self.rows(),required=True)
 def test_analyst_prior_is_not_checked_against_quotes(self):
  from probability import materialize
  materialize(self.report(12,origin='analyst_prior'),self.rows(),required=True)
 def test_prior_must_explain_why_a_matching_contract_was_not_used(self):
  from probability import materialize
  anchors={'direct':[{'signal_id':'poly','question':'Will no cut happen?','yes_mid_pct':96.45,'no_mid_pct':3.55,'volume_usd':500000}]}
  with self.assertRaisesRegex(ValueError,'直接定價'):materialize(self.report(2,origin='analyst_prior'),self.rows(),required=True,anchors=anchors)
  r=self.report(2,origin='analyst_prior');r['probability']['calculation']['direct_anchor_reason']='合約包括評估前已發生的減息，與問題窗口不同 [poly]'
  materialize(r,self.rows(),required=True,anchors=anchors)
  materialize(self.report(3.5),self.rows(),required=True,anchors=anchors)

class NoSilentSubstitution(unittest.TestCase):
 """Finding 2: missing identifiers must not silently become SPY / GOLD / market."""
 def plan(self,signals):
  return {'core_variable':'x','horizon':'2026-09-30 至 2026-12-30','priceability':'p','signals':signals}
 def sig(self,sid,source,**kw):
  return {'id':sid,'source':source,'label':'l','layer':'L','reason':'r','horizon':'h',**kw}
 def test_missing_identifier_is_rejected_not_defaulted(self):
  from analysis import validate_plan
  out=validate_plan(self.plan([self.sig('ok','yahoo',ticker='GC=F'),self.sig('no_ticker','yahoo'),self.sig('no_search','polymarket'),self.sig('no_commodity','cftc')]))
  self.assertEqual([s['id'] for s in out['signals']],['ok'])
  self.assertEqual({x['id'] for x in out['rejected_signals']},{'no_ticker','no_search','no_commodity'})
 def test_all_invalid_still_fails(self):
  from analysis import validate_plan
  with self.assertRaises(ValueError):validate_plan(self.plan([self.sig('no_ticker','yahoo')]))
 def test_eastmoney_requires_a_six_digit_code(self):
  import sources
  with self.assertRaisesRegex(ValueError,'6位'):sources.fetch('eastmoney',{'ticker':'HSI'})

class CryptoAnnualization(unittest.TestCase):
 """Finding 4: all Yahoo crypto pairs trade 365 days a year."""
 def test_crypto_pairs_use_365(self):
  from analysis import annualization_days
  for s in ('BTC-USD','ETH-USD','SOL-USD','DOGE-USD'):self.assertEqual(annualization_days(s),365)
  for s in ('SPY','GC=F','JPY=X','0016.HK','^HSI'):self.assertEqual(annualization_days(s),252)

class TopicProfiles(unittest.TestCase):
 """Finding 6: popular topics get a curated core signal list."""
 def test_profiles_route_and_are_valid(self):
  from signal_policy import profile,apply_policy
  from analysis import validate_plan
  cases={'未來12個月爆發第三次世界大戰的機率有多大？請用油價分析':'war','未來12個月台海爆發軍事衝突的機率有多大？':'taiwan','未來12個月美國陷入經濟衰退的機率有多大？':'recession','未來6個月納斯達克100指數較目前下跌至少20%的機率？AI 泡沫':'ai_tech','未來三個月布蘭特原油升穿每桶100美元的機率有多大？':'oil','香港樓價未來12個月會升還是跌？':'hk_market','恒生指數未來三個月較目前升超過10%的機率有多大？':'hk_market','美元兌日圓未來三個月跌穿140的機率有多大？':'jpy','美國與伊朗局勢會否升級？':'war','未來三個月美國減息機會':'rates'}
  for q,want in cases.items():
   self.assertEqual(profile(q),want,q)
   plan=apply_policy(q,{'core_variable':'x','horizon':'2026-09-30 至 2026-12-30','priceability':'p','signals':[]})
   if want!='rates':self.assertGreaterEqual(len(plan['signals']),6,q)
   checked=validate_plan(plan);self.assertEqual(checked.get('rejected_signals',[]),[],q)

class NumericHistoricalBand(unittest.TestCase):
 """Finding 7: numeric forecasts carry an objective historical-variability band."""
 def test_band_widens_with_years_ahead(self):
  from answer_types import historical_band
  b=historical_band(3.7,'2025',{'std':1.1654,'mean_absolute':.74},'2027-01-01至2027-12-31',[0,100])
  self.assertEqual(b['years_ahead'],2)
  self.assertAlmostEqual(b['one_sd_pp'],1.1654*2**.5,places=3)
  self.assertAlmostEqual(b['range'][0],round(3.7-1.1654*2**.5,2));self.assertAlmostEqual(b['range'][1],round(3.7+1.1654*2**.5,2))
 def test_band_respects_bounds_and_missing_data(self):
  from answer_types import historical_band
  self.assertEqual(historical_band(0.5,'2025',{'std':2},'2026-01-01至2026-12-31',[0,100])['range'][0],0)
  self.assertIsNone(historical_band(3.7,'2025',{},'2027',[0,100]))

if __name__=='__main__':unittest.main()
