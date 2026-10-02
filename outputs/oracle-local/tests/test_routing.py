import unittest
from routing import route_plan,regional_signals
class RoutingTests(unittest.TestCase):
 def test_ukraine_has_regional_assets_and_bounded_menu(self):
  rows=regional_signals('俄烏全面停火宣佈：截至2026年11月30日','2026-11-30')
  self.assertTrue({'ZW=F','USDRUB=X','RHM.DE','BA.L','LMT','RTX','ITA'} <= {r.get('ticker') for r in rows})
  self.assertTrue(20<=len(rows)<=28)
  self.assertTrue(all(all(r['routing'].get(k) for k in ('relevance','time_match','information_increment')) for r in rows))
  self.assertEqual({r['layer'] for r in rows if r.get('ticker') in ('^VIX','NG=F')},{'宏觀背景'})
 def test_unrelated_question_is_unchanged(self):
  p={'horizon':'h','signals':[]};self.assertEqual(route_plan('Bitcoin',p),p)

 def test_exact_dated_question_has_a_no_model_preset(self):
  from routing import preset_plan
  p=preset_plan('俄烏全面停火宣佈：截至2026年11月30日','2026-09-30T00:00:00+00:00')
  self.assertTrue(p['preset']);self.assertIn('香港時間',p['horizon']);self.assertTrue(20<=len(p['signals'])<=28)
  self.assertIsNone(preset_plan('俄烏何時停火？','2026-09-30'))
