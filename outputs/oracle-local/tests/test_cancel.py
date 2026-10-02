"""Stopping an analysis: child processes end promptly, stages stop, and saved data stays resumable."""
import sys, tempfile, threading, time, unittest
from pathlib import Path
import server

# Never write test jobs into the real report folder.
_TMP=Path(tempfile.mkdtemp(prefix='oracle-cancel-test-'));(_TMP/'reports').mkdir()
server.STATE=_TMP

def running_job(jid='a'*32):
 with server.LOCK:
  server.JOBS[jid]={'id':jid,'question':'q','status':'running','stage':'x','sources':[],'created_at':server.now()}
 server.CANCEL.clear()
 return jid

class RunTracked(unittest.TestCase):
 def setUp(self):server.CANCEL.clear()
 def test_normal_output(self):
  p=server.run_tracked([sys.executable,'-c','import sys;print(sys.stdin.read().upper())'],'hi',timeout=20)
  self.assertEqual(p.returncode,0);self.assertEqual(p.stdout.strip(),'HI')
 def test_timeout_still_raises_timeout(self):
  import subprocess
  with self.assertRaises(subprocess.TimeoutExpired):server.run_tracked([sys.executable,'-c','import time;time.sleep(30)'],'',timeout=1)
 def test_stop_kills_a_running_child_quickly(self):
  jid=running_job();started=time.monotonic();errors=[]
  def work():
   try:server.run_tracked([sys.executable,'-c','import time;time.sleep(60)'],'',timeout=120)
   except server.Cancelled as e:errors.append(e)
  t=threading.Thread(target=work);t.start();time.sleep(.5)
  server.cancel_job(jid);t.join(10)
  self.assertFalse(t.is_alive());self.assertEqual(len(errors),1)
  self.assertLess(time.monotonic()-started,8)
  self.assertEqual(server.ACTIVE,set())

class CancelRules(unittest.TestCase):
 def test_invalid_or_unknown_ids_are_rejected(self):
  with self.assertRaises(ValueError):server.cancel_job('../x')
  with self.assertRaises(ValueError):server.cancel_job('f'*32)
 def test_finished_jobs_cannot_be_stopped(self):
  jid=running_job('b'*32);server.JOBS[jid]['status']='done'
  with self.assertRaises(RuntimeError):server.cancel_job(jid)
 def test_stage_transition_stops_after_cancel(self):
  jid=running_job('c'*32);server.cancel_job(jid)
  with self.assertRaises(server.Cancelled):server.phase(jid,2)
 def test_failure_is_reported_as_user_stop(self):
  jid=running_job('d'*32);server.cancel_job(jid)
  server.record_failure(jid,RuntimeError('Codex 未完成回覆'))
  j=server.JOBS[jid];self.assertEqual(j['status'],'error');self.assertTrue(j['cancelled']);self.assertIn('已停止',j['error'])
 def test_ordinary_failure_is_unchanged(self):
  jid=running_job('e'*32)
  server.record_failure(jid,RuntimeError('模型回覆逾時'))
  j=server.JOBS[jid];self.assertFalse(j.get('cancelled',False));self.assertIn('逾時',j['error'])
 def tearDown(self):server.CANCEL.clear()

if __name__=='__main__':unittest.main()

class Shutdown(unittest.TestCase):
 def test_server_shutdown_stops_child_processes(self):
  import subprocess
  p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
  with server.ACTIVE_LOCK:server.ACTIVE.add(p)
  server.stop_children()
  self.assertIsNotNone(p.poll())
  with server.ACTIVE_LOCK:server.ACTIVE.discard(p)
  server.CANCEL.clear()
