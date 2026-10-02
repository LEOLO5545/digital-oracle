import copy,unittest
from compact import report_evidence
class CompactEvidenceTests(unittest.TestCase):
 def test_shared_rules_and_markets_keep_all_quotes_without_mutating_evidence(self):
  market={'id':'m','description':'complete rules','outcomes':['Yes','No'],'bestBid':.1,'bestAsk':.12}
  rows=[{'id':sid,'provider':'polymarket','data':[{'title':'event','markets':[copy.deepcopy(market)]}]} for sid in ('a','b')]
  original=copy.deepcopy(rows);result=report_evidence(rows)
  self.assertEqual(rows,original);self.assertEqual(len(result['markets_by_ref']),1);self.assertEqual(len(result['rules_by_ref']),1)
  ref=result['sources'][0]['data'][0]['market_refs'][0];m=result['markets_by_ref'][ref]
  self.assertEqual(m['bestAsk'],.12);self.assertEqual(result['rules_by_ref'][m['rules_ref']],'complete rules')
 def test_distinct_quotes_are_not_deduplicated_by_market_id(self):
  rows=[{'provider':'polymarket','data':[{'markets':[{'id':'m','bestBid':p}]}]} for p in (.1,.2)]
  self.assertEqual(len(report_evidence(rows)['markets_by_ref']),2)
 def test_search_narratives_do_not_enter_judgment(self):
  r=report_evidence([{'provider':'web','data':{'query':'CDS quote','snippets':[{'url':'https://example.com','text':'Unsupported commentary'}]}}])
  self.assertNotIn('Unsupported commentary',str(r));self.assertIn('https://example.com',str(r))

 def test_all_financial_evidence_round_trips(self):
  from compact import unpack_sources
  from quant import evidence_for_model
  rows=[{'id':'a','provider':'polymarket','data':[{'markets':[{'id':'x','description':None,'volume':24576},{'id':'y','description':'Complete rules','bestAsk':.19}]}]},{'id':'b','provider':'yahoo','data':{'statistics':{'last_close':100},'closes':[1,2]}}]
  self.assertEqual(unpack_sources(report_evidence(rows)),evidence_for_model(rows))
 def test_every_correlation_pair_is_retained(self):
  from compact import report_quant
  q={'strongest_pairs':list(range(18)),'cross_layer_pairs':list(range(12))}
  self.assertEqual(report_quant(q),q)

 def test_completed_statistics_exclude_partial_current_bar(self):
  from quant import evidence_for_model
  rows=[{'provider':'yahoo','data':{'statistics':{'volatility_last_date':'2026-09-29'},'closes':{'2026-09-29':100,'2026-09-30':200}}}]
  s=evidence_for_model(rows)[0]['data']['completed_statistics']
  self.assertEqual(s['last_close'],100);self.assertEqual(s['last_date'],'2026-09-29')
 def test_completed_drawdown_uses_same_date_as_close(self):
  from quant import evidence_for_model
  rows=[{'provider':'yahoo','data':{'statistics':{'volatility_last_date':'2026-09-29','current_drawdown_from_sample_peak_pct':-90},'closes':{'2026-09-28':200,'2026-09-29':100,'2026-09-30':20}}}]
  s=evidence_for_model(rows)[0]['data']['completed_statistics']
  self.assertEqual(s['current_drawdown_from_sample_peak_pct'],-50)

 def test_canonical_ids_keep_latest_quote_search_hits_and_full_rules(self):
  from compact import canonical_contracts
  rules='Important complete settlement wording '*80
  rows=[{'id':sid,'provider':'polymarket','checked_at':date,'data':[{'markets':[{'id':'m','bestBid':bid,'description':rules}]}]} for sid,date,bid in [('a','2026-09-29',.1),('b','2026-09-30',.2)]]
  rows[1]['data'][0]['markets'].append({'id':'later','bestBid':.3,'description':rules})
  original=copy.deepcopy(rows);packed=canonical_contracts(rows)
  self.assertEqual(rows,original);self.assertEqual(len(packed['markets']),2)
  market=packed['markets']['polymarket:m'];self.assertEqual(market['hits'],['a','b']);self.assertEqual(market['bestBid'],.2)
  self.assertEqual(packed['rules'][market['rules'][0]],rules)

 def test_shared_context_round_trips_every_value(self):
  from compact import shared_context
  text='complete rules '*100
  value={'evidence':[{'id':str(i),'long_key_for_measurement':i,'rules':text} for i in range(10)],'anchor':{'rules':text},'nullable':[{'a':None},{}]}
  packed=shared_context(value)
  def unpack(v):
   if isinstance(v,dict):
    if set(v)=={'text_ref'}:return packed['texts'][v['text_ref']]
    if set(v)=={'columns','rows'}:return [{k:unpack(x) for k,x in zip(v['columns'],row)} for row in v['rows']]
    return {k:unpack(x) for k,x in v.items()}
   if isinstance(v,list):return [unpack(x) for x in v]
   return v
  self.assertEqual(unpack(packed['data']),value)
