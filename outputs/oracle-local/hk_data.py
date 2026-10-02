"""Hong Kong money-market and cross-border flow series from official / exchange-data endpoints.

hkma       : HKMA public API (no key) — HIBOR fixings by tenor and the Aggregate Balance.
southbound : Eastmoney data centre — Stock Connect southbound daily net buying (sum of SH + SZ links).
Both return the same shape as FRED rows (observations + statistics) so local statistics treat them alike.
"""
import datetime, json, math, ssl, urllib.parse, urllib.request
import certifi
from quant import series_summary

HKMA_BASE = 'https://api.hkma.gov.hk/public/market-data-and-statistics/'
HIBOR_PATH = 'monthly-statistical-bulletin/er-ir/hk-interbank-ir-daily'
LIQUIDITY_PATH = 'daily-monetary-statistics/daily-figures-interbank-liquidity'
# series id -> (label, units, endpoint path, date field, value field, extra params)
HKMA_SERIES = {
 'HIBOR_ON': ('隔夜HIBOR', '% 年率', LIQUIDITY_PATH, 'end_of_date', 'hibor_overnight', {}),
 'HIBOR_1M': ('1個月HIBOR定價', '% 年率', LIQUIDITY_PATH, 'end_of_date', 'hibor_fixing_1m', {}),
 'HIBOR_3M': ('3個月HIBOR定價', '% 年率', HIBOR_PATH, 'end_of_day', 'ir_3m', {'segment': 'hibor.fixing'}),
 'HIBOR_6M': ('6個月HIBOR定價', '% 年率', HIBOR_PATH, 'end_of_day', 'ir_6m', {'segment': 'hibor.fixing'}),
 'HIBOR_12M': ('12個月HIBOR定價', '% 年率', HIBOR_PATH, 'end_of_day', 'ir_12m', {'segment': 'hibor.fixing'}),
 'AGG_BALANCE': ('銀行體系總結餘（收市）', '港元百萬', LIQUIDITY_PATH, 'end_of_date', 'closing_balance', {}),
}
SOUTHBOUND_URL = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
UA = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}


def _get_json(url, params, timeout=15, headers=None):
 full = url + '?' + urllib.parse.urlencode(params)
 req = urllib.request.Request(full, headers={**UA, **(headers or {})})
 with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context(cafile=certifi.where())) as r:
  return json.loads(r.read(5_000_000).decode('utf-8-sig'))


def _today():
 return datetime.datetime.now(datetime.timezone.utc).date()


def parse_hkma(series, payload, as_of=None):
 if series not in HKMA_SERIES:raise ValueError('未支援金管局序列')
 label, units, path, date_key, value_key, _ = HKMA_SERIES[series]
 header = payload.get('header') or {}
 if header and header.get('success') is False:raise ValueError('金管局接口未成功回應：' + str(header.get('err_msg', ''))[:80])
 records = (payload.get('result') or {}).get('records') or []
 cutoff = (as_of or _today()).isoformat()
 values = {}
 for r in records:
  d = str(r.get(date_key) or '')[:10]
  v = r.get(value_key)
  try:datetime.date.fromisoformat(d)
  except ValueError:continue
  if d > cutoff or type(v) not in (int, float) or not math.isfinite(v):continue  # never a future or blank figure
  values[d] = float(v)
 if len(values) < 2:raise ValueError('金管局序列有效觀察不足')
 data = {'series': series, 'name': label, 'units': units, 'statistics': series_summary(values), 'observations': dict(sorted(values.items())),
         'url': HKMA_BASE + path, 'note': '金管局官方公開數據；HIBOR為銀行同業拆息定價，不等於按揭實際利率。總結餘單位為港元百萬，反映銀行體系港元流動性，弱方兌換保證觸發時會收縮。'}
 if series == 'AGG_BALANCE':
  latest = max((r for r in records if str(r.get(date_key) or '')[:10] <= cutoff), key=lambda r: str(r.get(date_key)), default={})
  data['peg_band'] = {k: latest.get(k) for k in ('cu_weakside', 'cu_strongside')}
 return data


def state_dir():
 # Same location as sources.STATE, without re-importing sources inside its own subprocess.
 from pathlib import Path
 import os
 return Path(os.environ.get('ORACLE_STATE_DIR', str(Path(__file__).resolve().parents[2] / 'work/oracle-app-state')))


CACHE_SECONDS = 1800
PAGE = {LIQUIDITY_PATH: 130, HIBOR_PATH: 400}  # the liquidity records are ~50 fields each and the endpoint is slow with large pages


