"""Auditable checks of report completeness and internal consistency, not predictive accuracy."""
import json,re

def assess(job):
 report=job.get('report')
 if not report:return {'passed':False,'error':job.get('error','沒有完整報告')}
 rows=job.get('sources',[]);known={r['id'] for r in rows};good={r['id'] for r in rows if r['status']=='ok'}
 used={x['signal_id'] for layer in report['layers'] for x in layer['rows']}
 refs=set(re.findall(r'\[([a-z][a-z0-9_]*)\]',json.dumps(report,ensure_ascii=False)))
 p=report.get('probability',report.get('answer',{}));estimated=p.get('estimate');bounds=p.get('range');scenarios=report['scenarios']
 probs=[s.get('probability') for s in scenarios]
 checks={'only_known_citations':not(refs-known),'only_successful_table_rows':not(used-good),'layer_judgments':all(all(l.get(k) for k in ('summary','horizon','weight')) for l in report['layers']),'quantified_estimate_or_explicit_scenarios':bounds is not None and ((isinstance(estimated,(int,float)) and bounds[0]<=estimated<=bounds[1]) or (estimated is None and '示例' in p.get('kind','') and bool(p.get('sensitivity')))),'scenario_weights_consistent':(all(isinstance(x,(int,float)) for x in probs) and abs(sum(probs)-100)<0.01) or (estimated is None and all(x is None for x in probs)),'assumptions_present':bool(p.get('assumptions')),'sensitivity_cases':len(p.get('sensitivity',[]))>=2,'cross_market_computation':job.get('quantitative',{}).get('pair_count',0)>0,'contradictions_discussed':bool(report['analysis']['divergence']),'sub_conclusions_present':bool(report.get('sub_conclusions'))}
 if report.get('answer'):
  a=report['answer'];numeric=a['type']=='numeric_forecast'
  direction=numeric and a.get('direction_only') is True
  if direction:numeric=False  # no level was computable; judged like a text answer
  checks['quantified_estimate_or_explicit_scenarios']=(isinstance(estimated,(int,float)) and bounds[0]<=estimated<=bounds[1]) if numeric else isinstance(a.get('text'),str) and bool(a['text'])
  checks['scenario_weights_consistent']=all(x is None for x in probs)
  checks['sensitivity_cases']=len(a.get('sensitivity',[]))>=2 if numeric else True
 return {'passed':all(checks.values()),'checks':checks,'unknown_citations':sorted(refs-known),'unrepresented_successful_signals':sorted(good-used),'counts':{'requested_signals':len(rows),'successful_responses':len(good),'layers':len(report['layers']),'table_rows':sum(len(l['rows']) for l in report['layers']),'unique_table_signals':len(used),'correlation_pairs':job.get('quantitative',{}).get('pair_count',0)},'scope':'檢查完整性及內部一致性，不代表預測準確率、資料正確率或概率已校準。'}

AUDITOR='''你是金融研究報告的品質審核者。只能根據附帶原始金融證據、確定性計算及報告檢查，不查外部資料，不引用新聞評論。用香港繁體中文，輸出JSON {"findings":[{"severity":"critical/major/minor", "location":"報告具體欄位或signal_id", "problem":"可核對錯誤，引用正確數值/日期", "fix":"具體修正"}], "strengths":["..."], "overall":"..."}。
重點：1數值/單位/觀察日期是否一致；2對合約實際結算條件、期限、流動性是否誤讀；3回報相關性有否當因果或事件概率；4有否重複計算相關訊號；5概率中心、區間、情境、敏感度是否矛盾；6有否重大反證被忽略；7分層深度與數據覆蓋；8主觀估計有否冒充市場直接價格或回測結果。
本產品提供有明確假設的初步主觀概率；不因它尚未回測或沒有同名合約就一概判定錯誤。但必須指出數字只來自無解釋任意指定、假設與金融證據不連貫、或假裝統計推导。嚴重度按實際影響，不能為了挑錯虛構問題。最多8項實質問題，不評論格式偏好。'''

AUDITOR += '\n研究判斷允許明示未校準的參數及一個中心估計。不因無法從市場唯一識別參數就刪除中心或要求所有情境等權。審核選值與證據方向是否連貫、是否解釋幅度和替代值、合約映射及期限是否誠實，以及計算是否正確。若有calculation，computed_pct由程式重算，非回測結果；需修正時改calculation輸入而非只改estimate。未有數據支持的方向或假冒統計推導仍屬錯誤。'

AUDITOR += '\n若有answer欄位，先核對它是否回答原問題：numeric_forecast是水平與單位，不是發生概率；失業率調整為百分點。校對基準日期/統計口徑、預測全年與期末區別、delta幅度理由及反證。binary核對是非判斷與證據一致；comparison/explanation核對直接回答。數值研究預測可有透明主觀調整，但不能假稱統計校準；修正輸入而非刪除答案。'

