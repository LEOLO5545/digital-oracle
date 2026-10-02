import unittest
from liquidity import interpolate,deadline

def market(i,end,p,v=200000,rules='Same general ceasefire rules'):
 return dict(id=i,endDate=end,description=rules,outcomes=['Yes','No'],bestBid=p-.01,bestAsk=p+.01,volume=v,liquidity=20000,closed=False)
class LiquidityTests(unittest.TestCase):
 def test_illiquid_near_contract_is_not_anchor(self):
  ms=[market('a','2026-11-01T00:00:00Z',.08),market('b','2027-01-01T00:00:00Z',.18),market('c','2026-12-01T00:00:00Z',.11,24000)]
  r=interpolate(ms,'2026-12-01T00:00:00Z','2026-09-30T00:00:00Z')
  self.assertAlmostEqual(r['candidates'][0]['anchor_pct'],8+10*30/61)
  self.assertEqual(r['low_volume_reference_only'][0]['id'],'c')
 def test_different_rules_or_missing_bracket_never_interpolate(self):
  ms=[market('a','2026-11-01T00:00:00Z',.08),market('b','2027-01-01T00:00:00Z',.18,rules='Humanitarian pause only')]
  self.assertEqual(interpolate(ms,'2026-12-01T00:00:00Z','2026-09-30T00:00:00Z')['candidates'],[])
 def test_truncated_expired_or_inverted_quotes_are_excluded(self):
  for patch in ({'rules_truncated':True},{'closed':True},{'bestBid':.5,'bestAsk':.2}):
   ms=[market('a','2026-11-01T00:00:00Z',.08),{**market('b','2027-01-01T00:00:00Z',.18),**patch}]
   self.assertFalse(interpolate(ms,'2026-12-01T00:00:00Z','2026-09-30T00:00:00Z')['candidates'])
 def test_date_is_inclusive_hong_kong(self):self.assertEqual(deadline('截至2026年11月30日'),'2026-12-01T00:00:00+08:00')

 def test_explicit_plan_timezone_is_shared_with_anchor(self):
  self.assertEqual(deadline('截至2026年11月30日','至2026年11月30日23:59（UTC）'),'2026-12-01T00:00:00+00:00')
