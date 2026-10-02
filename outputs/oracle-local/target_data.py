"""Official target history, distinct from financial drivers and online opinions."""
import datetime, json, statistics, urllib.request
HK_URL='https://www.censtatd.gov.hk/api/get.php?id=210-06101&lang=en&full_series=1'

def parse_hk_unemployment(payload, as_of=None):
 if payload.get('header',{}).get('status',{}).get('code')!=0:raise ValueError('官方接口未成功回應')
 today=as_of or datetime.date.today();year=str(today.year);month=today.strftime('%Y%m')
 def series(freq,code):
  out=[]
  for r in payload.get('dataSet',[]):
   value=r.get('figure');period=str(r.get('period',''))
   if r.get('SEX')!='' or r.get('freq')!=freq or r.get('sv')!=code or type(value) not in (int,float):continue
   if (freq=='Y' and period>=year) or (freq!='Y' and period>=month):continue
   out.append({'period':period,'value':value})
  return sorted(out,key=lambda r:r['period'])
 annual=series('Y','UR');rolling=series('M3M','UR');adjusted=series('M3M','SAUR')
 if len(annual)<5:raise ValueError('官方年度失業率历史不足')
 recent=annual[-11:];changes=[b['value']-a['value'] for a,b in zip(recent,recent[1:])]
 return {'url':HK_URL,'units':'%','target':'香港失業率','baseline':{**annual[-1],'frequency':'annual','measure':'UR','seasonally_adjusted':False},'annual_history':annual,'recent_rolling_unadjusted':rolling[-12:],'recent_rolling_adjusted':adjusted[-12:],'historical_annual_change_pp':{'sample_years':[recent[0]['period'],recent[-1]['period']],'median':statistics.median(changes),'mean_absolute':statistics.mean(abs(x) for x in changes),'std':statistics.stdev(changes),'min':min(changes),'max':max(changes)},'note':'年度值為全年整體情況，未經季節性調整；M3M為截至所列月份的滾動三個月，不是年度值。官方歷史是水平基準，金融訊號是預測調整依據。歷史改動幅度不是股價對失業率的回歸係數。'}

def fetch_hk_unemployment():
 request=urllib.request.Request(HK_URL,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
 with urllib.request.urlopen(request,timeout=15) as response:payload=json.load(response)
 return parse_hk_unemployment(payload)

RVD_URL='https://www.rvd.gov.hk/datagovhk/1.4M.csv'
def parse_hk_housing(text,as_of=None):
 import csv,io,math
 today=as_of or datetime.date.today();cutoff=today.strftime('%Y-%m')
 lines=text.lstrip('\ufeff').splitlines();header=next((i for i,s in enumerate(lines) if s.startswith('Month,')),None)
 if header is None:raise ValueError('差估署CSV缺少月份欄位')
 series=[]
 for row in csv.DictReader(io.StringIO('\n'.join(lines[header:]))):
  try:period=datetime.datetime.strptime(row['Month'].strip(),'%m-%Y').strftime('%Y-%m');value=float(row['All Classes'])
  except (KeyError,ValueError):continue
  if period<cutoff and math.isfinite(value) and value>0:series.append({'period':period,'value':value,'provisional':row.get('All Classes - Remarks','').strip()=='P'})
 series.sort(key=lambda x:x['period'])
 if not series:raise ValueError('差估署未有可用的已公布月份')
 lookup={x['period']:x['value'] for x in series};changes=[]
 for x in series:
  prior=f"{int(x['period'][:4])-1}{x['period'][4:]}"
  if prior in lookup:changes.append({'period':x['period'],'value':(x['value']/lookup[prior]-1)*100})
 return {'url':RVD_URL,'units':'指數','target':'香港私人住宅售價指數（全港、所有類別）','baseline':series[-1],'monthly_history':series[-24:],'change_12_months_pct':next((x['value'] for x in reversed(changes) if x['period']==series[-1]['period']),None),'historical_12m_returns_pct':changes[-120:],'note':'官方月度所有類別指數；P為臨時數字。最新公布月份可能滯後，並非今日即時樓價。股價變化不可直接當作樓價變幅。'}

def fetch_hk_housing():
 request=urllib.request.Request(RVD_URL,headers={'User-Agent':'Mozilla/5.0'})
 with urllib.request.urlopen(request,timeout=15) as response:text=response.read().decode('utf-8-sig')
 return parse_hk_housing(text)
