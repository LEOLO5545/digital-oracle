"""Question-specific required coverage; configurable, independent of report prose."""
import json,re
from pathlib import Path

def config():return json.loads((Path(__file__).parent/'config/analysis.json').read_text())
def profile(question):
 for key,pattern in [('ukraine',r'俄烏|俄乌|烏克蘭|乌克兰|ukrain'),('taiwan',r'台海|臺海|台灣|臺灣|台湾|taiwan'),('war',r'世界大戰|世界大战|world war|ww3|戰爭|战争|軍事衝突|军事冲突|開戰|美伊|伊朗|以色列|iran|israel'),('recession',r'衰退|recession'),('ai_tech',r'\bAI\b|AI |人工智能|納斯達克|纳斯达克|納指|nasdaq|半導體'),('oil',r'原油|油價|油价|布蘭特|brent|wti'),('hk_market',r'恒生|恆生|恒指|港股|香港樓|樓價|楼价|hang seng|港元|港幣|港币|聯匯|联汇|脫鈎|脱钩|hibor|hkd'),('jpy',r'日圓|日元|日圆|yen|jpy'),('bitcoin',r'bitcoin|btc|比特幣|比特币'),('gold',r'黃金|黄金|gold'),('rates',r'減息|减息|加息|fed|interest rate'),('equity',r'股票|個股|nvidia|nvda|tesla|aapl')]:
  if re.search(pattern,question,re.I):return key
 return 'general'
def selector(signal):
 source=signal.get('source',signal.get('provider'))
 key=signal.get('search','') if source in ('polymarket','web') else signal.get('commodity','') if source=='cftc' else signal.get('series','') if source in ('fred','kalshi','hkma') else '' if source=='southbound' else signal.get('ticker','')
 return source,key

# Web search is a quote locator only and is often blocked; these series have structured free sources.
HK_ROUTES=[(r'aggregate balance|總結餘|总结余|結餘|结余','hkma','AGG_BALANCE'),(r'overnight hibor|隔夜.{0,4}hibor|hibor.{0,6}(overnight|隔夜|o/n)','hkma','HIBOR_ON'),(r'(12|twelve)[ -]?(m|month|個月|个月).{0,8}hibor|hibor.{0,10}(12|twelve)[ -]?(m|month|個月|个月)','hkma','HIBOR_12M'),(r'(6|six)[ -]?(m|month|個月|个月).{0,8}hibor|hibor.{0,10}(6|six)[ -]?(m|month|個月|个月)','hkma','HIBOR_6M'),(r'(3|three)[ -]?(m|month|個月|个月).{0,8}hibor|hibor.{0,10}(3|three)[ -]?(m|month|個月|个月)','hkma','HIBOR_3M'),(r'hibor|銀行同業拆息|银行同业拆息','hkma','HIBOR_1M'),(r'southbound|南向|港股通.{0,6}(資金|资金|淨|净|flow)','southbound',''),(r'\brvd\b|差估署|差餉|差饷|private domestic price','rvd_hk_housing','')]
def reroute_hk(plan):
 """Move HIBOR / aggregate balance / southbound requests off web search onto their structured sources."""
 seen=set()
 for s in plan.get('signals',[]):
  if s.get('source')!='web':continue
  text=' '.join(str(s.get(k,'')) for k in ('search','label')).lower()
  for pattern,source,series in HK_ROUTES:
   if re.search(pattern,text,re.I):
    if (source,series) in seen:s['_drop']=True;break
    seen.add((source,series));s.update(source=source,series=series,search='market',rerouted_from='web')
    # answer_types tells the model to cite the official housing baseline by this id
    if source=='rvd_hk_housing' and not any(x.get('id')=='hk_housing_baseline' for x in plan['signals']):s['id']='hk_housing_baseline'
    break
 for s in plan.get('signals',[]):
  if s.get('source') in ('hkma','southbound','rvd_hk_housing') and not s.get('_drop'):seen.add((s['source'],s.get('series','')))
 plan['signals']=[s for s in plan.get('signals',[]) if not s.pop('_drop',False)]
 # Drop structured duplicates created by rerouting (same source+series asked twice).
 out=[];keys=set()
 for s in plan['signals']:
  k=(s['source'],s.get('series','')) if s['source'] in ('hkma','southbound','rvd_hk_housing') else None
  if k and k in keys:continue
  if k:keys.add(k)
  out.append(s)
 plan['signals']=out
 return plan

def apply_policy(question,plan):
 import copy
 from analysis import signal_key
 p=reroute_hk(copy.deepcopy(plan));kind=profile(question);policy=config()['profiles'][kind];known={signal_key(s) for s in p['signals']}
 for i,item in enumerate(policy.get('required',[])):
  source,key,label,layer=item;field='search' if source=='polymarket' else 'series' if source in ('fred','kalshi','hkma') else 'commodity' if source=='cftc' else 'ticker'
  s={'id':f'core_{kind}_{i}','source':source,field:key or ('' if source=='southbound' else 'SPY'),'label':label,'layer':layer,'reason':'核心清單：核對直接定價、資金成本或目標資產','horizon':p['horizon']}
  if signal_key(s) not in known:p['signals'].append(s);known.add(signal_key(s))
 for s in p['signals']:
  source,key=selector(s);s['tier']='core' if f'{source}:{key}' in policy['core'] or f'{source}:*' in policy['core'] or s.get('forecast_spec') else 'background'
  if kind=='equity' and s.get('source')=='yahoo' and s.get('ticker') not in ('SPY','QQQ','DX-Y.NYB','^VIX'):s['tier']='core'
 p['routing_profile']=kind
 return p


MAX_SIGNALS=40
def trim_to_budget(plan,limit=MAX_SIGNALS):
 """Required core signals and answer baselines are added after planning; never let them push the plan
 over the hard limit (that used to fail the whole analysis with 「訊號數目超出範圍」).
 Drops planner background signals first, web-search leads before structured data, latest-listed first."""
 signals=list(plan.get('signals',[]))
 if len(signals)<=limit:return plan
 def protected(s):return s.get('tier')=='core' or s.get('forecast_spec') or str(s.get('id','')).startswith('core_') or str(s.get('id','')).endswith('_baseline')
 order=[i for i,s in sorted(enumerate(signals),key=lambda x:(x[1].get('source')!='web',-x[0])) if not protected(s)]
 drop=set(order[:len(signals)-limit])
 kept=[s for i,s in enumerate(signals) if i not in drop]
 return {**plan,'signals':kept[:limit],'trimmed_signals':[{'id':signals[i]['id'],'label':signals[i].get('label'),'reason':'超出40個訊號上限，優先保留核心及基準訊號'} for i in sorted(drop)]}
