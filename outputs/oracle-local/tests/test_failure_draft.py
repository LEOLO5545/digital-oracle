import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import server
class FailureDraftTests(unittest.TestCase):
 def test_failure_preserves_valid_draft_for_display_and_export(self):
  job='e'*32;draft={'title':'已完成草稿','conclusion':'待核對'}
  with tempfile.TemporaryDirectory() as tmp,patch.object(server,'STATE',Path(tmp)):
   server.JOBS[job]={'id':job,'status':'running','generated_report':draft}
   try:
    server.record_failure(job,RuntimeError('模型回覆逾時（240秒）'))
    self.assertEqual(server.JOBS[job]['report'],draft)
    self.assertTrue(server.JOBS[job]['preview'])
    self.assertEqual(server.JOBS[job]['status'],'error')
   finally:server.JOBS.pop(job,None)
 def test_expired_total_budget_does_not_start_another_model(self):
  job='f'*32
  with tempfile.TemporaryDirectory() as tmp,patch.object(server,'STATE',Path(tmp)),patch.object(server,'model') as model:
   server.JOBS[job]={'id':job,'deadline_at':'2000-01-01T00:00:00+00:00'}
   try:
    with self.assertRaisesRegex(RuntimeError,'時間預算'):server.measured_model(job,'內容核對','p')
    model.assert_not_called()
   finally:server.JOBS.pop(job,None)
 def test_saved_running_job_after_restart_is_recoverable_not_running(self):
  import json
  job='9'*32
  with tempfile.TemporaryDirectory() as tmp,patch.object(server,'STATE',Path(tmp)):
   folder=Path(tmp)/'reports';folder.mkdir();(folder/(job+'.json')).write_text(json.dumps({'id':job,'status':'running','sources':[]}))
   value=server.job_view(job)
   self.assertEqual(value['status'],'error');self.assertIn('中斷',value['error'])
