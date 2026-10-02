"""Descriptive cross-market calculations. These do not estimate event probabilities."""
import csv,io,math,statistics,datetime,urllib.request,ssl
import certifi,urllib.error,time
def research_today():
 return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()

def coin_quote_consistency(prices):
 by_symbol={p.get('symbol'):p for p in prices};checks=[]
 try:btc=float(by_symbol['BTC']['price_usd'])
 except (KeyError,TypeError,ValueError):return checks
 for symbol,p in by_symbol.items():
  if symbol=='BTC':continue
  try:usd=float(p['price_usd']);cross=float(p['price_btc'])*btc
  except (KeyError,TypeError,ValueError):continue
  if usd<=0 or not all(math.isfinite(x) for x in (usd,cross)):continue
  deviation=100*(cross/usd-1)
  checks.append({'symbol':symbol,'reported_usd':usd,'btc_cross_implied_usd':cross,'difference_pct':deviation,'flagged':abs(deviation)>2,'note':'2%為資料一致性檢查閾值，並非交易訊號；不同欄位可能不同步，欠逐筆時間戳時不能視作套利機會。'})
 return checks

FRED_SERIES={
 'DFF':('有效聯邦基金利率','percent'),
 'SOFR':('有抵押隔夜融資利率','percent'),
 'BAMLH0A0HYM2':('美國高收益債OAS','percentage points'),
 'BAMLC0A0CM':('美國投資級債OAS','percentage points'),
 'BAMLH0A3HYC':('美國CCC級債OAS','percentage points'),
 'T10YIE':('美國10年盈虧平衡通脹','percent'),
 'DFII10':('美國10年實質國債收益率','percent'),
 'T10Y2Y':('美國10年減2年國債息差','percentage points'),
 'VIXCLS':('CBOE VIX收市指數','index points'),
}
def series_summary(values):
 pairs=sorted((d,float(v)) for d,v in values.items() if math.isfinite(float(v)))
 if len(pairs)<2:raise ValueError('有效時間序列不足')
 latest=pairs[-1][1];vs=[v for _,v in pairs]
 out={'first_date':pairs[0][0],'last_date':pairs[-1][0],'observations':len(pairs),'latest':latest,'sample_min':min(vs),'sample_max':max(vs),'sample_percentile':100*sum(v<=latest for v in vs)/len(vs)}
 for n in (5,21,63):out[f'change_{n}_observations']=latest-pairs[-n-1][1] if len(pairs)>n else None
 out['note']='分位數只相對本次樣本，不代表完整歷史或事件概率。變化按資料觀察期，不是日曆日。'
 return out

def parse_fred(text,series):
 rows=list(csv.DictReader(io.StringIO(text)))
 if not rows or series not in rows[0]:raise ValueError('FRED CSV 欄位不符')
 values={}
 for row in rows:
  date=row.get('observation_date') or row.get('DATE')
  try:value=float(row[series]);datetime.date.fromisoformat(date)
  except (ValueError,TypeError):continue
  if math.isfinite(value):values[date]=value
 return {'series':series,'name':FRED_SERIES[series][0],'units':FRED_SERIES[series][1],'statistics':series_summary(values),'observations':values,'url':'https://fred.stlouisfed.org/series/'+series,'note':'FRED發布的金融市場序列；抓取時間不是觀察時間，樣本可能延遲或修訂。第三方序列的商用再分發權利未核定。'}

def fetch_fred(series):
 if series not in FRED_SERIES:raise ValueError('未支援FRED序列')
 start=(research_today()-datetime.timedelta(days=550)).isoformat()
 url='https://fred.stlouisfed.org/graph/fredgraph.csv?id='+series
 req=urllib.request.Request(url)
 # The caller owns the single retry budget.
 with urllib.request.urlopen(req,context=ssl.create_default_context(cafile=certifi.where()),timeout=18) as r:text=r.read(2_000_000).decode('utf-8-sig')
 data=parse_fred(text,series)
 data['observations']={d:v for d,v in data['observations'].items() if d>=start}
 data['statistics']=series_summary(data['observations'])
 return data

