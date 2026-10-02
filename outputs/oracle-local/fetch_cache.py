"""Provider cache keys exclude question-specific labels and retain observation provenance."""
import hashlib,json,datetime
QUERY_FIELDS=('ticker','search','commodity','series','expiration','forecast_spec')
def cache_key(provider,plan):
 # Include only parameters consumed by this provider, enabling cross-question reuse.
 fields={'yahoo':('ticker','forecast_spec'),'polymarket':('search',),'web':('search',),'cftc':('commodity',),'fred':('series',),'kalshi':('series',),'options':('ticker','expiration','forecast_spec'),'deribit_options':('ticker','expiration'),'edgar':('ticker',),'eastmoney':('ticker',),'deribit':('ticker',)}.get(provider,())
 return hashlib.sha256(json.dumps([2,provider,{k:plan.get(k) for k in fields}],sort_keys=True).encode()).hexdigest()
def usable(row,seconds,now):
 try:age=(datetime.datetime.fromisoformat(now)-datetime.datetime.fromisoformat(row['checked_at'])).total_seconds()
 except (KeyError,ValueError,TypeError):return False
 return row.get('status')=='ok' and 0<=age<seconds
