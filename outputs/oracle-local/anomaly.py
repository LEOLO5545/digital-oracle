"""Deterministic escalation. Thresholds describe sample anomalies, not event probabilities."""
import math,statistics,datetime
from signal_policy import config

def series_metrics(values,cutoff=None):
 cutoff=cutoff or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
 pairs=sorted((d,float(v)) for d,v in values.items() if d<cutoff and isinstance(v,(int,float)) and math.isfinite(v))
 if not pairs:return {}
 cfg=config()['anomaly'];n=cfg['change_periods'];vs=[v for _,v in pairs];latest=vs[-1]
 # Exclude current change from the historical reference distribution.
 historical=[vs[i]-vs[i-n] for i in range(n,len(vs)-1)][-cfg['history_changes']:]
 out={'last_date':pairs[-1][0],'latest':latest,'observations':len(vs),'sample_percentile':100*sum(v<=latest for v in vs)/len(vs),'change_21_observations':latest-vs[-n-1] if len(vs)>n else None,'change_reference_count':len(historical)}
 if len(historical)>=cfg['history_changes']:out['change_21_std']=statistics.stdev(historical)
 else:out['anomaly_limit']='不足252個歷史21期變化；不使用雙標準差條件'
 return out

def triggers(stats):
 cfg=config()['anomaly'];reasons=[];p=stats.get('sample_percentile')
 if isinstance(p,(int,float)) and (p>=cfg['percentile_high'] or p<=cfg['percentile_low']):reasons.append(f'樣本分位 {p:.1f}% 達尾部門檻')
 change=stats.get('change_21_observations');sd=stats.get('change_21_std')
 if isinstance(change,(int,float)) and isinstance(sd,(int,float)) and sd>0 and abs(change)>=cfg['sigma_multiplier']*sd:reasons.append(f'21期變化達歷史標準差 {abs(change)/sd:.2f} 倍')
 return reasons

def classify(rows,quantitative,profile):
 directions=config()['profiles'].get(profile,{}).get('risk_direction',{});by_id={r['id']:r for r in rows};promotions=[]
 for row in rows:
  if row.get('status')!='ok':continue
  data=row.get('data',{});stats={}
  if isinstance(data,dict):
   values=data.get('closes') or data.get('observations')
   if isinstance(values,dict):stats=series_metrics(values)
   else:stats=data.get('managed_money_net_pct_oi') or data.get('statistics') or {}
  row['computed_statistics']=stats
  row['anomaly_reasons']=triggers(stats)
 for derived in quantitative.get('derived_series',[]):
  a,b=[by_id[x] for x in derived['signals']];av=a['data']['closes'];bv=b['data']['closes']
  values={d:av[d]-bv[d] if derived['mode']=='spread' else av[d]/bv[d] for d in av.keys()&bv.keys() if bv[d]>0}
  reasons=triggers({**derived,**series_metrics(values)})
  if reasons:
   promotions.append({'name':derived['name'],'signals':derived['signals'],'reasons':reasons,'derived':True})
   for row in (a,b):
    if row.get('tier')!='core':row['anomaly_reasons'].extend([derived['name']+'：'+x for x in reasons])
 for row in rows:
  if row.get('status')!='ok' or row.get('tier')=='core':continue
  ticker=row.get('data',{}).get('symbol') if isinstance(row.get('data'),dict) else None
  direction=directions.get(ticker);change=row.get('computed_statistics',{}).get('change_21_observations')
  if direction and isinstance(change,(int,float)):
   for core in rows:
    if core.get('tier')!='core' or core.get('status')!='ok' or not isinstance(core.get('data'),dict):continue
    core_dir=directions.get(core['data'].get('symbol'));core_change=core.get('computed_statistics',{}).get('change_21_observations')
    if core_dir and isinstance(core_change,(int,float)) and change*direction*core_change*core_dir<0 and (triggers(row['computed_statistics']) or triggers(core.get('computed_statistics',{}))):
     row['anomaly_reasons'].append('按設定風險方向與核心 '+core['name']+' 背離，至少一方達異常門檻');break
  if row.get('anomaly_reasons'):
   row['tier']='promoted';promotions.append({'name':row['name'],'signals':[row['id']],'reasons':row['anomaly_reasons'],'derived':False})
 return promotions
