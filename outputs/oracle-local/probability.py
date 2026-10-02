"""Recompute a disclosed research estimate; arithmetic is not statistical calibration."""
import copy, math

INSTRUCTION = '''
研究估計規範（取代上文要求無法數據識別便不選中心的規則）：
原作要求根據多層訊號作權重判斷，提供一個具體初步機率。有相關市場證據時，必須選出你認為最合理的一組主要假設，不能只展示等權示例、取區間中點或留空中心。此為主觀研究估計，不是已知真實機率、不是校準預測。缺乏回測或完全同名合約不構成取消中心的理由；但資料全失敗或與問題無關時不可虛構。
請加入 probability.calculation：
{"method":"conditional_bridge","baseline_event":"被定價的基準事件B，與目標T區分","baseline_pct":基準機率百分數,"baseline_origin":"market_quote / maturity_interpolation / statistical_model / analyst_prior","baseline_reason":"實際報價/計算或明示的研究先驗及理由，引用[id]","baseline_sources":["真實成功訊號id"],"target_given_baseline_pct":P(T|B)百分數,"target_without_baseline_pct":P(T|非B)百分數,"conditional_reason":"為何選這兩個主要參數而非鄰近替代值；數據支撐方向，數值幅度是研究判斷時必須明說","channels":[{"name":"獨立經濟渠道","signal_ids":["id"],"effect":"支持/反對/中性","reason":"實際數據如何影響基準、條件參數或保持不調整；同類相關資產合併一個渠道"}],"alternatives":[{"case":"另一合理假設","baseline_pct":數值,"target_given_baseline_pct":數值,"target_without_baseline_pct":數值,"reason":"引用[id]說明變動；最少兩組，至少一組移除最重要的分析渠道"}]}
程式按 P(T)=P(B)P(T|B)+(1−P(B))P(T|非B) 重算中心與替代情境，不接受只寫一個無計算依據的數字。主要假設及每個alternatives必須完整填入baseline_pct、target_given_baseline_pct、target_without_baseline_pct三個有限數字，禁止null、字串或省略。所有參數單位0至100；至少3個不同經濟渠道。所有baseline_sources和signal_ids只用events.sources.id或signals.id；合約market ID不是signal id，應以該合約hits中列出的來源id引用。不把價格相關係數當條件機率。baseline若取市場報價/期限插值，數字須能從附帶證據核對；無市場錨時可以明示研究先驗，禁止假稱歷史頻率。T與B不完全同義時不要假設子集；明示兩個條件參數的定義及期限。B=T且期限完全一致時，條件參數為100及0，其他渠道可用於信心及敏感度，不強迫調整。累計合約涉及過去事件時，須有證據排除過去已觸發，否則另選前瞻基準或明示條件性研究先驗，不能直接當未來報價。
直接定價規則：liquidity_anchors.direct列出期限與問題截止相差不超過14日的高成交Yes/No合約，no_mid_pct為「事件不發生」合約的反向讀數。若其條款與問題相同或只差已知不會發生的部分（例如評估前窗口已確認沒有發生），必須以該報價作基準：baseline_origin=market_quote，baseline_pct取買賣價範圍內或其反向讀數，baseline_sources引用該signal_id。只有條款確實不同時才可用研究先驗，並須填direct_anchor_reason逐條說明差異。程式會核對market_quote是否真的出現在引用來源。\nprobability.kind用「主觀研究估計（未經回測校準）」。estimate輸出按上述主要參數計算、保留一位小數；range是主要及替代假設的包絡，不是信賴區間。headline_summary直接回答問題，最多60字；數字以程式計算為準。scenarios用目標發生/未發生兩個互補情境，加入target_outcome:true/false，概率由程式填入。主結論不得再寫沒有優先中心；限制集中一次說明。選值理由不能只有「未識別」或「保守」，須比較為何主選值較其他值貼合實際金融訊號。不要引用新聞。
'''

def compute(b,q,u):
 for v in (b,q,u):
  if type(v) not in (float,int) or not math.isfinite(v) or not 0<=v<=100:raise ValueError('機率參數必須為0至100有限數值')
 return b*q/100+(100-b)*u/100

def rounded(value):
 return float(f'{value:.2g}') if 0<value<0.1 else round(value,1)

QUOTE_TOLERANCE_PP=1.0

def quoted_values(rows,ids):
 """Every event-contract price in the cited sources, as intervals in percent, with complements."""
 import json
 spans=[]
 def add(lo,hi):
  try:lo,hi=100*float(lo),100*float(hi)
  except (TypeError,ValueError):return
  if not(math.isfinite(lo) and math.isfinite(hi)):return
  lo,hi=min(lo,hi),max(lo,hi);spans.append((lo,hi));spans.append((100-hi,100-lo))
 for r in rows:
  if r.get('id') not in ids or r.get('status')!='ok':continue
  data=r.get('data')
  if isinstance(data,list):
   for event in data:
    for m in (event.get('markets',[]) if isinstance(event,dict) else []):
     if m.get('bestBid') is not None and m.get('bestAsk') is not None:add(m['bestBid'],m['bestAsk'])
     prices=m.get('outcomePrices')
     try:prices=json.loads(prices) if isinstance(prices,str) else prices
     except ValueError:prices=None
     for p in prices or []:add(p,p)
     if m.get('lastTradePrice') is not None:add(m['lastTradePrice'],m['lastTradePrice'])
  elif isinstance(data,dict):
   for m in data.get('markets',[]) if isinstance(data.get('markets'),list) else []:
    if isinstance(m,dict) and m.get('yes_bid') is not None and m.get('yes_ask') is not None:add(m['yes_bid'],m['yes_ask'])
 return spans

