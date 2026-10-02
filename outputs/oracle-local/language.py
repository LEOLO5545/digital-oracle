"""Normalize generated prose, preserving identifiers, URLs and original evidence."""
from opencc import OpenCC
_converter = OpenCC('s2t')
_LITERAL = {'signal_id','id','ticker','source','provider','url'}
def traditional(value, key=''):
 if isinstance(value,str):
  return value if key in _LITERAL or value.startswith(('http://','https://')) else _converter.convert(value).replace('盧佈','盧布')
 if isinstance(value,list):return [traditional(v,key) for v in value]
 if isinstance(value,dict):return {k:traditional(v,k) for k,v in value.items()}
 return value

def report_language(value, rows):
 """Expand shorthand citation ranges only when every referenced signal exists."""
 import re
 known={r['id'] for r in rows}
 def expand(match):
  prefix,start,end=match.groups();a,b=int(start),int(end)
  ids=[prefix+str(n).zfill(len(start)) for n in range(a,b+1)] if 0<=b-a<40 else []
  if not ids or any(s not in known for s in ids):raise ValueError('引用範圍包含未知訊號')
  return ' '.join('['+sid+']' for sid in ids)
 def visit(item):
  if isinstance(item,str):return re.sub(r'\[([a-z][a-z0-9_]*?)(\d+)至\1(\d+)\]',expand,item)
  if isinstance(item,list):return [visit(x) for x in item]
  if isinstance(item,dict):return {k:visit(v) for k,v in item.items()}
  return item
 return visit(traditional(value))
