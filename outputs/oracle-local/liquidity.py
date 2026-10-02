"""Auditable term interpolation. Never equates related contract definitions."""
import datetime as dt
import json, math, re

def timestamp(value):
 return dt.datetime.fromisoformat(value.replace('Z','+00:00'))

def deadline(question, horizon=""):
 """Exclusive cutoff: the question's own date, else the LAST date written in the plan horizon."""
 pattern=r'(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})'
 m=re.search(pattern,question)
 # Audit fix: "next N months" questions carry their end date only in the plan horizon.
 parts=m.groups() if m else (re.findall(pattern,horizon or '') or [None])[-1]
 if not parts:return None
 # An unspecified timezone is explicitly assumed Hong Kong, inclusive of named day.
 day=dt.date(*map(int,parts))+dt.timedelta(days=1)
 zone=dt.timezone.utc if re.search(r'UTC|世界協調',question+' '+horizon,re.I) and not re.search(r'香港|HKT|UTC\+0?8',question+' '+horizon,re.I) else dt.timezone(dt.timedelta(hours=8))
 return dt.datetime.combine(day,dt.time(),zone).isoformat()

def interpolate(markets,target,as_of):
 """Input must be a same-event family; exact complete rules further partition it."""
 target=timestamp(target);now=timestamp(as_of);groups={};references=[]
 for m in markets:
  try:
   outcomes=m.get('outcomes');outcomes=json.loads(outcomes) if isinstance(outcomes,str) else outcomes
   bid,ask,volume,liq=map(float,(m['bestBid'],m['bestAsk'],m['volume'],m['liquidity']))
   end=timestamp(m['endDate']);rules=m.get('description','').strip()
   if m.get('closed') or m.get('rules_truncated') or not rules or outcomes!=['Yes','No']:continue
   if end<=now or not all(math.isfinite(v) for v in (bid,ask,volume,liq)) or not 0<=bid<=ask<=1 or ask-bid>.1 or liq<=0:continue
   item={'id':m['id'],'question':m.get('question'),'end':m['endDate'],'midpoint_pct':50*(bid+ask),'bid_pct':100*bid,'ask_pct':100*ask,'volume_usd':volume,'liquidity_usd':liq}
   references.append(item)
   if volume>=100000:groups.setdefault(rules,[]).append((end,item))
  except (KeyError,TypeError,ValueError):continue
 results=[]
 for rules,items in groups.items():
  before=[x for x in items if x[0]<=target];after=[x for x in items if x[0]>=target]
  if not before or not after:continue
  a=min(before,key=lambda x:target-x[0]);b=min(after,key=lambda x:x[0]-target)
  if a[1]['midpoint_pct']>b[1]['midpoint_pct']:continue # Non-monotone cumulative claims cannot be smoothed silently.
  w=(target-a[0]).total_seconds()/(b[0]-a[0]).total_seconds() if a[0]!=b[0] else 0
  low=a[1]['midpoint_pct'];high=b[1]['midpoint_pct']
  results.append({'earlier':a[1],'later':b[1],'weight_later':w,'anchor_pct':low+(high-low)*w,'quote_band_pct':[a[1]['bid_pct']*(1-w)+b[1]['bid_pct']*w,a[1]['ask_pct']*(1-w)+b[1]['ask_pct']*w],'monotonicity_only_bounds_pct':[low,high],'constant_hazard_anchor_pct':100*(1-(1-low/100)**(1-w)*(1-high/100)**w),'rules':rules,'assumption':'相同完整條款之累積事件機率在兩期限間線性插值；另列固定風險率曲線作對照。報價帶不是統計信賴區間；成交額門檻並不證明當前深度充足。'})
 return {'candidates':results,'low_volume_reference_only':[x for x in references if x['volume_usd']<100000]}

DIRECT_MIN_VOLUME=100000;DIRECT_MAX_SPREAD=.1;DIRECT_MAX_GAP_DAYS=14

