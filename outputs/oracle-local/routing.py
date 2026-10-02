"""Regional signal menu: economic channels, time fit and incremental role."""
import re

def is_ukraine(question):
 return bool(re.search(r'俄烏|俄乌|烏克蘭|乌克兰|ukrain',question,re.I))

def regional_signals(question, horizon):
 if not is_ukraine(question):return None
 from signal_policy import config
 menu=config()['profiles']['ukraine']['menu']
 out=[]
 for i,(source,key,label,layer,reason) in enumerate(menu):
  out.append(dict(id=f'ru_{i+1:02d}',source=source,label=label,layer=layer,reason=reason,horizon=horizon+'；使用最近日線／周度觀察，非固定到期事件機率',**{('search' if source in ('web','polymarket') else 'commodity' if source=='cftc' else 'series' if source=='fred' else 'ticker'):key or 'SPY'},routing={'relevance':reason,'time_match':'最近市場變動作同期背景；事件合約需另核對截止日期','information_increment':reason,'role':'lead' if source=='web' else 'background' if layer=='宏觀背景' else 'comparison' if layer=='美國防務對照' else 'primary'}))
 return out

def route_plan(question,plan):
 signals=regional_signals(question,plan['horizon'])
 return {**plan,'signals':signals,'routing_profile':'ukraine','signal_budget':28} if signals else plan

def preset_plan(question,as_of):
 """Only the exact supported dated ceasefire question bypasses language planning."""
 if re.fullmatch(r'未來三個月[，, ]?美國減息機會[？?]?',question.strip()):
  import datetime,calendar
  from signal_policy import config,apply_policy
  start=datetime.datetime.fromisoformat(as_of).date();month=start.month+3;year=start.year+(month-1)//12;month=(month-1)%12+1
  end=datetime.date(year,month,min(start.day,calendar.monthrange(year,month)[1]))
  p={'core_variable':'由評估時點至截止日，美國聯儲局至少宣佈一次下調聯邦基金利率目標區間。','horizon':f'{as_of} 至 {end.isoformat()} 23:59 香港時間','priceability':'核對各次決策合約的互斥結果、期限及流動性；隔夜利率及債市作交叉核對。','forecast':None,'signals':[],'preset':True}
  for i,(source,key,label,layer) in enumerate(config()['profiles']['rates']['background']):
   p['signals'].append({'id':f'rates_bg_{i}','source':source,'series' if source=='fred' else 'ticker':key,'label':label,'layer':layer,'reason':'控制利率以外的共同市場因素','horizon':p['horizon']})
  return apply_policy(question,p)
 if not re.fullmatch(r'俄[烏乌]全面停火宣[佈布][：:，,\s]*截至20\d{2}年\d{1,2}月\d{1,2}日[。？?]?',question.strip()):return None
 from liquidity import deadline
 target=deadline(question)
 p={'core_variable':'俄羅斯及烏克蘭雙方於期限前公開宣佈已同意全面停火；局部、人道或單方停火不算。宣佈協議與生效及持續履行分開。','horizon':f'{as_of} 起，至 {target} 之前（香港時間，包含指定當日）','priceability':'事件合約先核對條款、期限與成交額；其他金融渠道提供方向及反證，不能直接換算事件機率。','forecast':None,'signals':[]}
 p=route_plan(question,p);p['preset']=True
 for sid,ticker,label in [('ru_europe','VGK','歐洲股票大市'),('ru_dollar','DX-Y.NYB','美元指數')]:
  p['signals'].append({'id':sid,'source':'yahoo','ticker':ticker,'label':label,'layer':'宏觀背景','reason':'控制區域股市及美元因素，避免將防務或商品走勢全歸因停火','horizon':p['horizon']})
 return p
