import unittest,json,tempfile
from pathlib import Path
from unittest.mock import patch
import server
from test_analysis import report
class RecoveryTests(unittest.TestCase):
 def test_resume_uses_saved_evidence_without_new_collection(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'reports').mkdir();rid='d'*32
   original={'id':rid,'status':'error','question':'q','plan':{'signals':[{'id':'gold'}],'horizon':'h'},'sources':[{'id':'gold','status':'ok','provider':'yahoo','data':{}}],'quantitative':{},'created_at':'2026-09-30T00:00:00+00:00'}
   (root/'reports'/f'{rid}.json').write_text(json.dumps(original))
   with patch.object(server,'STATE',root),patch.object(server.threading,'Thread') as thread:
    job=server.resume_job(rid)
   self.assertEqual(server.JOBS[job]['sources'],original['sources'])
   self.assertEqual(server.JOBS[job]['resumed_from'],rid)
   self.assertEqual(thread.call_args.kwargs['target'],server.resume_report_job)
   server.JOBS.pop(job);server.BUSY=False
