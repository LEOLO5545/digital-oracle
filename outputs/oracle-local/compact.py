"""Lossless shared contract text and bounded model context; original evidence untouched."""
import copy,hashlib,json
from quant import evidence_for_model

def report_evidence(rows):
 sources=copy.deepcopy(evidence_for_model(rows));rules={};markets={}
 for row in sources:
  if row.get('provider')=='web':
   # Search is a locator, not an opinion channel. Original snippets remain downloadable.
   data=row.get('data') or {}
   row['data']={'query':data.get('query'),'candidate_urls':[s.get('url') for s in data.get('snippets',[]) if isinstance(s,dict)],'note':'未核對原頁的搜尋線索；文字摘要不送入判斷。'}
  if row.get('provider')!='polymarket' or not isinstance(row.get('data'),list):continue
  for event in row['data']:
   refs=[]
   for market in event.get('markets',[]):
    text=market.get('description')
    if text:
     market.pop('description')
     key=hashlib.sha256(text.encode()).hexdigest()[:16];rules[key]=text;market['rules_ref']=key
    key=hashlib.sha256(json.dumps(market,sort_keys=True).encode()).hexdigest()[:16]
    markets[key]=market;refs.append(key)
   event.pop('markets',None);event['market_refs']=refs
 packed={'sources':sources,'markets_by_ref':markets,'rules_by_ref':rules,'note':'market_refs及rules_ref是精確去重引用，不是缺失資料；來源id仍用於報告引用。'}
 restored=unpack_sources(packed)
 baseline=evidence_for_model(rows)
 if [r for r in restored if r.get('provider')!='web']!=[r for r in baseline if r.get('provider')!='web']:raise ValueError('金融證據去重前後不一致')
 return packed

def unpack_sources(packed):
 sources=copy.deepcopy(packed['sources'])
 for row in sources:
  if row.get('provider')!='polymarket' or not isinstance(row.get('data'),list):continue
  for event in row['data']:
   event['markets']=[]
   for key in event.pop('market_refs',[]):
    market=copy.deepcopy(packed['markets_by_ref'][key])
    if 'rules_ref' in market:market['description']=packed['rules_by_ref'][market.pop('rules_ref')]
    event['markets'].append(market)
 return sources

def report_quant(q):
 # Retain every computed pair and counter-signal; size alone is not a relevance test.
 return q

def report_plan(plan):return {k:v for k,v in plan.items() if k not in ('signals','sources')}

def canonical_contracts(rows):
 """One current snapshot per market ID, with every search hit and full rule variants."""
 import hashlib,json
 markets={};rules={};sources=[]
 for row in rows:
  provider=row.get('provider');data=row.get('data');sid=row['id'];sources.append({'id':sid,'provider':provider,'checked_at':row.get('checked_at')})
  if provider=='polymarket':items=[m for e in data or [] if isinstance(e,dict) for m in e.get('markets',[])]
  elif provider=='kalshi':items=(data or {}).get('markets',[])
  else:continue
  for m in items:
   mid=str(m.get('id') or m.get('ticker') or hashlib.sha256(json.dumps(m,sort_keys=True).encode()).hexdigest()[:16]);key=provider+':'+mid
   fields=('id','question','outcomes','outcomePrices','bestBid','bestAsk','volume','liquidity','endDate','closed','rules_truncated') if provider=='polymarket' else ('ticker','title','yes_bid','yes_ask','no_bid','no_ask','volume','liquidity','close_time','status','rules_truncated')
   v={k:m[k] for k in fields if k in m};v['hits']=[sid]
   refs=[]
   for field in ('description','rules_primary','rules_secondary'):
    value=m.get(field)
    if value:
     ref=hashlib.sha256(value.encode()).hexdigest()[:12];rules[ref]=value;refs.append(ref)
   v['rules']=refs;v['quote_as_of']=m.get('updatedAt') or row.get('checked_at') or ''
   if key in markets:
    old=markets[key];hits=sorted(set(old['hits']+[sid]));variants=sorted(set(old['rules']+refs))
    if v['quote_as_of']<old['quote_as_of']:v=old
    v['hits']=hits;v['rules']=variants
    if old.get('rule_conflict') or set(old['rules'])!=set(refs):v['rule_conflict']=True
   markets[key]=v
 return {'sources':sources,'markets':markets,'rules':rules,'note':'相同ID只取最新回應；hits保留搜尋來源；完整條款共用rules，不合併不同期限合約。'}

def tabular_context(value):
 """Lossless columns/rows encoding for repeated record keys; never drops values."""
 if isinstance(value,dict):return {k:tabular_context(v) for k,v in value.items()}
 if isinstance(value,list):
  if len(value)>=3 and all(isinstance(v,dict) for v in value):
   columns=list(dict.fromkeys(k for v in value for k in v))
   # Only homogeneous records: missing and null remain distinct in other lists.
   if all(set(v)==set(columns) for v in value):
    table={'columns':columns,'rows':[[tabular_context(v[k]) for k in columns] for v in value]}
    if len(json.dumps(table))<len(json.dumps(value)):return table
  return [tabular_context(v) for v in value]
 return value

def shared_context(value):
 """Reference identical long strings (e.g. settlement rules) across all sections."""
 texts={};counts={}
 def count(v):
  if isinstance(v,str) and len(v)>300:counts[v]=counts.get(v,0)+1
  elif isinstance(v,dict):
   for x in v.values():count(x)
  elif isinstance(v,list):
   for x in v:count(x)
 count(value)
 def pack(v):
  if isinstance(v,str) and counts.get(v,0)>1:
   ref=hashlib.sha256(v.encode()).hexdigest()[:12];texts[ref]=v;return {'text_ref':ref}
  if isinstance(v,dict):return {k:pack(x) for k,x in v.items()}
  if isinstance(v,list):return [pack(x) for x in v]
  return v
 data=pack(value)
 return {'data':tabular_context(data),'texts':texts,'encoding':'columns/rows為無損表格；text_ref引用texts完整原文，非缺漏。'}
