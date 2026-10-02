import unittest
from routing import preset_plan
from signal_policy import apply_policy
class PolicyTests(unittest.TestCase):
 def test_ukraine_core_and_ttf_replaces_us_gas(self):
  p=apply_policy('俄烏',preset_plan('俄烏全面停火宣佈：截至2026年11月30日','2026-09-30'))
  core={s.get('ticker') for s in p['signals'] if s['tier']=='core'}
  self.assertTrue({'ZW=F','USDRUB=X','RHM.DE','BA.L','LDO.MI','TTF=F','BZ=F'}<=core)
  self.assertNotIn('NG=F',{s.get('ticker') for s in p['signals']})
 def test_rates_require_contracts_and_funding(self):
  p=apply_policy('未來三個月美國減息機會',{'signals':[],'horizon':'三個月'})
  self.assertTrue({'polymarket','kalshi','fred','treasury','yahoo'}<={s['source'] for s in p['signals']})
  self.assertTrue(all(s['tier']=='core' for s in p['signals']))
 def test_rates_supported_question_uses_calendar_preset(self):
  p=preset_plan('未來三個月美國減息機會','2026-09-30T00:00:00+00:00')
  self.assertTrue(p['preset']);self.assertIn('2026-12-30',p['horizon'])
  self.assertIn('KXFEDDECISION',{s.get('series') for s in p['signals']})
