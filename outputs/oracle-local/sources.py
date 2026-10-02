"""Bounded, read-only live data adapters. Each runs in its own subprocess."""
import dataclasses, datetime, json, os, sys, math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
STATE=Path(os.environ.get('ORACLE_STATE_DIR',str(BASE/'work/oracle-app-state')))
sys.path.insert(0,str(BASE/'work/digital-oracle'))
import certifi
os.environ['SSL_CERT_FILE']=certifi.where()
from digital_oracle import *
from digital_oracle.http import UrllibJsonClient
CATALOG={
 'rvd_hk_housing':('香港差餉物業估價署','官方私人住宅售價指數（月度）','https://www.rvd.gov.hk/datagovhk/1.4M.csv'),
 'censtatd_hk_unemployment':('香港政府統計處','官方失業率歷史水平基準','https://www.censtatd.gov.hk/en/web_table.html?id=210-06101'),
 'hkma':('香港金管局','HIBOR・銀行體系總結餘（官方）','https://apidocs.hkma.gov.hk'),
 'southbound':('港股通南向資金','每日南向成交淨買入（東方財富數據中心）','https://data.eastmoney.com/hsgt/'),
 'fred':('FRED 金融序列','信用息差・實質利率・通脹補償','https://fred.stlouisfed.org'),
 'polymarket':('Polymarket','事件預測市場','https://polymarket.com'),
 'kalshi':('Kalshi','事件合約・利率與經濟','https://kalshi.com'),
 'treasury':('US Treasury','美國國債曲線','https://home.treasury.gov/resource-center-data-chart-center/interest-rates'),
 'bis':('BIS','央行利率','https://data.bis.org'),
 'cftc':('CFTC COT','商品期貨持倉','https://publicreporting.cftc.gov'),
 'yahoo':('Yahoo Finance','股票・黃金・指數歷史','https://finance.yahoo.com'),
 'options':('Yahoo Options','美股期權','https://finance.yahoo.com'),
 'deribit':('Deribit','加密期貨','https://www.deribit.com'),
 'deribit_options':('Deribit Options','加密期權保護成本與波幅偏斜','https://www.deribit.com'),
 'coinlore':('CoinLore','免費加密行情・毋須帳戶','https://www.coinlore.com/cryptocurrency-data-api'),
 'coingecko':('CoinGecko','加密現價及市值','https://www.coingecko.com'),
 'edgar':('SEC EDGAR','公司申報','https://www.sec.gov/edgar/search'),
 'worldbank':('World Bank','宏觀歷史指標','https://data.worldbank.org'),
 'eastmoney':('Eastmoney','A股價格及資金流','https://www.eastmoney.com'),
 'feargreed':('CNN Fear & Greed','美股市場情緒','https://edition.cnn.com/markets/fear-and-greed'),
 'web':('Web Search','補充公開網頁','https://duckduckgo.com'),
}
def normalize(x):
 if dataclasses.is_dataclass(x):x={f.name:getattr(x,f.name) for f in dataclasses.fields(x) if f.name!='raw'}
 if isinstance(x,dict):return {str(k):[normalize(m) for m in v] if k in ('markets','annual_history') and isinstance(v,list) else normalize(v) for k,v in x.items() if k!='raw'}
 if isinstance(x,(list,tuple)):
  if len(x)>20:return {'total':len(x),'sampled':True,'first':[normalize(v) for v in x[:5]],'last':[normalize(v) for v in x[-10:]]}
  return [normalize(v) for v in x]
 if isinstance(x,str):return x[:1800]
 return x

def validate_data(name,data):
 if data is None or data==[] or data=={}:raise ValueError('來源沒有符合條件的資料')
 if name=='eastmoney' and data.get('quote',{}).get('last',0)<=0:raise ValueError('即時價格為零，未視為有效報價；可能仍未開市')
 return data

def load_config():
 if (STATE/'config.json').exists():
  conf=json.loads((STATE/'config.json').read_text())
  for k in ('EDGAR_USER_EMAIL','COINGECKO_DEMO_API_KEY'):
   if conf.get(k):os.environ[k]=conf[k]

class ExplicitYahooFetcher:
 def __init__(self,adjust):self.adjust=adjust
 def fetch_history(self,symbol,*,period,interval):
  import yfinance
  frame=yfinance.Ticker(symbol).history(period=period,interval=interval,auto_adjust=self.adjust,actions=False,timeout=12)
  return [{'Date':date,**{k:None if isinstance(v,float) and not math.isfinite(v) else v for k,v in row.items()}} for date,row in frame.iterrows()]