def _cached_endpoint(path, extra, timeout):
 """One request per endpoint for all series in an analysis: signals run in parallel processes,
 so the first one fetches under a file lock and the rest reuse the saved payload."""
 import fcntl, hashlib, os, time
 folder = state_dir() / 'cache-hkma';folder.mkdir(parents=True, exist_ok=True)
 key = hashlib.sha256((path + json.dumps(extra, sort_keys=True)).encode()).hexdigest()[:16]
 cache, lock = folder / (key + '.json'), folder / (key + '.lock')
 with open(lock, 'w') as handle:
  fcntl.flock(handle, fcntl.LOCK_EX)
  try:
   if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_SECONDS:return json.loads(cache.read_text())
   date_key = 'end_of_date' if path == LIQUIDITY_PATH else 'end_of_day'
   payload = _get_json(HKMA_BASE + path, {'pagesize': PAGE[path], 'sortby': date_key, 'sortorder': 'desc', **extra}, timeout=timeout)
   if (payload.get('header') or {}).get('success') is False:raise ValueError('金管局接口未成功回應：' + str(payload['header'].get('err_msg', ''))[:80])
   tmp = cache.with_suffix('.tmp');tmp.write_text(json.dumps(payload));os.replace(tmp, cache)
   return payload
  finally:fcntl.flock(handle, fcntl.LOCK_UN)


# Daily liquidity figures are current but the endpoint is unreliable; the monthly bulletin has the
# same overnight / 1-month fixings with about a month's lag. Used only when the daily endpoint fails.
FALLBACK = {'HIBOR_ON': 'ir_overnight', 'HIBOR_1M': 'ir_1m'}


def fetch_hkma(series):
 if series not in HKMA_SERIES:raise ValueError('未支援金管局序列：' + str(series))
 label, units, path, date_key, value_key, extra = HKMA_SERIES[series]
 try:
  return parse_hkma(series, _cached_endpoint(path, extra, timeout=8))
 except Exception as exc:  # timeouts, HTTP errors, malformed payloads
  if series not in FALLBACK:raise ValueError('金管局接口未能回應（' + str(exc)[:60] + '）') from exc
  try:payload = _cached_endpoint(HIBOR_PATH, {'segment': 'hibor.fixing'}, timeout=7)
  except Exception as second:raise ValueError('金管局每日及月度接口均未能回應（' + str(second)[:60] + '）') from second
  records = [{'end_of_date': r.get('end_of_day'), value_key: r.get(FALLBACK[series])} for r in (payload.get('result') or {}).get('records') or []]
  data = parse_hkma(series, {'result': {'records': records}})
  data['fallback'] = '每日流動性接口未能回應（' + str(exc)[:60] + '），改用金管局月度統計公報的同一定價；最新日期約滯後一個月。'
  data['note'] += data['fallback']
  return data


def parse_southbound(payload, as_of=None):
 if payload.get('success') is False or not isinstance(payload.get('result'), dict):raise ValueError('東方財富南向資金接口未成功回應')
 cutoff = (as_of or _today()).isoformat()
 net, turnover = {}, {}
 for r in payload['result'].get('data') or []:
  if str(r.get('MUTUAL_TYPE')) != '006':continue  # 006 = southbound total (Shanghai + Shenzhen links)
  d = str(r.get('TRADE_DATE') or '')[:10]
  try:datetime.date.fromisoformat(d)
  except ValueError:continue
  v = r.get('NET_DEAL_AMT')
  if d > cutoff or type(v) not in (int, float) or not math.isfinite(v):continue
  net[d] = float(v)
  if type(r.get('DEAL_AMT')) in (int, float):turnover[d] = float(r['DEAL_AMT'])
 if len(net) < 5:raise ValueError('南向資金有效觀察不足')
 dates = sorted(net)
 def total(n):return sum(net[d] for d in dates[-n:]) if len(dates) >= n else None
 flow_stats = {k: v for k, v in series_summary(net).items() if not k.startswith('change_')}
 flow_stats['note'] = '每日淨買入是流量；判斷資金方向應看cumulative_net_buy累計值，不要把兩日流量相減當作趨勢。分位數只相對本次樣本。'
 return {'series': 'SOUTHBOUND_NET', 'name': '港股通南向成交淨買入（滬深合計）', 'units': '百萬元（東方財富口徑）',
         'statistics': flow_stats, 'observations': {d: net[d] for d in dates},
         'cumulative_net_buy': {'last_5_days': total(5), 'last_21_days': total(21), 'last_63_days': total(63), 'units': '百萬元'},
         'latest_turnover': turnover.get(dates[-1]), 'positive_days_last_21': sum(net[d] > 0 for d in dates[-21:]),
         'url': 'https://data.eastmoney.com/hsgt/', 'note': '每日成交淨買入＝買入減賣出成交額，是交易流量而非持倉變化；單日數字波動大，宜看累計。數據由東方財富轉載，非港交所官方接口。'}


def fetch_southbound():
 params = {'reportName': 'RPT_MUTUAL_DEAL_HISTORY', 'columns': 'MUTUAL_TYPE,TRADE_DATE,NET_DEAL_AMT,DEAL_AMT,BUY_AMT,SELL_AMT', 'source': 'WEB',
           'sortColumns': 'TRADE_DATE', 'sortTypes': -1, 'pageNumber': 1, 'pageSize': 300, 'filter': '(MUTUAL_TYPE="006")'}
 return parse_southbound(_get_json(SOUTHBOUND_URL, params, headers={'Referer': 'https://data.eastmoney.com/'}))
