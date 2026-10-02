"""Horizon-matched option quotes, not event probability estimates."""
import datetime,math,dataclasses
from quant import research_today

def choose_expiration(expirations,requested,today=None):
 today=today or research_today().isoformat()
 available=sorted(d for d in set(expirations) if d>today)
 if not available:raise ValueError('沒有未到期合約')
 target=datetime.date.fromisoformat(requested)
 return min(available,key=lambda d:(abs((datetime.date.fromisoformat(d)-target).days),d<requested))

def option_quote(book,instrument,role):
 raw=book.raw;bid=book.best_bid;ask=book.best_ask
 two_sided=bid is not None and ask is not None and 0<bid<=ask
 mid=(bid+ask)/2 if two_sided else None
 return {'role':role,'instrument':instrument.instrument_name,'strike_usd':instrument.strike,'option_type':instrument.option_type,'timestamp_ms':book.timestamp_ms,'state':book.state,'underlying_price_usd':raw.get('underlying_price'),'index_price_usd':book.index_price,'bid_coin':bid,'ask_coin':ask,'mid_coin':mid,'spread_pct_of_mid':100*(ask-bid)/mid if mid else None,'two_sided_quote':two_sided,'mark_iv_pct':raw.get('mark_iv'),'bid_iv_pct':raw.get('bid_iv'),'ask_iv_pct':raw.get('ask_iv'),'open_interest_coin':book.open_interest,'volume_24h_coin':raw.get('stats',{}).get('volume'),'delta_vendor':raw.get('greeks',{}).get('delta')}

def equity_tail_quotes(chain,threshold_pct=-20):
 if not chain.underlying_price or chain.underlying_price<=0:return {'error':'缺少標的價格，不能選門檻附近合約'}
 target=chain.underlying_price*(1+threshold_pct/100)
 contracts=sorted(chain.puts if threshold_pct<0 else chain.calls,key=lambda c:c.strike)
 if not contracts:return {'error':'沒有對應方向的期權合約'}
 nearest=min(range(len(contracts)),key=lambda i:abs(contracts[i].strike-target))
 selected=contracts[max(0,nearest-1):nearest+2];quotes=[]
 for contract in selected:
  bid=contract.bid;ask=contract.ask;valid=bid is not None and ask is not None and 0<bid<=ask
  quotes.append({**dataclasses.asdict(contract),'two_sided_quote':valid,'spread_pct_of_mid':200*(ask-bid)/(ask+bid) if valid else None})
 return {'threshold_return_pct':threshold_pct,'target_strike':target,'target_bracketed':min(c.strike for c in selected)<=target<=max(c.strike for c in selected),'quotes':quotes,'note':'完整鏈中選門檻最近履約價及相鄰兩檔；門檻按本次期權標的快照計，不一定等於歷史日線P₀。權利金以每股美元表示，IV為小數年化值。來源未保留逐筆報價時間；無雙邊報價或期限不匹配時降權。美式行使及買賣價差限制數字期權近似，不能直接稱實際事件概率。'}

def fetch_crypto_options(client,plan):
 from digital_oracle import DeribitProvider,DeribitInstrumentsQuery
 provider=DeribitProvider(client);currency='ETH' if plan.get('ticker','BTC').startswith('ETH') else 'BTC'
 instruments=provider.list_instruments(DeribitInstrumentsQuery(currency=currency,kind='option'))
 requested=plan.get('expiration') or (research_today()+datetime.timedelta(days=90)).isoformat()
 def date(i):return datetime.datetime.fromtimestamp(i.expiration_timestamp/1000,datetime.timezone.utc).date().isoformat()
 active=[i for i in instruments if i.is_active and i.expiration_timestamp and i.strike]
 selected=choose_expiration([date(i) for i in active],requested)
 chain=[i for i in active if date(i)==selected]
 spot=client.get_json('https://www.deribit.com/api/v2/public/get_index_price',params={'index_name':currency.lower()+'_usd'})['result']['index_price']
 quotes=[]
 for role,kind,multiple in [('ATM保護','put',1),('下行20%附近保護','put',0.8),('上行20%附近','call',1.2)]:
  candidates=[i for i in chain if i.option_type==kind]
  if not candidates:continue
  instrument=min(candidates,key=lambda i:abs(i.strike-spot*multiple))
  quotes.append(option_quote(provider.get_order_book(instrument.instrument_name),instrument,role))
 if not quotes:raise ValueError('目標到期日沒有可用期權')
 ivs=[q.get('mark_iv_pct') for q in quotes]
 skew=ivs[1]-ivs[2] if len(ivs)==3 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in ivs[1:]) else None
 return {'currency':currency,'requested_expiration':requested,'selected_expiration':selected,'expiry_mismatch_days':(datetime.date.fromisoformat(selected)-datetime.date.fromisoformat(requested)).days,'index_at_selection_usd':spot,'quotes':quotes,'downside_minus_upside_mark_iv_pp':skew,'note':'以現貨指數選最近ATM及正負20%履約價；不是25-delta risk reversal。IV為百分比，偏斜為百分點。期權權利金、成交量及持倉以BTC或ETH計；各次報價非同時快照。無雙邊報價時不可用mark IV當可成交價格。期權價格含風險溢價，delta與IV均不是實際事件機率；到期不匹配需降權。'}
