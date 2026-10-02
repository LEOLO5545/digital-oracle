"""Content-free measurements; character counts use Unicode code points, not tokens."""
import datetime,json,time
from contextlib import contextmanager

def timestamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def prompt_parts(instructions,payload):
 encoded=json.dumps(payload,ensure_ascii=False)
 parts={k:len(json.dumps(v,ensure_ascii=False)) for k,v in payload.items()}
 parts['instructions']=len(instructions)
 parts['json_framing']=len(encoded)+1-sum(parts.values())+len(instructions)
 return instructions+'\n'+encoded,parts

@contextmanager
def measurement(record,kind,name,**metadata):
 start=time.monotonic();entry={'name':name,'started_at':timestamp(),**metadata}
 try:
  yield entry
  entry.setdefault('status','ok')
 except BaseException:
  entry['status']='error'
  raise
 finally:
  entry.update(ended_at=timestamp(),seconds=round(time.monotonic()-start,3))
  record(kind,entry)