def verify_market_baseline(c,rows,anchors):
 """Audit fix: a baseline labelled as a quote must be readable from the cited evidence."""
 origin=c.get('baseline_origin');value=c.get('baseline_pct')
 if origin=='market_quote':
  spans=quoted_values(rows,set(c.get('baseline_sources',[])))
  if not spans:raise ValueError('基準標為市場報價，但引用來源沒有事件合約報價可核對')
  if not any(lo-QUOTE_TOLERANCE_PP<=value<=hi+QUOTE_TOLERANCE_PP for lo,hi in spans):
   raise ValueError(f'基準標為市場報價 {value}%，但與引用來源的買賣價、成交價或其反向讀數均不符（容差±{QUOTE_TOLERANCE_PP}個百分點）；請按實際報價修正，或改標研究先驗並說明')
 if origin=='maturity_interpolation':
  points=[x.get(k) for f in (anchors or {}).get('families',[]) for x in f.get('candidates',[]) for k in ('anchor_pct','constant_hazard_anchor_pct')]
  points=[p for p in points if isinstance(p,(int,float))]
  if points and not any(abs(value-p)<=QUOTE_TOLERANCE_PP for p in points):raise ValueError('基準標為期限插值，但與程式計算的插值錨點不符')
 direct=[d for d in (anchors or {}).get('direct',[]) if not d.get('within_window_single_event')]
 if direct and origin in ('analyst_prior','statistical_model'):
  reason=c.get('direct_anchor_reason')
  if not(isinstance(reason,str) and reason.strip()):
   names='；'.join(f"{d.get('question')}（Yes {d.get('yes_mid_pct'):.1f}% / 反向 {d.get('no_mid_pct'):.1f}%）" for d in direct[:3])
   raise ValueError('有期限吻合的直接定價合約：'+names+'。請以其報價或反向讀數作基準（baseline_origin=market_quote），或在direct_anchor_reason逐條說明條款為何與問題不符')

def materialize(report,rows,required=False,anchors=None):
 if not isinstance(report,dict):return report
 if report.get('probability') is None:
  if required:raise ValueError('機率問題需要probability與具體計算')
  return report
 if not isinstance(report['probability'],dict):raise ValueError('probability必須為物件')
 result=copy.deepcopy(report);p=result['probability'];c=p.get('calculation')
 if not c:
  if required:raise ValueError('新研究報告需要calculation及有理據的主要假設，不能以沒有優先中心代替答案')
  return result  # Historical JSON is never assigned a fabricated center.
 if c.get('method')!='conditional_bridge':raise ValueError('未知機率計算方法')
 good={r['id'] for r in rows if r.get('status')=='ok'}
 def text(value):return isinstance(value,str) and bool(value.strip())
 def ids(values):return isinstance(values,list) and bool(values) and all(isinstance(v,str) and v in good for v in values)
 for key in ('baseline_event','baseline_reason','conditional_reason'):
  if not text(c.get(key)):raise ValueError('機率計算缺少 '+key)
 if c.get('baseline_origin') not in ('market_quote','maturity_interpolation','statistical_model','analyst_prior'):raise ValueError('基準來源類型無效')
 if not ids(c.get('baseline_sources')):raise ValueError('基準需引用可用證據')
 verify_market_baseline(c,rows,anchors)
 channels=c.get('channels',[])
 if len(channels)<3 or len({x.get('name') for x in channels})<3:raise ValueError('研究估計需要至少三個具名分析渠道')
 for x in channels:
  if not text(x.get('name')) or not text(x.get('reason')) or not ids(x.get('signal_ids')) or x.get('effect') not in ('支持','反對','中性'):raise ValueError('分析渠道需有可用證據、方向及選值理由')
 def value(case):
  for key in ('baseline_pct','target_given_baseline_pct','target_without_baseline_pct'):
   v=case.get(key)
   if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=100:raise ValueError('calculation '+str(case.get('case','主要假設'))+' 的 '+key+' 必須填0至100數字，不可null')
  return compute(case['baseline_pct'],case['target_given_baseline_pct'],case['target_without_baseline_pct'])
 exact=value(c);central=rounded(exact);alternatives=c.get('alternatives',[])
 if len(alternatives)<2:raise ValueError('需至少兩個替代假設')
 sensitivities=[]
 for case in alternatives:
  if not text(case.get('case')) or not text(case.get('reason')):raise ValueError('替代假設需有理由')
  sensitivities.append({'case':case['case'],'estimate':rounded(value(case)),'reason':case['reason']})
 p.update(estimate=central,kind='主觀研究估計（未經回測校準）',range=[min([central]+[s['estimate'] for s in sensitivities]),max([central]+[s['estimate'] for s in sensitivities])],sensitivity=sensitivities)
 c.update(computed_pct=exact,formula='P(T) = P(B) × P(T|B) + (1 − P(B)) × P(T|非B)',calibrated=False)
 scenarios=result.get('scenarios',[])
 if len(scenarios)!=2 or {type(x.get('target_outcome')) for x in scenarios}!={bool} or {x['target_outcome'] for x in scenarios}!={True,False}:raise ValueError('新估計需目標發生與未發生兩個互補情境，target_outcome為true/false')
 for scenario in scenarios:scenario['probability']=central if scenario['target_outcome'] else round(100-central,6)
 return result