def direct_candidates(rows,target,as_of):
 """Liquid Yes/No contracts whose stated deadline is within two weeks of the question's cutoff.
 Both the Yes price and its complement are shown, because 'no event happens' markets price the
 question in reverse. Rules still decide whether a contract matches; the gap is disclosed."""
 target=timestamp(target);now=timestamp(as_of);out=[];seen=set()
 for row in rows:
  if row.get('status')!='ok':continue
  if row.get('provider')=='polymarket' and isinstance(row.get('data'),list):
   for event in row['data']:
    for m in event.get('markets',[]) if isinstance(event,dict) else []:
     try:
      outcomes=m.get('outcomes');outcomes=json.loads(outcomes) if isinstance(outcomes,str) else outcomes
      bid,ask,volume=float(m['bestBid']),float(m['bestAsk']),float(m['volume']);end=timestamp(m['endDate'])
     except (KeyError,TypeError,ValueError):continue
     key=('polymarket',m.get('id'))
     if key in seen or m.get('closed') or outcomes!=['Yes','No'] or end<=now:continue
     if not (math.isfinite(bid) and math.isfinite(ask) and 0<=bid<=ask<=1) or ask-bid>DIRECT_MAX_SPREAD or volume<DIRECT_MIN_VOLUME:continue
     gap=(end-target).total_seconds()/86400
     if abs(gap)>DIRECT_MAX_GAP_DAYS:continue
     seen.add(key)
     out.append({'signal_id':row['id'],'provider':'polymarket','market_id':m.get('id'),'question':m.get('question'),'deadline':m['endDate'],'deadline_gap_days':round(gap,2),'yes_bid_pct':100*bid,'yes_ask_pct':100*ask,'yes_mid_pct':50*(bid+ask),'no_mid_pct':100-50*(bid+ask),'volume_usd':volume,'rules':(m.get('description') or '')[:600],'rules_truncated':bool(m.get('rules_truncated'))})
  if row.get('provider')=='kalshi' and isinstance(row.get('data'),dict):
   for m in row['data'].get('markets',[]):
    try:bid,ask,volume=float(m['yes_bid']),float(m['yes_ask']),float(m['volume']);end=timestamp(m['close_time'])
    except (KeyError,TypeError,ValueError):continue
    if m.get('status') not in (None,'active','open') or end<=now or not (0<=bid<=ask<=1) or ask-bid>DIRECT_MAX_SPREAD or volume<DIRECT_MIN_VOLUME:continue
    # Kalshi decision markets are single-event outcomes inside the window, not cumulative claims.
    if end>target:continue
    out.append({'signal_id':row['id'],'provider':'kalshi','market_id':m.get('ticker'),'question':m.get('title'),'deadline':m['close_time'],'deadline_gap_days':round((end-target).total_seconds()/86400,2),'within_window_single_event':True,'yes_bid_pct':100*bid,'yes_ask_pct':100*ask,'yes_mid_pct':50*(bid+ask),'no_mid_pct':100-50*(bid+ask),'volume_usd':volume,'rules':(m.get('rules_primary') or '')[:600]})
 # Cumulative/whole-window contracts first; single-meeting Kalshi outcomes are secondary context.
 poly=sorted([x for x in out if x['provider']=='polymarket'],key=lambda x:-x['volume_usd'])[:10]
 kal=sorted([x for x in out if x['provider']=='kalshi'],key=lambda x:(x['deadline'],-x['volume_usd']))[:8]
 return poly+kal

def liquidity_anchors(rows,question,as_of,horizon=""):
 target=deadline(question,horizon)
 result={'target_exclusive':target,'timezone_assumption':'日期包含當日；依問題或研究計劃明示時區，未指定時採香港時間。target_exclusive是唯一計算截止時間，與合約實際UTC到期時間分開。','minimum_volume_usd':100000,'families':[]}
 result['direct']=[]
 if not target:return result
 result['direct']=direct_candidates(rows,target,as_of)
 result['direct_note']='direct：期限與問題截止相差不超過14日、成交≥USD 100K、買賣價差≤10個百分點的Yes/No合約；no_mid_pct是「事件不發生」合約的反向讀數。仍須逐條核對rules與問題定義；Kalshi單次會議合約只是窗口內其中一個事件，不是累計機率。'
 seen=set()
 for row in rows:
  if row.get('provider')!='polymarket' or row.get('status')!='ok':continue
  for event in row.get('data',[]) if isinstance(row.get('data'),list) else []:
   key=event.get('url')
   if not key or key in seen:continue
   seen.add(key)
   computed=interpolate(event.get('markets',[]),target,as_of)
   if computed['candidates'] or computed['low_volume_reference_only']:result['families'].append({'signal_id':row['id'],'title':event.get('title'),'url':key,**computed})
 return result
