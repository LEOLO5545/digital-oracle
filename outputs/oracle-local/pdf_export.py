"""Private, bounded PDF export of an existing report; never calls the model."""
import json,os,shutil,subprocess,tempfile,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SLOT=threading.BoundedSemaphore(1)

def export_pdf(job,port):
 if not job.get('report'):raise ValueError('目前沒有可匯出的分析報告')
 if not SLOT.acquire(blocking=False):raise RuntimeError('另一份PDF正在產生，請稍後再試')
 try:
  bundle=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node'
  node=os.environ.get('ORACLE_NODE') or shutil.which('node') or str(bundle/'bin/node')
  module=os.environ.get('ORACLE_PLAYWRIGHT_MODULE') or str(bundle/'node_modules/playwright')
  chrome=os.environ.get('ORACLE_CHROME') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
  if not Path(node).exists() or not Path(module).exists() or not Path(chrome).exists():raise RuntimeError('PDF產生工具未就緒，請檢查本機Node、Playwright及Chrome')
  with tempfile.TemporaryDirectory(prefix='oracle-pdf-') as folder:
   data=Path(folder)/'report.json';out=Path(folder)/'report.pdf'
   data.write_text(json.dumps(job,ensure_ascii=False));data.chmod(0o600)
   env={**os.environ,'ORACLE_PLAYWRIGHT_MODULE':module,'ORACLE_CHROME':chrome}
   try:
    result=subprocess.run([node,str(ROOT/'pdf_render.cjs'),str(data),str(out),str(port)],env=env,capture_output=True,text=True,timeout=75)
   except subprocess.TimeoutExpired:raise RuntimeError('PDF產生逾時，分析內容已保留，請重試') from None
   if result.returncode or not out.exists():raise RuntimeError('PDF產生未完成，請重試；原分析內容不受影響')
   content=out.read_bytes()
   if not content.startswith(b'%PDF-'):raise RuntimeError('PDF格式驗證失敗，請重試')
   return content
 finally:SLOT.release()