def fetch(name,plan):
 load_config();c=UrllibJsonClient(timeout_seconds=12,retry_attempts=1)
 ticker=plan.get('ticker') or 'SPY';search=plan.get('search') or 'Fed decision'
 if name=='censtatd_hk_unemployment':
  from target_data import fetch_hk_unemployment
  data=fetch_hk_unemployment()
 elif name=='rvd_hk_housing':
  from target_data import fetch_hk_housing
  data=fetch_hk_housing()
 elif name=='hkma':
  from hk_data import fetch_hkma
  data=fetch_hkma(plan.get('series') or 'HIBOR_1M')
 elif name=='southbound':
  from hk_data import fetch_southbound
  data=fetch_southbound()
 elif name=='polymarket':
  payload=c.get_json('https://gamma-api.polymarket.com/public-search',params={'q':search,'limit_per_type':5,'events_status':'active'})
  events=[]
  for e in payload.get('events',[])[:5]:
   if e.get('closed'):continue
   active=[m for m in e.get('markets',[]) if not m.get('closed')]
   markets=[{**{k:m.get(k) for k in ('question','outcomes','outcomePrices','bestBid','bestAsk','volume','volume24hr','liquidity','endDate','closed','description','id','updatedAt','lastTradePrice')},'rules_truncated':len(m.get('description') or '')>1800} for m in active[:40]]
   events.append({'title':e.get('title'),'endDate':e.get('endDate'),'url':'https://polymarket.com/event/'+e['slug'],'markets':markets,'active_markets_total':len(active),'included_markets':len(markets),'markets_truncated':len(active)>len(markets)})
  data=events
 elif name=='kalshi':
  ms=KalshiProvider(c).list_markets(KalshiMarketQuery(series_ticker=plan.get('series') or 'KXFEDDECISION',limit=100))
  total=len(ms);ms=sorted(ms,key=lambda m:m.close_time or '9999')[:20]
  data={'markets':[{**{k:getattr(m,k) for k in ('ticker','event_ticker','title','status','yes_bid','yes_ask','no_bid','no_ask','volume','volume_24h','close_time','expiration_time','rules_primary','rules_secondary','yes_sub_title','no_sub_title','liquidity','open_interest')},'rules_truncated':len(m.rules_primary or '')>1800 or len(m.rules_secondary or '')>1800} for m in ms],'returned_market_count':total,'included_market_count':len(ms),'markets_truncated':total>len(ms),'note':'按close_time最近優先；最終expiration不一定等於決定日期，應核對條款。報價以美元/一美元Yes合約表示；成交及持倉為合約數。'}
 elif name=='fred':
  from quant import fetch_fred
  data=fetch_fred(plan.get('series') or 'BAMLH0A0HYM2')
 elif name=='treasury':
  from quant import treasury_history
  curves=USTreasuryProvider(c).list_yield_curve(YieldCurveQuery())
  latest,spread_stats=treasury_history(curves)
  data={'latest':latest,'spread_10y_2y_history':spread_stats,'note':'息差單位為百分點，乘100為基點。'}
 elif name=='bis':data=BisProvider(c).get_policy_rates(BisRateQuery(start_year=datetime.date.today().year-1))
 elif name=='cftc':
  from quant import series_summary
  from digital_oracle.providers.cftc import CFTC_SODA_URL
  provider=CftcCotProvider(http_client=c)
  candidates=provider.list_reports(CftcCotQuery(commodity_name=plan.get('commodity') or 'GOLD',limit=80,primary_only=False))
  if not candidates:raise ValueError('没有持倉記錄')
  latest_date=max(r.report_date for r in candidates)
  selected=max((r for r in candidates if r.report_date==latest_date),key=lambda r:r.open_interest).market_name
  payload=c.get_json(CFTC_SODA_URL,params={'$where':"market_and_exchange_names = '"+selected.replace("'","''")+"'",'$order':'report_date_as_yyyy_mm_dd DESC','$limit':52})
  reports=provider._parse_reports(payload)
  data={'market_name':selected,'reports':reports,'managed_money_net':series_summary({r.report_date:r.mm_net for r in reports}),'managed_money_net_pct_oi':series_summary({r.report_date:100*r.mm_net/r.open_interest for r in reports if r.open_interest>0}),'note':'固定同一市場名稱，避免混合WTI/Brent；每週觀察，分位數按實際樣本，不是多年極端值。'}
 elif name in ('yahoo','options'):
  import yfinance
  yfinance.set_tz_cache_location(str(STATE/('cache-'+name)))
  if name=='yahoo':
   from analysis import price_statistics
   adjusted=not bool(plan.get('forecast_spec'))
   history=YahooPriceProvider(fetcher=ExplicitYahooFetcher(adjusted)).get_history(PriceHistoryQuery(symbol=ticker,limit=(1826 if ticker in ('BTC-USD','ETH-USD') else 1260) if plan.get('forecast_spec') else 300))
   data={'symbol':ticker,'price_basis':'auto_adjust=True：供應商復權OHLC，股票/ETF歷史包含股息調整' if adjusted else 'auto_adjust=False：未自動套用股息復權的Close；拆股處理由供應商負責。用於期末價格門檻對照。','statistics':price_statistics(history),'history':history,'closes':{b.date:b.close for b in history.bars}}
   if plan.get('forecast_spec'):
    from quant import terminal_return_baselines
    spec=plan['forecast_spec'];data['terminal_return_baselines']=terminal_return_baselines(data['closes'],spec['threshold_return_pct'],spec['calendar_days'],data['statistics']['annualization_days'])
  else:
   p=YFinanceProvider();ex=p.get_expirations(ticker)
   from quant import research_today
   requested=plan.get('expiration') or (research_today()+datetime.timedelta(days=90)).isoformat()
   from derivatives import choose_expiration,equity_tail_quotes
   expiry=choose_expiration(ex.expirations,requested)
   chain=p.get_chain(OptionsChainQuery(ticker=ticker,expiration=expiry,compute_greeks=False))
   data={'ticker':ticker,'underlying_price':chain.underlying_price,'atm_call':chain.atm_call,'atm_put':chain.atm_put,'put_call_volume_ratio':chain.put_call_volume_ratio,'put_call_oi_ratio':chain.put_call_oi_ratio,'total_volume':chain.total_volume,'total_open_interest':chain.total_open_interest,'requested_expiration':requested,'selected_expiration':expiry,'expiry_mismatch_days':(datetime.date.fromisoformat(expiry)-datetime.date.fromisoformat(requested)).days,'chain':chain,'atm_iv':chain.atm_iv() if callable(chain.atm_iv) else chain.atm_iv,'implied_move':chain.implied_move() if callable(chain.implied_move) else chain.implied_move,'note':'IV及跨式成本並非事件概率；按目標日期選最接近的可用到期。整體成交及持倉比已用完整鏈計算；原始鏈截樣不可重算。未使用固定利率生成Greeks。'}
   data['tail_quotes']=equity_tail_quotes(chain,plan.get('forecast_spec',{}).get('threshold_return_pct',-20))
 elif name=='deribit_options':
  from derivatives import fetch_crypto_options
  data=fetch_crypto_options(c,plan)
 elif name=='deribit':
  p=DeribitProvider(c);currency='ETH' if ticker.startswith('ETH') else 'BTC'
  data={'book':p.get_order_book(currency+'-PERPETUAL'),'futures':p.get_futures_term_structure(DeribitFuturesCurveQuery(currency=currency))}
 elif name=='coinlore':
  markets=c.get_json('https://api.coinlore.net/api/tickers/',params={'start':0,'limit':10})
  prices=c.get_json('https://api.coinlore.net/api/ticker/',params={'id':'90,80'})
  global_data=c.get_json('https://api.coinlore.net/api/global/')
  if not markets.get('data') or not prices or not global_data:raise ValueError('CoinLore 回應欠資料')
  from quant import coin_quote_consistency
  data={'prices':prices,'markets':markets,'global':global_data,'consistency_checks':coin_quote_consistency(prices),'note':'供應商未提供每個報價觀察時間；抓取時間不是報價時間。不同供應商價格可能有差異。'}
 elif name=='coingecko':
  p=CoinGeckoProvider();p.http_client.timeout_seconds=12;p.http_client.retry_attempts=1
  data={'prices':p.get_prices(),'markets':p.list_markets(CoinGeckoMarketQuery(per_page=5)),'global':p.get_global()}
 elif name=='edgar':
  if not os.environ.get('EDGAR_USER_EMAIL'):raise ValueError('SEC 未配置聯絡電郵')
  p=EdgarProvider();p.http_client.timeout_seconds=12;p.http_client.retry_attempts=1
  if ticker not in ('SPY','GC=F','BTC','ETH','^HSI'):data=p.get_insider_transactions(EdgarInsiderQuery(ticker=ticker,limit=5))
  else:data=p.search_filings(EdgarSearchQuery(query=search,forms='10-K',limit=5))
 elif name=='worldbank':data=WorldBankProvider(c).get_indicator(WorldBankQuery(indicator='NY.GDP.MKTP.CD',date_range='2022:2025'))
 elif name=='eastmoney':
  # Audit fix: never substitute an unrelated A-share (previously 002156) for an invalid code.
  if not (ticker.isdigit() and len(ticker)==6):raise ValueError('Eastmoney需要6位A股代號，收到 '+ticker)
  p=EastmoneyProvider()
  p.http_client.timeout_seconds=12;p.http_client.retry_attempts=1
  data={'quote':p.get_quote(EastmoneyQuoteQuery(symbol=ticker)),'history':p.get_history(EastmoneyKlineQuery(symbol=ticker,limit=10)),'flow':p.get_fund_flow(EastmoneyFundFlowQuery(symbol=ticker,limit=5))}
 elif name=='feargreed':
  p=FearGreedProvider();p.http_client.timeout_seconds=12;p.http_client.retry_attempts=1;data=p.get_index()
 elif name=='web':data=WebSearchProvider().search(search)
 else:raise ValueError('未知來源')
 data=normalize(data);validate_data(name,data)
 return data

if __name__=='__main__':
 name=sys.argv[1];plan=json.loads(sys.stdin.read() or '{}');result={'id':name,'name':CATALOG[name][0],'url':CATALOG[name][2],'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  from quant import quality_summary
  data=fetch(name,plan);result.update(status='ok',data=data,quality=quality_summary(name,data))
 except Exception as e:
  code=None;cur=e
  while cur:
   code=getattr(cur,'code',None) or code;cur=cur.__cause__
  msg=f'HTTP {code}：來源拒絕或暫時無法提供資料' if code else str(e)[:220]
  result.update(status='error',error=msg)
 print(json.dumps(result,ensure_ascii=False,default=str))
