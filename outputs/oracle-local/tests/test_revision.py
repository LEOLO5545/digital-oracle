import json,unittest
from unittest.mock import Mock
from evaluation import audit_and_revise
from analysis import validate_report
from language import traditional
from test_analysis import report
class RevisionTests(unittest.TestCase):
 def test_one_rewrite_and_recheck(self):
  original=report();revised=report();revised['conclusion']='公開證據，憑報價判斷。'
  finding={'findings':[dict(severity='major',location='conclusion',problem='文字與證據不符',fix='修正結論')]}
  model=Mock(side_effect=[json.dumps(finding),json.dumps({'changes':[{'path':'/conclusion','value':revised['conclusion']}]}),json.dumps({'findings':[]})])
  r,a,h=audit_and_revise(original,[{'id':'gold','status':'ok'}],{},model,validate_report,traditional)
  self.assertTrue(a['passed']);self.assertEqual(model.call_count,3);self.assertEqual(h[0]['original_report'],original);self.assertEqual(r,revised)
 def test_persistent_findings_stop_after_one_rewrite(self):
  f={'findings':[dict(severity='major',location='x',problem='x',fix='x')]};m=Mock(side_effect=[json.dumps(f),json.dumps({'changes':[{'path':'/conclusion','value':'c'}]}),json.dumps(f)])
  r,a,h=audit_and_revise(report(),[{'id':'gold','status':'ok'}],{},m,validate_report,traditional)
  self.assertFalse(a['passed']);self.assertEqual(m.call_count,3)
 def test_conversion_preserves_identifiers_and_numbers(self):
  self.assertEqual(traditional({'conclusion':'公开凭证','signal_id':'public','n':11}),{'conclusion':'公開憑證','signal_id':'public','n':11})

 def test_recheck_failure_keeps_valid_revised_report(self):
  f={'findings':[dict(severity='major',location='x',problem='x',fix='x')]}
  revised=report();revised['conclusion']='修正版'
  m=Mock(side_effect=[json.dumps(f),json.dumps({'changes':[{'path':'/conclusion','value':revised['conclusion']}]}),RuntimeError('timeout')])
  r,a,h=audit_and_revise(report(),[{'id':'gold','status':'ok'}],{},m,validate_report,traditional)
  self.assertEqual(r['conclusion'],'修正版');self.assertFalse(a['passed'])

 def test_citation_ranges_expand_only_known_sources(self):
  from language import report_language
  rows=[{'id':f'ru_{n:02}'} for n in range(5,8)]
  self.assertEqual(report_language('[ru_05至ru_07]',rows),'[ru_05] [ru_06] [ru_07]')
  with self.assertRaises(ValueError):report_language('[ru_05至ru_08]',rows)

 def test_patch_preserves_unaffected_layers_and_rejects_unknown_paths(self):
  from evaluation import apply_changes
  original=report();revised=apply_changes(original,[{'path':'/probability/estimate','value':31}])
  self.assertEqual(revised['layers'],original['layers']);self.assertEqual(original['probability']['estimate'],30)
  with self.assertRaises(ValueError):apply_changes(original,[{'path':'/unknown','value':1}])

 def test_saved_audit_resumes_at_patch_without_repeating_initial_review(self):
  f={'findings':[dict(severity='major',location='conclusion',problem='p',fix='f')]}
  m=Mock(side_effect=[json.dumps({'changes':[{'path':'/conclusion','value':'修正版'}]}),json.dumps({'findings':[]})])
  r,a,h=audit_and_revise(report(),[{'id':'gold','status':'ok'}],{},m,validate_report,traditional,initial_audit=f)
  self.assertEqual(m.call_count,2);self.assertTrue(a['passed']);self.assertEqual(r['conclusion'],'修正版')

 def test_focused_audit_keeps_conclusion_but_not_tables(self):
  original=report();original['headline_summary']='初步結論'
  model=Mock(return_value=json.dumps({'findings':[]}))
  _,audit,_=audit_and_revise(original,[{'id':'gold','status':'ok'}],{},model,validate_report,traditional,focused=True)
  payload=json.loads('{'+model.call_args.args[0].split('\n{',1)[1])
  self.assertEqual(set(payload['report']),{'probability','scenarios','headline_summary','conclusion','monitor'})
  self.assertTrue(audit['passed'])