def audit_and_revise(report, rows, context, generate, validate, normalize, progress=lambda text:None, checkpoint=lambda data:None, initial_audit=None, focused=False):
 """One audit-driven rewrite at most. Original and each review remain inspectable."""
 from analysis import parse_json
 def audit(candidate):
  checked={k:candidate[k] for k in ('answer','probability','scenarios','headline_summary','conclusion','monitor') if k in candidate} if focused else candidate
  instruction=AUDITOR+('只核對提供的答案類型、數值或機率推算、情境、一眼結論及監察指標。其他報告欄位不在本次核對範圍。' if focused else '')
  result=parse_json(generate(instruction+'\n'+json.dumps({**context,'report':checked},ensure_ascii=False,separators=(',',':'))))
  findings=result.get('findings')
  if not isinstance(findings,list) or any(not isinstance(f,dict) or any(not isinstance(f.get(k),str) for k in ('severity','location','problem','fix')) for f in findings):raise ValueError('核對意見格式無效')
  return normalize(result)
 history=[]
 try:
  progress('05 草稿已完成 · 核對內容');first=initial_audit if initial_audit is not None else audit(report)
  if not first['findings']:return report,{'qualitative_audit':first,'revision_attempted':False,'passed':True},history
  history.append({'original_report':report,'audit':first})
  checkpoint({'revisions':history,'audit_findings':first['findings']})
  progress('05 草稿已完成 · 修正受影響欄位（1/1）')
  patch_report={k:report[k] for k in ('answer','probability','scenarios','headline_summary','monitor','conclusion') if k in report} if focused else report
  prompt='根據證據及核對意見，只輸出需要替換的欄位，不要重寫完整報告。不得虛構資料。輸出JSON {"changes":[{"path":"/probability/basis","value":"修正內容"}]}。若修改probability的range、estimate或kind，必須用/probability一次替換整個物件，並同步替換/scenarios。range=null時，estimate、所有sensitivity.estimate及scenarios.probability必須全部null；若保留條件演算值，kind標為假設情境示例且range為情境包絡。path使用JSON Pointer，必須指向原報告已存在欄位；陣列索引由0開始。最多20項。數值、情境和敏感度如受影響須一併修正，保留無誤內容。若未能支持優先中心，probability.estimate可設null並將kind標為假設情境示例；range只代表列出的參數算術包絡，sensitivity展示多組條件值，scenarios無權重依據則probability全null。completed_statistics是從原始完整日線計算的收市基準，請用它修正包含當日暫值的價格與回報；相應下調或更新方向論述。headline_summary仍須白話且不超過60字。\n'+json.dumps({**context,'original_report':patch_report,'audit':first},ensure_ascii=False,separators=(',',':'))
  if report.get('probability',{}).get('calculation'):
   prompt+='\n本報告已有研究估計模型。保留calculation和具體中心；修正參數、理由及受影響文字，不因參數屬研究判斷就把estimate改null。程式會重算estimate/range/sensitivity及互補scenarios；若替換整個probability必須包含calculation，scenarios保留target_outcome。'
  if report.get('answer'):
   prompt+='\n這是按問題類型回答的報告。保留answer.type，禁止改成probability。numeric_forecast須保留calculation，程式會由來源基準及delta重算estimate/range/scenarios；若answer.direction_only為true（目標基準未取得），保持calculation為null及scenarios.estimate為null，只修正方向判斷文字，不可虛構基準；修改輸入及理由而非改輸出數字。binary保留直接decision及text；比較/解釋保留text。不把沒有校準等同不能提供明示假設的研究估计，但不得杜撰數據或假稱回歸。'
  patch=parse_json(generate(prompt))
  checkpoint({'revision_patch':patch})
  revised=validate(normalize(apply_changes(report,patch.get('changes'))),rows)
  history[0]['revised_report']=revised
  checkpoint({'generated_report':revised,'draft_revision':1,'revisions':history})
  progress('05 修正已完成 · 最後複核');second=audit(revised)
  history[0]['recheck']=second
  return revised,{'qualitative_audit':second,'revision_attempted':True,'passed':not second['findings']},history
 except (ValueError,TypeError,KeyError,RuntimeError) as exc:
  # A failed audit is not silently marked passed; preserve the last valid report.
  candidate=history[0].get('revised_report',report) if history else report
  return candidate,{'passed':False,'revision_attempted':bool(history),'error':str(exc)[:200],'qualitative_audit':{'findings':[{'severity':'major','location':'品質核對流程','problem':'核對或修正未完成','fix':'重新執行內容核對；目前版本未通過複核'}]}},history

def apply_changes(report, changes):
 """Apply replacements to existing report paths, then normal schema validation follows."""
 import copy
 if not isinstance(changes,list) or not 1<=len(changes)<=20:raise ValueError('修正需包含1至20個欄位')
 result=copy.deepcopy(report)
 for change in changes:
  if not isinstance(change,dict):raise ValueError('修正格式無效')
  path=change.get('path','')
  if not isinstance(path,str) or not path.startswith('/') or path=='/' or 'value' not in change:raise ValueError('修正路徑無效')
  keys=[k.replace('~1','/').replace('~0','~') for k in path[1:].split('/')]
  target=result
  for key in keys[:-1]:
   if isinstance(target,list) and key.isdigit() and int(key)<len(target):target=target[int(key)]
   elif isinstance(target,dict) and key in target:target=target[key]
   else:raise ValueError('修正引用未知路徑')
  key=keys[-1]
  if isinstance(target,list):
   if not key.isdigit() or int(key)>=len(target):raise ValueError('修正索引無效')
   target[int(key)]=change['value']
  elif isinstance(target,dict) and key in target:target[key]=change['value']
  else:raise ValueError('修正引用未知欄位')
 return result