def correlation(xs,ys):
 if len(xs)<20 or len(xs)!=len(ys):return None
 mx=statistics.mean(xs);my=statistics.mean(ys)
 den=math.sqrt(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
 return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/den if den else None

def paired(a,b,window=126):
 # Align CLOSE DATES before computing returns, so each return spans identical endpoints.
 cutoff=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
 dates=sorted(d for d in set(a)&set(b) if d<cutoff)[-window-1:]
 dates=[d for d in dates if a[d]>0 and b[d]>0]
 if len(dates)<21:return None
 ra=[math.log(a[y]/a[x]) for x,y in zip(dates,dates[1:])]
 rb=[math.log(b[y]/b[x]) for x,y in zip(dates,dates[1:])]
 recent=min(21,len(dates)-1)
 return {'from':dates[0],'to':dates[-1],'common_return_intervals':len(ra),'return_correlation':correlation(ra,rb),'recent_return_correlation':correlation(ra[-21:],rb[-21:]),'relative_return_21_common_observations_pp':100*((a[dates[-1]]/a[dates[-recent-1]]-1)-(b[dates[-1]]/b[dates[-recent-1]]-1))}

def change_return_pair(levels,prices,window=126):
 cutoff=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
 dates=sorted(d for d in set(levels)&set(prices) if d<cutoff and prices[d]>0)[-window-1:]
 if len(dates)<21:return None
 changes=[levels[y]-levels[x] for x,y in zip(dates,dates[1:])]
 returns=[math.log(prices[y]/prices[x]) for x,y in zip(dates,dates[1:])]
 return {'from':dates[0],'to':dates[-1],'common_return_intervals':len(changes),'change_return_correlation':correlation(changes,returns),'recent_change_return_correlation':correlation(changes[-21:],returns[-21:]),'method':'共同日期的金融序列絕對變動，對同期間價格log回報；不是收益率水平相關性。'}

def cross_market(rows):
 prices={r['id']:r for r in rows if r.get('status')=='ok' and r.get('provider')=='yahoo' and r.get('data',{}).get('closes')}
 comparisons=[]
 ids=list(prices)
 for i,aid in enumerate(ids):
  for bid in ids[i+1:]:
   p=paired(prices[aid]['data']['closes'],prices[bid]['data']['closes'])
   if p:comparisons.append({'a':aid,'b':bid,**p})
 lookup={r['data']['symbol']:r for r in prices.values()};derived=[]
 for x,y,label,mode in [('BZ=F','CL=F','Brent－WTI每桶美元價差','spread'),('HG=F','GC=F','銅金價格比率（不同報價單位，非無單位價值比）','ratio'),('GC=F','SI=F','金銀比率','ratio'),('ITA','SPY','軍工相對大市價格比率','ratio'),('XLY','XLP','可選消費相對必需消費','ratio'),('HYG','IEF','高收益債ETF相對國債ETF價格比率，非OAS','ratio')]:
  if x not in lookup or y not in lookup:continue
  ar=lookup[x];br=lookup[y];a=ar['data']['closes'];b=br['data']['closes']
  series={d:a[d]-b[d] if mode=='spread' else a[d]/b[d] for d in sorted(set(a)&set(b)) if b[d]>0 and d<datetime.datetime.now(datetime.timezone.utc).date().isoformat()}
  if len(series)<2:continue
  derived.append({'name':label,'signals':[ar['id'],br['id']],'mode':mode,**series_summary(series)})
 strongest=sorted(comparisons,key=lambda p:abs(p['return_correlation'] or 0),reverse=True)
 targets={r['id'] for r in prices.values() if r['data'].get('terminal_return_baselines')}
 rates={r['data'].get('series'):r for r in rows if r.get('status')=='ok' and r.get('provider') in ('fred','hkma') and r.get('data',{}).get('observations')}
 transmission=[]
 for series,tickers in [('DFII10',('GC=F','BTC-USD','QQQ','TLT')),('BAMLH0A0HYM2',('SPY','HYG','BTC-USD')),('T10YIE',('CL=F','TIP')),('T10Y2Y',('KRE',)),('HIBOR_1M',('^HSI','0016.HK','0823.HK','0012.HK','2388.HK','0005.HK')),('HIBOR_3M',('^HSI','0016.HK','0823.HK','2388.HK')),('AGG_BALANCE',('^HSI','0016.HK','2388.HK'))]:
  if series not in rates:continue
  for ticker in tickers:
   if ticker not in lookup:continue
   a=rates[series];b=lookup[ticker];pair=change_return_pair(a['data']['observations'],b['data']['closes'])
   if pair:transmission.append({'a':a['id'],'b':b['id'],'change_units':a['data']['units'],**pair})
 return {'method':'排除UTC當日日線後，按共同日期配對計算log回報Pearson相關性，最多126個共同觀察期；不足20期或零變異不估算。未作假設檢定或多重比較校正。','cautions':['相關性不是因果關係，也不能直接換算事件概率。','高相關或低相關都不能證明訊號獨立；相同ETF與成分股仍需合併判讀。','市場時區、收市時點、轉倉及樣本選擇可影響結果。'], 'price_series_count':len(prices),'pair_count':len(comparisons),'strongest_pairs':strongest[:18],'cross_layer_pairs':[p for p in strongest if prices[p['a']].get('layer')!=prices[p['b']].get('layer')][:12],'target_pairs':[p for p in comparisons if p['a'] in targets or p['b'] in targets],'rate_change_price_return_pairs':transmission,'derived_series':derived}

def evidence_for_model(rows):
 # Keep exact series for local calculations/download, send compact statistics to the model.
 out=[]
 for row in rows:
  r=dict(row)
  if isinstance(r.get('data'),dict):r['data']={k:v for k,v in r['data'].items() if k not in ('closes','observations','history','chain')}
  if row.get('provider')=='yahoo' and isinstance(row.get('data'),dict):
   cutoff=row['data'].get('statistics',{}).get('volatility_last_date')
   closes=row['data'].get('closes',{})
   prices=sorted((d,v) for d,v in (closes.items() if isinstance(closes,dict) else []) if cutoff and d<=cutoff and isinstance(v,(int,float)) and v>0)
   if prices:
    r['data']['completed_statistics']={'last_date':prices[-1][0],'last_close':prices[-1][1],'observations':len(prices),'current_drawdown_from_sample_peak_pct':100*(prices[-1][1]/max(v for _,v in prices)-1),'method':'按取數時已完成日線的截止日期計算，不把當日暫值當收市價',**{f'return_{n}_observations_pct':100*(prices[-1][1]/prices[-n-1][1]-1) if len(prices)>n else None for n in (5,21,63)}}
  out.append(r)
 return out


def treasury_history(curves):
 def date(s):
  try:return datetime.date.fromisoformat(s)
  except ValueError:return datetime.datetime.strptime(s,'%m/%d/%Y').date()
 ordered=sorted(curves,key=lambda x:date(x.date))
 if not ordered:raise ValueError('國債曲線沒有資料')
 spread={date(x.date).isoformat():x.spread('10Y','2Y') for x in ordered if x.spread('10Y','2Y') is not None}
 return ordered[-1],series_summary(spread)

def terminal_return_baselines(values,threshold_pct,calendar_days,annualization_days=252):
 """Historical frequency and constant-volatility scenarios; NOT calibrated forecasts."""
 import bisect
 if not -100<threshold_pct<500 or not 1<=calendar_days<=366:raise ValueError('目標回報或期限無效')
 pairs=sorted((datetime.date.fromisoformat(d),v) for d,v in values.items() if math.isfinite(v) and v>0 and datetime.date.fromisoformat(d)<datetime.datetime.now(datetime.timezone.utc).date())
 if len(pairs)<100:raise ValueError('歷史分布樣本不足100筆')
 dates=[d for d,v in pairs];prices=[v for d,v in pairs];threshold=threshold_pct/100
 terminal=[];disjoint=[];next_start=0
 for i,start in enumerate(dates):
  end=start+datetime.timedelta(days=calendar_days);j=bisect.bisect_left(dates,end)
  if j>=len(dates) or (dates[j]-end).days>7:continue
  ret=prices[j]/prices[i]-1;hit=ret<=threshold if threshold<0 else ret>=threshold
  terminal.append(hit)
  if i>=next_start:disjoint.append(hit);next_start=j
 returns=[math.log(b/a) for a,b in zip(prices,prices[1:])]
 models=[];years=calendar_days/365.25
 for window in (63,252):
  sample=returns[-window:]
  if len(sample)<30:continue
  sigma=statistics.stdev(sample)*math.sqrt(annualization_days)
  if sigma<=0:continue
  for drift in (-.1,0,.1):
   z=(math.log(1+threshold)-(drift-.5*sigma*sigma)*years)/(sigma*math.sqrt(years))
   cdf=.5*(1+math.erf(z/math.sqrt(2)));prob=cdf if threshold<0 else 1-cdf
   models.append({'volatility_observations':len(sample),'annualized_volatility_pct':sigma*100,'assumed_annual_drift_pct':drift*100,'probability_pct':prob*100})
 stress=[]
 if models:
  reference_vol=max(x['annualized_volatility_pct'] for x in models)/100
  for multiple in (1.5,2):
   for drift in (-.2,0):
    sigma=reference_vol*multiple
    z=(math.log(1+threshold)-(drift-.5*sigma*sigma)*years)/(sigma*math.sqrt(years))
    cdf=.5*(1+math.erf(z/math.sqrt(2)))
    stress.append({'reference_realized_vol_pct':100*reference_vol,'volatility_multiplier_assumption':multiple,'annualized_volatility_pct':100*sigma,'assumed_annual_drift_pct':100*drift,'calendar_days':calendar_days,'probability_pct':100*(cdf if threshold<0 else 1-cdf)})
 return {'event':'期末回報'+('低於或等於' if threshold<0 else '高於或等於')+str(threshold_pct)+'%；不是期內曾觸及','calendar_days':calendar_days,'history_start':dates[0].isoformat(),'history_end':dates[-1].isoformat(),'overlapping_historical_windows':len(terminal),'historical_hits':sum(terminal),'overlapping_frequency_pct':100*sum(terminal)/len(terminal) if terminal else None,'non_overlapping_windows':len(disjoint),'non_overlapping_hits':sum(disjoint),'non_overlapping_frequency_pct':100*sum(disjoint)/len(disjoint) if disjoint else None,'constant_volatility_scenarios':models,'stress_scenarios':stress,'stress_method':'以63/252期較高實現波動作參考，乘1.5或2；漂移0或-20%均為明示壓力假設，不是估計的參數或市場報價。對數回報常態均值=(mu-sigma²/2)T，標準差=sigma√T；T=日數/365.25。壓力模型概率不是該壓力情境本身發生的概率。','walk_forward_baseline':rolling_terminal_backtest(pairs,threshold_pct,calendar_days,annualization_days),'limits':['歷史頻率不是未來概率；重疊窗口高度相關，不可當獨立試驗。','非重疊窗口亦受市場制度變化影響；樣本可能太小，零次不等於不可能。','對數常態情境使用假设漂移-10%／0%／+10%、固定波動；無法充分涵蓋肥尾、跳躍及波動聚集。','以首個不早於目標日且相差不超過7日的觀察作期末；假日有日期偏差。','模型與歷史頻率是對照基準，必須再結合衍生品及其他金融層，不能平均後當校準概率。']}

def quality_summary(provider,data,checked_date=None):
 """Transport success is distinct from observation freshness or verified financial evidence."""
 today=checked_date or research_today();observed=None;role='structured_financial_data';notes=[]
 if provider=='web':return {'role':'unverified_quote_lead','observation_date':None,'age_days':None,'notes':['搜尋摘要未核對原頁；不納入概率權重。']}
 if provider in ('yahoo','fred','hkma','southbound'):observed=data.get('statistics',{}).get('last_date')
 elif provider=='censtatd_hk_unemployment':
  role='official_target_baseline';observed=str(data['baseline']['period'])+'-12-31';notes.append('年度UR為水平基準；近期滾動三個月另列，不能與全年平均混為一談。')
 elif provider=='cftc':observed=data.get('managed_money_net',{}).get('last_date');notes.append('每週持倉，公布有時差。')
 elif provider=='treasury':
  observed=data.get('spread_10y_2y_history',{}).get('last_date')
 elif provider in ('deribit','deribit_options'):
  stamps=[q.get('timestamp_ms') for q in data.get('quotes',[])] if provider=='deribit_options' else [data.get('book',{}).get('timestamp_ms')]
  stamps=[v for v in stamps if isinstance(v,(int,float))]
  if stamps:observed=datetime.datetime.fromtimestamp(min(stamps)/1000,datetime.timezone.utc).date().isoformat()
  if provider=='deribit_options':notes.append('各期權報價有獨立毫秒時間戳；並非同時快照。到期偏差 '+str(data.get('expiry_mismatch_days'))+' 日。')
 elif provider=='edgar':role='filing_index';notes.append('只取得申報索引；不能由此確定實際買賣方向或金額。')
 elif provider=='coinlore':
  notes.append('供應商沒有每筆報價觀察時間，抓取時間不代表報價時間。')
  for check in data.get('consistency_checks',[]):
   if check['flagged']:notes.append(check['symbol']+'美元價與BTC交叉換算偏差'+str(round(check['difference_pct'],2))+'%；不作同步報價或套利證據。')
 elif provider in ('polymarket','kalshi'):notes.append('還需逐一核對相關性、結算條件、到期日、流動性及價差。')
 age=None
 if observed:
  try:age=(today-datetime.date.fromisoformat(observed)).days
  except ValueError:notes.append('觀察日期格式不能自動解析。')
  if age is not None and age>14 and role!='official_target_baseline':notes.append('觀察超過14天，當前風險分析需降低權重。')
 return {'role':role,'observation_date':observed,'age_days':age,'notes':notes}

def rolling_terminal_backtest(pairs,threshold_pct,calendar_days,annualization_days):
 """Walk-forward check of a fixed zero-drift lognormal BASELINE, not the AI forecast."""
 import bisect
 dates=[d for d,v in pairs];prices=[v for d,v in pairs]
 logs=[math.log(b/a) for a,b in zip(prices,prices[1:])]
 horizon=calendar_days/365.25;threshold=threshold_pct/100;points=[];i=252
 while i<len(dates):
  j=bisect.bisect_left(dates,dates[i]+datetime.timedelta(days=calendar_days))
  if j>=len(dates):break
  if (dates[j]-dates[i]).days>calendar_days+7:
   i+=1;continue
  sigma=statistics.stdev(logs[i-252:i])*math.sqrt(annualization_days)
  if sigma>1e-10:
   z=(math.log(1+threshold)+.5*sigma*sigma*horizon)/(sigma*math.sqrt(horizon))
   cdf=.5*(1+math.erf(z/math.sqrt(2)));prob=cdf if threshold<0 else 1-cdf
   ret=prices[j]/prices[i]-1;outcome=int(ret<=threshold if threshold<0 else ret>=threshold)
   past=[]
   for start in range(i):
    end=bisect.bisect_left(dates,dates[start]+datetime.timedelta(days=calendar_days))
    if end>i or (dates[end]-dates[start]).days>calendar_days+7:continue
    old_return=prices[end]/prices[start]-1
    past.append(int(old_return<=threshold if threshold<0 else old_return>=threshold))
   benchmark=(sum(past)+1)/(len(past)+2)
   points.append({'forecast_date':dates[i].isoformat(),'outcome_date':dates[j].isoformat(),'predicted_pct':100*prob,'realized_return_pct':100*ret,'outcome':outcome,'squared_error':(prob-outcome)**2,'historical_frequency_benchmark_pct':100*benchmark,'benchmark_past_windows':len(past),'benchmark_squared_error':(benchmark-outcome)**2})
  i=j
 return {'model':'固定零漂移、過去252筆log回報波動的對數常態模型；每次只用預測日期之前及當日資料。','forecast_count':len(points),'event_count':sum(p['outcome'] for p in points),'brier_score':statistics.mean(p['squared_error'] for p in points) if points else None,'historical_benchmark_brier':statistics.mean(p['benchmark_squared_error'] for p in points) if points else None,'benchmark_method':'同一預測時點已完整結束的歷史窗口頻率，採(事件次數+1)/(窗口數+2)平滑；只作簡單預測基準，不據重疊窗口建立置信區間。','mean_forecast_pct':statistics.mean(p['predicted_pct'] for p in points) if points else None,'realized_frequency_pct':100*sum(p['outcome'] for p in points)/len(points) if points else None,'points':points,'limitations':'這只檢查固定統計基準，不是完整AI報告的回測。窗口依次不重疊，但仍有制度依賴；樣本較少，不能据此聲稱概率校準或準確率。Brier越低越好，尺度0至1；須與同一測試點的歷史頻率基準比較。'}
