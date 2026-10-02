const $=s=>document.querySelector(s),token=$('meta[name="oracle-token"]').content;let current=null,timer=null,start=0,last=null,previewKey="",outlineObserver=null,pollFailures=0;
const labels={ok:'已取到資料',lead:'只有線索／無可用數據',error:'取數失敗',unchecked:'未檢查'};
async function api(path,body){const r=await fetch(path,{signal:AbortSignal.timeout(20000),method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Oracle-Token':token},body:body?JSON.stringify(body):undefined});let d;try{d=await r.json()}catch{const e=new Error(r.ok?'伺服器回應格式不正確，請重新整理頁面。':'伺服器暫時未能處理（HTTP '+r.status+'），請重新整理；如持續出現請重新啟動數字先知。');e.status=r.status;throw e}if(!r.ok||(d.error&&!d.id)){const e=new Error(d.error||'請求失敗');e.status=r.status;throw e}return d}
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n}
function badge(s){return el('span',labels[s]||s,'badge '+s)}
function time(s){return s?new Date(s).toLocaleString('zh-HK',{timeZone:'Asia/Hong_Kong',hour12:false}):'尚未檢查'}
function error(e){$('#error').textContent=e.message||String(e);$('#error').hidden=false}
async function status(){try{const d=await api('/api/status');const host=$('#sources');host.replaceChildren();for(const s of d.sources){if(s.id==='coingecko')continue;const row=el('div',undefined,'source'),info=el('div');info.append(el('span',s.name,'source-name'),el('small',s.error||s.description));row.append(info,badge(s.status));row.title='最近請求：'+time(s.checked_at);host.append(row)}return d}catch(e){$('#sources').textContent='伺服器未連接，請確認本地服務仍在運行。'}}
async function history(){try{const reports=await api('/api/history');$('#history').replaceChildren();for(const r of reports){const b=el('button',undefined,'history-entry');b.append(el('span',(r.revision_of?'修正版 · ':'')+time(r.created_at),'history-date'),el('span',r.question,'history-question'));b.disabled=!!timer;b.onclick=async()=>{try{const d=await api('/api/reports/'+r.id);render(d);$('#history-panel').open=false}catch(e){error(e)}};$('#history').append(b)}if(!reports.length)$('#history').textContent='完成第一份分析後會出現在這裏。'}catch(e){$('#history').textContent='研究紀錄暫時未能讀取。'}}
function busy(on){document.querySelectorAll('.history-entry').forEach(b=>b.disabled=on);$('#submit').disabled=on;$('#resume').disabled=on;$('#check').disabled=on;$('#progress').hidden=!on;$('#empty').hidden=on||!!last;$('#save-key').disabled=on;$('#download').disabled=on}
function cited(tag,text){const n=el(tag);for(const part of expandCitationRanges(String(text??'')).split(/(\[[a-z][a-z0-9_]*\])/g)){const id=part.slice(1,-1);if(part.startsWith('[')&&(last?.sources||[]).some(s=>s.id===id)){const source=(last.sources||[]).find(s=>s.id===id),a=el('a',source.name,'citation');a.href='#evidence-'+id;a.title='查閱證據：'+source.name+' ['+id+']';a.setAttribute('aria-label','查閱證據：'+source.name);a.onclick=()=>{const target=document.getElementById('evidence-'+id);if(target){target.open=true;for(let parent=target.parentElement;parent;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true}};if(n.lastChild?.nodeType===1&&n.lastChild.classList?.contains('citation'))n.append(document.createTextNode('、'));n.append(a)}else if(part)n.append(document.createTextNode(part))}return n}
function paragraphs(host,values){for(const v of values||[])host.append(cited('p',v))}
function table(headers,rows){const wrap=el('div',undefined,'table-wrap'),t=el('table'),head=el('thead'),tr=el('tr');for(const h of headers){const cell=el('th',h);cell.scope='col';tr.append(cell)}head.append(tr);t.append(head);const body=el('tbody');for(const row of rows){const r=el('tr');for(const [i,v] of row.entries()){const cell=cited('td',String(v??'未提供'));cell.dataset.label=headers[i]||'';if(typeof v==='number'||/^[-+−]?\d[\d,.]*(%|倍|期)?$/.test(String(v)))cell.classList.add('numeric');r.append(cell)}body.append(r)}t.append(body);wrap.append(t);wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label',headers.join('、')+'；可橫向捲動');return wrap}
function renderPlan(d){const p=d.plan;if(!p?.signals)return;$('#pipeline').hidden=false;document.body.classList.add('analysing');const host=$('#plan');host.replaceChildren();host.append(el('p','01 / 理解問題與規劃訊號','eyebrow'));for(const [label,key] of [['研究問題','core_variable'],['時間窗口','horizon'],['取數前的定價評估','priceability']]){if(p[key]){host.append(el('h3',label),el('p',p[key]))}}if(p.answer_spec){const names={probability:'事件機率',numeric_forecast:'數值預測',binary:'是非判斷',comparison:'比較分析',explanation:'解釋分析'};host.append(el('h3','答案形式'),el('p',(names[p.answer_spec.type]||p.answer_spec.type)+(p.answer_spec.unit?' · 單位：'+p.answer_spec.unit:'')))}host.append(el('p','02 / 市場訊號','eyebrow'));const states=new Map((d.sources||[]).map(s=>[s.id,s]));const groups=[...new Set(p.signals.map(s=>s.layer))];for(const layer of groups){host.append(el('h3',layer));const chips=el('div',undefined,'signal-chips');for(const sig of p.signals.filter(s=>s.layer===layer)){const state=states.get(sig.id),chip=el('span',(state?(state.status==='ok'?'✓ ':'! '):'○ ')+sig.label,'signal-chip '+(state?.status||'pending'));chip.title=sig.reason+'\n時間：'+sig.horizon+(state?.error?'\n'+state.error:'');chips.append(chip)}host.append(chips)}const ok=(d.sources||[]).filter(s=>s.status==='ok').length,failed=(d.sources||[]).filter(s=>s.status==='error').length;host.append(el('p',`${ok} 已取得 · ${failed} 未取得 · ${p.signals.length} 個規劃訊號`,'coverage'));host.append(el('p','03 / 缺口檢查與反證補查','eyebrow'));if(d.review){const review=el('details');review.append(el('summary','補查前的缺口評估（非最終計數）'),el('p',d.review));host.append(review)}host.append(el('p','04 / 分層分析與研究結論','eyebrow'));host.append(el('p',d.status==='done'?'分析完成':'分析中；取數成功不代表與問題直接相關。','muted'))}
function num(n,d=2){return n==null?'—':Number(n).toFixed(d)}
function renderQuant(host,q){if(!q)return;host.append(el('h2','跨市場量化核對'),el('p',`${q.price_series_count} 條完整價格序列 · ${q.pair_count} 組共同日期比較`,'muted'),el('p',q.method,'muted'));if(q.derived_series?.length){host.append(el('h3','相對價格與息差'));host.append(table(['計算項目','最近觀察','21期變化','樣本內分位'],q.derived_series.map(x=>[x.name+' '+x.signals.map(id=>'['+id+']').join(' '),x.last_date+'：'+num(x.latest,4),num(x.change_21_observations,4),num(x.sample_percentile,1)+'%（非事件概率）'])))}if(q.strongest_pairs?.length){host.append(el('h3','重複訊號與相關性'));host.append(el('p','按絕對相關性展示最高的10組，供識別可能重複的證據；未展示的配對不表示無關。','muted'));host.append(table(['訊號配對','樣本／截止日','回報相關性','近21期相關性'],q.strongest_pairs.slice(0,10).map(x=>['['+x.a+'] × ['+x.b+']',x.common_return_intervals+'期／'+x.to,num(x.return_correlation),num(x.recent_return_correlation)])))}if(q.target_pairs?.length){host.append(el('h3','目標資產對各金融市場'));host.append(table(['訊號配對','共同期數／截止日','回報相關性','近21期'],q.target_pairs.map(x=>['['+x.a+'] × ['+x.b+']',x.common_return_intervals+'期／'+x.to,num(x.return_correlation),num(x.recent_return_correlation)])))}if(q.rate_change_price_return_pairs?.length){host.append(el('h3','利率／息差變動與價格回報'));host.append(el('p','收益率與息差使用絕對變動，資產使用log回報；共同日期配對，不能解讀為因果。','muted'));host.append(table(['訊號配對','共同期數／截止日','變動對回報相關性','近21期'],q.rate_change_price_return_pairs.map(x=>['['+x.a+'] × ['+x.b+']',x.common_return_intervals+'期／'+x.to,num(x.change_return_correlation),num(x.recent_change_return_correlation)])))}paragraphs(host,q.cautions)}
function renderBaselines(host,sources){for(const source of sources||[]){const b=source.data?.terminal_return_baselines;if(!b)continue;host.append(el('h2','價格事件的統計對照'),el('p',source.name+' · '+b.event+' · '+b.calendar_days+' 日'),el('p','樣本日期：'+b.history_start+' 至 '+b.history_end,'muted'));host.append(table(['歷史窗口','事件次數／樣本數','歷史頻率（非預測）'],[['重疊窗口',b.historical_hits+' / '+b.overlapping_historical_windows,num(b.overlapping_frequency_pct,1)+'%'],['不重疊窗口',b.non_overlapping_hits+' / '+b.non_overlapping_windows,num(b.non_overlapping_frequency_pct,1)+'%']]));host.append(el('h3','固定波動模型：不同假設下的結果'));host.append(table(['波動估計樣本','年化波動','假設年化漂移','模型概率'],(b.constant_volatility_scenarios||[]).map(x=>[x.volatility_observations+'期',num(x.annualized_volatility_pct,1)+'%',x.assumed_annual_drift_pct+'%',num(x.probability_pct,1)+'%'])));if(b.stress_scenarios?.length){host.append(el('h3','壓力條件下的模型對照'),el('p',b.stress_method,'muted'));host.append(table(['假設波動倍數','年化波動','假設年化漂移','條件概率'],b.stress_scenarios.map(x=>[x.volatility_multiplier_assumption+'倍',num(x.annualized_volatility_pct,1)+'%',x.assumed_annual_drift_pct+'%',num(x.probability_pct,1)+'%'])))}if(b.walk_forward_baseline){const t=b.walk_forward_baseline;host.append(el('h3','只用當時資料的向前測試'),el('p',t.forecast_count+'次固定模型預測，實際事件'+t.event_count+'次；Brier分數 '+num(t.brier_score,3)+'（越低越好）'),el('p','同期歷史頻率基準 Brier：'+num(t.historical_benchmark_brier,3)),el('p',t.benchmark_method||'舊版本未計算此比較。','muted'),el('p',t.limitations,'muted'))}paragraphs(host,b.limits)}}
function renderReport(r){const host=$('#answer');host.replaceChildren();$('#report-title').textContent=r.title;renderSummary(r);if(last?.preview){const pending=el('p',last.status==='error'?'分析已中斷 · 已完成草稿保留，可接續核對。這不是最終版。':'草稿已完成 · 內容核對／修正中。這不是最終版，預測與文字仍可能更新。','audit-note');$('#quick-summary').prepend(pending);}const findings=last?.quality_audit?.qualitative_audit?.findings;
if(findings?.length){const review=el('details',undefined,'audit-note');review.append(el('summary','這份報告有 '+findings.length+' 項尚未解決的核對意見'));for(const f of findings)review.append(el('h4',f.location),el('p',f.problem),el('p','修正方向：'+f.fix));host.append(review)}
if(last?.revisions?.length){const history=el('details',undefined,'revision-history');history.append(el('summary','修訂紀錄 · 原稿與核對意見'));for(const item of last.revisions){for(const f of item.audit?.findings||[])history.append(el('p',f.location+'：'+f.problem+'；'+f.fix));const draft=el('details');draft.append(el('summary','查閱完整原稿 JSON'),el('pre',JSON.stringify(item.original_report,null,2)));history.append(draft)}host.append(history)}
const nav=el('nav',undefined,'report-nav');for(const [label,id] of [['查看答案','report-conclusion'],['情境與子結論','report-scenarios'],['監察指標','report-monitor']]){const a=el('a',label);a.href='#'+id;a.setAttribute('aria-label',label);nav.append(a)}host.append(nav);const p=r.answer||r.probability,card=el('section',undefined,'probability-card');card.id='report-conclusion';card.append(el('p',p.kind+' · 信心：'+p.confidence,'eyebrow'),el('strong',answerValue(r),'probability-value'),el('h3',p.target||p.event),el('p',p.range?(p.calculation?'替代假設範圍 ':p.kind.includes('示例')?'參數演算範圍 ':'合理範圍 ')+p.range[0]+'–'+p.range[1]+answerUnit(r):'','muted'),el('p',p.horizon,'muted'));host.append(el('h2','數據摘要'),el('p',r.coverage,'muted'));if(r.coverage_analysis)host.append(el('p',r.coverage_analysis,'muted'));for(const [index,layer] of r.layers.entries()){const section=el('details',undefined,'layer');section.id='report-layer-'+index;const heading=el('h3');heading.append(el('span',String(index+1).padStart(2,'0'),'layer-number'),document.createTextNode(layer.title.replace(/^[一二三四五六七八九十]+[、．.：:]\s*/,'')));const toggle=el('summary');toggle.append(heading);if(layer.summary)toggle.append(el('p',layer.summary,'layer-summary'));section.append(toggle);if(layer.horizon)section.append(el('p','時間層：'+layer.horizon+' ｜ 權重判斷：'+layer.weight,'muted'));section.append(table(['訊號 / 日期與數據','市場反映甚麼','限制與其他解釋'],layer.rows.map(x=>['['+x.signal_id+']\n'+(x.promotion_reasons?.length?'因異常升級：'+x.promotion_reasons.join('；')+'\n':'')+x.observation,x.interpretation,x.caveat])));host.append(section)}renderBaselines(host,last?.sources);renderQuant(host,last?.quantitative);host.append(el('h2','交叉分析'));for(const [key,title] of [['agreement','共振訊號'],['divergence','關鍵分歧'],['time_horizons','時間分層']]){host.append(el('h3',title));paragraphs(host,r.analysis[key])}host.append(el('h2','綜合判斷'),el('p',r.conclusion,'conclusion'),card);const advanced=el('details',undefined,'advanced');advanced.append(el('summary',r.answer?'進階：答案如何推算':'進階：機率如何推算'),cited('p',p.basis));if(p.assumptions){advanced.append(el('h3','估計依賴的假設'));paragraphs(advanced,p.assumptions)}if(p.sensitivity){advanced.append(el('h3','換一個假設，答案會怎樣變？'));advanced.append(el('p','以下為分析假設下的敏感度比較，並非回測結果。','muted'));advanced.append(table(['替代情況','初步估計','原因'],p.sensitivity.map(s=>[s.case,s.estimate==null?'移除後失去量化基礎':s.estimate+answerUnit(r),s.reason])))}if(p.calculation?.method==='conditional_bridge'){const c=p.calculation;advanced.append(el('h3','研究估計的計算紀錄'),el('p','以下參數由研究模型根據證據選定，中心數字由程式重算；未經回測校準。','muted'),table(['項目','數值','依據'],[['基準事件的機率',c.baseline_pct+'%',c.baseline_event+'：'+c.baseline_reason],['基準事件發生時，目標發生的估計',c.target_given_baseline_pct+'%',c.conditional_reason],['基準事件未發生時，目標仍發生的估計',c.target_without_baseline_pct+'%','補足不同事件定義及期限的情境']]),el('p',c.formula+' → '+p.estimate+'%'),table(['分析渠道','方向','判斷理由'],(c.channels||[]).map(x=>[x.name,x.effect,x.reason])))}if(p.calculation?.method==='baseline_adjustments'){const c=p.calculation;advanced.append(el('h3','預測水平的計算紀錄'),el('p',c.baseline_reason),table(['項目','水平或調整','依據'],[['歷史基準',c.baseline_value+p.unit,(c.baseline_period||'')+' ['+c.baseline.signal_id+']'],...c.adjustments.map(x=>[x.name,(x.delta>=0?'+':'')+x.delta+(p.unit==='%'?' 個百分點':p.unit),x.reason])]),el('p',c.formula+' → '+p.estimate+p.unit));}host.append(advanced);const scenariosTitle=el('h2',r.answer?'替代情境':'情境與機率');scenariosTitle.id='report-scenarios';host.append(scenariosTitle);host.append(table(['情境',r.answer?'預測水平／條件':'概率','依據','觸發條件'],r.scenarios.map(s=>[s.name,r.answer?(s.estimate!=null?s.estimate+(s.unit||p.unit):'條件判斷'):(s.probability===null?'未量化':s.probability+'%'),s.basis,s.trigger])));if(r.sub_conclusions){host.append(el('h3','子結論'));host.append(table(['維度','判斷','信心程度','支持與反對訊號'],r.sub_conclusions.map(s=>[s.dimension,s.judgment,s.confidence,s.evidence])))}host.append(el('h3','核心邏輯鏈'));paragraphs(host,r.logic_chain);const monitorTitle=el('h2','需要監察的變化');monitorTitle.id='report-monitor';host.append(monitorTitle);host.append(table(['訊號','目前觀察','觸發條件','含意'],r.monitor.map(m=>[signalLabel(m.signal),m.current,m.trigger,m.meaning])));host.append(el('h3','資料限制'));paragraphs(host,[...new Set([...(r.limitations||[]),p.limitations].filter(Boolean))]);renderTiming(host,last?.timing||r.timing);decorateReport(r)}
function render(d){last=d;$('#download-pdf').disabled=!d.report;renderPlan(d);renderTimeline(d);$('#result').hidden=false;$('#empty').hidden=true;$('#result-question').textContent=d.question;$('#report-title').textContent=d.report?.title||d.question;$('#result-time').textContent='取數／分析開始於 '+time(d.created_at)+' HKT'+(d.revision_note?' ｜ '+d.revision_note:Array.isArray(d.revision_notes)?' ｜ '+d.revision_notes.join('；'):'');if(d.report)renderReport(d.report);else $('#answer').replaceChildren(...(d.answer||'').split(/\n\s*\n/).map(p=>el('p',p)));const box=$('#evidence');box.replaceChildren();for(const s of d.sources||[]){const det=el('details',undefined,'evidence'),sum=el('summary');det.id='evidence-'+s.id;sum.append(el('span','['+s.id+'] '+s.name),badge(s.status));det.append(sum,el('p','抓取時間：'+time(s.checked_at)+(s.cache_hit?'（重用30分鐘內快取，保留原抓取時間）':''),'muted'));if(s.quality){det.append(el('p','觀察日期：'+(s.quality.observation_date||'未提供／依各合約資料')+(s.quality.age_days!=null?' · 相距 '+s.quality.age_days+' 日':''),'muted'));paragraphs(det,s.quality.notes)}if(s.url&&s.url.startsWith('https://')){const a=el('a','前往來源 ↗');a.href=s.url;a.target='_blank';a.rel='noopener noreferrer';det.append(a)}const links=Array.isArray(s.data)?s.data.filter(x=>x?.url?.startsWith('https://')).map(x=>({url:x.url,title:x.title||x.url})):s.data?.url?.startsWith('https://')?[{url:s.data.url,title:s.data.name||s.data.series||'具體資料序列'}]:[];for(const link of links.slice(0,6)){const p=el('p'),a=el('a',link.title+' ↗');a.href=link.url;a.target='_blank';a.rel='noopener noreferrer';p.append(a);det.append(p)}det.append(el('pre',JSON.stringify(s.data||{error:s.error},null,2)));box.append(det)}}
async function poll(){try{const d=await api('/api/jobs/'+current+'?brief=1');pollFailures=0;$('#error').hidden=true;renderPlan(d);renderTimeline(d);if(d.created_at)start=Date.parse(d.resume_started_at||d.created_at);$('#stage').textContent=d.stage.replace('根據核對意見修正報告（最多一次）','草稿已完成 · 修正中（1/1）').replace('核對市場證據與報告內容','草稿已完成 · 核對內容').replace('複核修正版','修正已完成 · 最後複核');$('#elapsed').textContent='總計 '+Math.floor((Date.now()-start)/1000)+' 秒'+(d.model_phase_started_at?' · 本階段 '+Math.max(0,Math.floor((Date.now()-Date.parse(d.model_phase_started_at))/1000))+' 秒':'');$('#progress-sources').replaceChildren(...(d.sources||[]).map(s=>{const b=badge(s.status);b.textContent=s.name+' · '+labels[s.status];return b}));if(d.status==='running'){if(d.generated_report&&previewKey!=='draft-'+(d.draft_revision||0)){const full=await api('/api/jobs/'+current);render({...full,report:full.generated_report,preview:true});previewKey='draft-'+(d.draft_revision||0)}else if(!d.generated_report&&d.quantitative){const key=d.sources.length+':'+d.quantitative.pair_count;if(key!==previewKey){previewKey=key;$('#result').hidden=false;$('#result-question').textContent=d.question;$('#report-title').textContent='市場訊號已取得';$('#result-time').textContent='數據已取得，完整判斷及預測仍在分析中';$('#answer').replaceChildren();renderQuant($('#answer'),d.quantitative);$('#evidence').replaceChildren()}}timer=setTimeout(poll,1500);return}timer=null;busy(false);sessionStorage.removeItem('oracleJob');if(d.status==='error'){const resumable=!d.no_market_data&&!!d.plan&&(d.sources||[]).some(s=>s.status==='ok'),msg=d.error||'分析未完成';error(new Error(resumable&&!/已保存/.test(msg)?msg.replace(/[。．.]\s*$/,'')+'；已取得的數據已保存，可直接接續報告。':msg));if(d.generated_report||d.report||d.sources?.length){render({...d,report:d.report||d.generated_report,preview:true});if(!d.report&&!d.generated_report){$('#report-title').textContent=resumable?'數據已保存，報告尚未完成':'分析未完成';$('#answer').replaceChildren();renderQuant($('#answer'),d.quantitative)}}if(resumable){$('#resume').dataset.job=d.id;$('#resume').title=d.question||'';$('#resume').hidden=false}}else render(d);await status();await history()}catch(e){if(e.status&&e.status<500){timer=null;busy(false);error(e);return}pollFailures++;error(new Error('進度連線暫時中斷，正在重新連線（'+pollFailures+'）；分析可能仍在伺服器運行，已顯示內容會保留。'));timer=setTimeout(poll,Math.min(10000,1500*pollFailures))}}
async function launch(path,body){$('#error').hidden=true;$('#resume').hidden=true;$('#result').hidden=true;last=null;$('#quick-summary')?.remove();previewKey='';outlineObserver?.disconnect();$('#report-outline').replaceChildren();$('#research-metrics').replaceChildren();$('#pipeline').hidden=false;$('#plan').replaceChildren();busy(true);start=Date.now();$('#stage').textContent='準備中';$('#progress-sources').replaceChildren();try{const d=await api(path,body);current=d.id;sessionStorage.setItem('oracleJob',JSON.stringify({id:current,start}));poll()}catch(e){busy(false);error(e)}}
$('#ask').addEventListener('submit',e=>{e.preventDefault();const q=$('#question').value.trim();if(q.length<3)return error(new Error('請輸入至少三個字。'));launch('/api/ask',{question:q})});
for(const b of document.querySelectorAll('[data-q]'))b.onclick=()=>{$('#question').value=b.dataset.q;$('#question').focus()};
$('#resume').onclick=()=>launch('/api/resume',{id:$('#resume').dataset.job});
$('#check').onclick=()=>launch('/api/check',{});
$('#download').onclick=()=>{if(!last)return;const blob=new Blob([JSON.stringify(last,null,2)],{type:'application/json;charset=utf-8'}),u=URL.createObjectURL(blob),a=el('a');a.href=u;a.download='oracle-analysis.json';a.click();URL.revokeObjectURL(u)};
$('#save-key').onclick=async()=>{const b=$('#save-key');b.disabled=true;$('#key-result').textContent='驗證中…';try{const d=await api('/api/key',{key:$('#key').value});$('#key').value='';$('#key-result').textContent=d.message;await status()}catch(e){$('#key-result').textContent=e.message}finally{b.disabled=false}};
(async()=>{const state=await status();await history();try{const saved=state?.active_job?{id:state.active_job,start:Date.now()}:null;if(saved){current=saved.id;start=saved.start;busy(true);poll()}else{sessionStorage.removeItem('oracleJob');const d=await api('/api/last');if(d.answer){render(d);if(location.hash==='#result')$('#result').scrollIntoView()}const recovery=await api('/api/recoverable');if(recovery.id){$('#resume').dataset.job=recovery.id;$('#resume').hidden=false;$('#resume').title=recovery.question}}}catch(e){error(e)}})();

// Navigation and coverage describe the loaded report, never illustrative market data.
function decorateReport(report){
 const metrics=$('#research-metrics');metrics.replaceChildren();
 const measures=[[report.layers.length,'分析層次'],[(last.sources||[]).filter(s=>s.status==='ok').length,'已取得訊號']];
 if(last.quantitative?.pair_count!=null)measures.push([last.quantitative.pair_count,'共同日期比較']);
 for(const [value,label] of measures){const group=el('div');group.append(el('strong',String(value)),el('span',label));metrics.append(group)}
 const value=$('.probability-value');
 if(value)value.replaceChildren(el('small',report.answer?.direction_only?'方向判斷':report.answer?.type==='numeric_forecast'?'預測水平':report.answer?'研究判斷':'初步估計'),document.createTextNode(answerValue(report)));
 const outline=$('#report-outline');outline.replaceChildren(el('p','研究導覽 / CONTENTS'));
 const entries=[['研究摘要','result'],...report.layers.map((layer,i)=>[layer.title,'report-layer-'+i]),['答案與依據','report-conclusion'],['情境與子結論','report-scenarios'],['監察指標','report-monitor']];
 for(const [label,id] of entries){const link=el('a',label);link.href='#'+id;link.onclick=()=>{const target=document.getElementById(id);if(target?.tagName==='DETAILS')target.open=true};outline.append(link)}
 outlineObserver?.disconnect();
 const links=[...outline.querySelectorAll('a')];
 outlineObserver=new IntersectionObserver(items=>{for(const entry of items){if(entry.isIntersecting){for(const link of links){if(link.hash==='#'+entry.target.id)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current')}}}},{rootMargin:'-5% 0px -65% 0px',threshold:0});
 for(const [,id] of entries){const target=document.getElementById(id);if(target)outlineObserver.observe(target)}
}

// Hero: an abstract signal-convergence field. Four families of strands (the
// legend's signal types) flow through three analysis planes into one focal
// point. It is illustrative only and contains no simulated market data.
(()=>{
 const canvas=$('#signal-canvas');if(!canvas)return;const ctx=canvas.getContext('2d');if(!ctx)return;
 const reduced=matchMedia('(prefers-reduced-motion: reduce)');
 let energy=0,energyBase=0,energyTarget=0,w=0,h=0,scale=1,frame=0,visible=true,base=null,strands=[],particles=[],px=0,py=0,tx=0,ty=0,t0=performance.now();
 const families=[[143,230,193],[180,196,188],[143,230,193],[180,196,188]];
 function focus(){return {x:w*.72+px*14,y:h*.5+py*10}}
 function build(){
  strands=[];const f=focus();
  for(let fam=0;fam<4;fam++){
   const sy=h*(.16+fam*.225);
   for(let i=0;i<14;i++){
    const o=(i-6.5)*h*.0042,spread=(fam-1.5)*h*.012+o*.25;
    strands.push({fam,p0:{x:w*.02,y:sy+o},p1:{x:w*.34,y:sy+o*1.1},p2:{x:w*.5,y:f.y+spread*2.2},p3:{x:f.x,y:f.y+spread*.2},accent:fam===0||fam===2,i})
   }
  }
  const keep=particles.length;particles=keep?particles.map((p,k)=>({...p,s:strands[(k*7)%strands.length]})):Array.from({length:Math.min(110,Math.round(w/9))},(_,k)=>({s:strands[(k*7)%strands.length],t:Math.random(),v:.035+Math.random()*.05,r:.6+Math.random()*1.3}));
  // Static layer: strands, planes and scale ticks rendered once per resize/parallax step.
  if(!base||base.width!==canvas.width||base.height!==canvas.height){base=document.createElement('canvas');base.width=canvas.width;base.height=canvas.height}const b=base.getContext('2d');b.setTransform(1,0,0,1,0,0);b.clearRect(0,0,base.width,base.height);b.setTransform(scale,0,0,scale,0,0);
  b.strokeStyle='rgba(226,240,233,.07)';b.lineWidth=1;
  for(let x=w*.08;x<w;x+=w*.06){b.beginPath();b.moveTo(x,h*.06);b.lineTo(x,h*.06+5);b.moveTo(x,h*.94);b.lineTo(x,h*.94-5);b.stroke()}
  for(const s of strands){
   const g=b.createLinearGradient(s.p0.x,0,s.p3.x,0),c=families[s.fam].join(',');
   g.addColorStop(0,`rgba(${c},0)`);g.addColorStop(.35,`rgba(${c},${s.accent?.22:.12})`);g.addColorStop(1,`rgba(${c},${s.accent?.5:.26})`);
   b.strokeStyle=g;b.lineWidth=s.i===6||s.i===7?.9:.55;b.beginPath();b.moveTo(s.p0.x,s.p0.y);b.bezierCurveTo(s.p1.x,s.p1.y,s.p2.x,s.p2.y,s.p3.x,s.p3.y);b.stroke()
  }
  for(let k=0;k<3;k++){
   const x=w*(.42+k*.085),top=h*(.14+k*.07),bot=h*(.86-k*.07),sl=w*.045;
   b.beginPath();b.moveTo(x,top);b.lineTo(x+sl,top+h*.05);b.lineTo(x+sl,bot+h*.05);b.lineTo(x,bot);b.closePath();
   const g=b.createLinearGradient(x,0,x+sl,0);g.addColorStop(0,'rgba(143,230,193,.02)');g.addColorStop(1,'rgba(143,230,193,.085)');b.fillStyle=g;b.fill();
   b.strokeStyle='rgba(143,230,193,.22)';b.lineWidth=.7;b.stroke()
  }
 }
 function at(s,t){const u=1-t;return {x:u*u*u*s.p0.x+3*u*u*t*s.p1.x+3*u*t*t*s.p2.x+t*t*t*s.p3.x,y:u*u*u*s.p0.y+3*u*u*t*s.p1.y+3*u*t*t*s.p2.y+t*t*t*s.p3.y}}
 function draw(now,dt){
  ctx.clearRect(0,0,w,h);if(base){ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.drawImage(base,0,0);ctx.restore()}
  const f=focus(),time=(now-t0)/1000;
  ctx.globalCompositeOperation='lighter';
  for(const p of particles){
   p.t+=p.v*dt*(1+energy*3.2);if(p.t>1)p.t-=1;
   const q=at(p.s,p.t),near=Math.pow(p.t,3),a=Math.sin(Math.PI*Math.min(1,p.t*1.15))*.9;
   ctx.fillStyle=`rgba(${p.s.accent?'200,245,225':'226,240,233'},${(.25+near*.75)*a})`;
   ctx.beginPath();ctx.arc(q.x,q.y,p.r*(1+near*.6),0,6.283);ctx.fill()
  }
  // Focal glow and slow concentric rings: the point where evidence converges.
  const glow=ctx.createRadialGradient(f.x,f.y,0,f.x,f.y,h*.22);glow.addColorStop(0,`rgba(143,230,193,${.28+energy*.3})`);glow.addColorStop(.4,'rgba(143,230,193,.06)');glow.addColorStop(1,'rgba(143,230,193,0)');
  ctx.fillStyle=glow;ctx.beginPath();ctx.arc(f.x,f.y,h*.22,0,6.283);ctx.fill();
  ctx.globalCompositeOperation='source-over';
  for(let k=0;k<3;k++){const ph=((time*(.22+energy*.5))+k/3)%1,r=8+ph*h*.2;ctx.strokeStyle=`rgba(143,230,193,${.45*(1-ph)})`;ctx.lineWidth=.8;ctx.beginPath();ctx.arc(f.x,f.y,r,0,6.283);ctx.stroke()}
  ctx.strokeStyle='rgba(200,245,225,.9)';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(f.x,f.y-h*.075);ctx.lineTo(f.x,f.y+h*.075);ctx.stroke();
  ctx.fillStyle='#e6fff4';ctx.shadowColor='#8fe6c1';ctx.shadowBlur=18;ctx.beginPath();ctx.arc(f.x,f.y,3.2+energy*2.5,0,6.283);ctx.fill();ctx.shadowBlur=0
 }
 let lastT=performance.now(),builtAt={x:0,y:0};
 function loop(now){
  const dt=Math.min(.05,(now-lastT)/1000);lastT=now;
  px+=(tx-px)*.05;py+=(ty-py)*.05;energyTarget=Math.max(energyBase,energyTarget-dt*.9);energy+=(energyTarget-energy)*Math.min(1,dt*4);
  if(Math.abs(px-builtAt.x)>.04||Math.abs(py-builtAt.y)>.04){build();builtAt={x:px,y:py}}
  draw(now,dt);
  if(visible&&!document.hidden&&!reduced.matches)frame=requestAnimationFrame(loop)
 }
 function start(){cancelAnimationFrame(frame);lastT=performance.now();if(reduced.matches){draw(performance.now(),0);return}frame=requestAnimationFrame(loop)}
 function size(){const r=canvas.getBoundingClientRect();w=r.width;h=r.height;if(!w||!h)return;scale=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(w*scale);canvas.height=Math.round(h*scale);ctx.setTransform(scale,0,0,scale,0,0);build();if(reduced.matches){for(const p of particles)p.t=Math.random();draw(performance.now(),0)}}
 new ResizeObserver(size).observe(canvas);size();
 new IntersectionObserver(([e])=>{visible=e.isIntersecting;if(visible)start();else cancelAnimationFrame(frame)}).observe(canvas);
 if(matchMedia('(pointer:fine)').matches)addEventListener('pointermove',e=>{tx=e.clientX/innerWidth*2-1;ty=e.clientY/innerHeight*2-1},{passive:true});
 reduced.addEventListener('change',start);
 document.addEventListener('oracle:energy',e=>{const d=e.detail||{};if('base' in d)energyBase=d.base;if('pulse' in d)energyTarget=Math.min(1,Math.max(energyTarget,d.pulse))});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden&&visible)start()});
 start();
})();

$('.header-nav a[href="#history-panel"]').addEventListener('click',()=>{$('#history-panel').open=true});

new IntersectionObserver(entries=>{for(const entry of entries)$('.back-top').hidden=entry.isIntersecting},{threshold:0}).observe($('.intro'));

function firstSentence(text){return String(text||'').split(/(?<=[。！？])\s*/)[0]}
function signalLabel(value){return (last?.sources||[]).some(s=>s.id===value)?'['+value+']':value}
function answerUnit(r){return r.answer?.unit??'%'}
function answerValue(r){const a=r.answer;if(a){if(a.type==='numeric_forecast'&&a.estimate==null)return String(a.text||'未能量化').split(/[；;。]/)[0];if(a.type==='numeric_forecast')return (a.unit==='%'&&Number.isInteger(a.estimate)?a.estimate.toFixed(1):a.estimate)+a.unit;if(a.type==='binary')return a.decision?'是':'否';return a.text}const p=r.probability||{};return p.estimate==null?'未選定中心':p.estimate+'%'}
function renderSummary(r){
 let box=$('#quick-summary');if(!box){box=el('section',undefined,'quick-summary');box.id='quick-summary';$('#research-metrics').after(box)}box.replaceChildren();
 const p=r.answer||r.probability||{},top=el('div',undefined,'summary-top');
 top.append(el('p',(last?.preview||last?.quality_audit?.passed===false?'待核對草稿 · ':'最終版 · ')+'一眼結論','eyebrow'),el('strong',answerValue(r),'summary-number'),el('p',(p.range?p.range.join('–')+answerUnit(r)+' · ':'')+(p.horizon||'期限未提供'),'summary-range'));
 if(!r.answer&&p.estimate==null&&p.range)top.append(el('p','參數情境包絡 · 沒有優先中心','muted'));box.append(top,cited('blockquote',r.headline_summary||firstSentence(r.conclusion)),el('p',(p.kind||'')+' · 信心：'+(p.confidence||'未提供'),'muted'));
 const grid=el('div',undefined,'summary-signals');
 for(const [label,items] of [['主要支持',r.analysis?.agreement],['主要反證／分歧',r.analysis?.divergence]]){const part=el('div');part.append(el('h3',label));for(const item of (items||[]).filter(x=>!/(不能算兩票|不能重複|不可重複|同業共同因素)/.test(x)).slice(0,2)){const line=cited('p',firstSentence(item));line.title=String(item).replace(/\[[a-z][a-z0-9_]*\]/g,'');part.append(line)}grid.append(part)}box.append(grid);
 const m=r.monitor?.[0];if(m)box.append(cited('p','首要監察：'+signalLabel(m.signal)+' · 觸發門檻：'+m.trigger));
}

function expandCitationRanges(text){return text.replace(/\[([a-z][a-z0-9_]*?)(\d+)至\1(\d+)\]/g,(match,prefix,start,end)=>{const a=Number(start),b=Number(end);if(b<a||b-a>=40)return match;const ids=Array.from({length:b-a+1},(_,i)=>prefix+String(a+i).padStart(start.length,'0'));return ids.every(id=>(last?.sources||[]).some(s=>s.id===id))?ids.map(id=>'['+id+']').join(' '):match})}

function renderTiming(host,timing){if(!timing)return;const box=el('details',undefined,'advanced');box.append(el('summary','分析耗時'));const names={signal_planning:'規劃訊號',data_collection:'並行取數',statistics:'統計計算',liquidity_anchor:'流動性與期限核對',prompt_assembly:'組合模型輸入'};const entries=[...(timing.stages||[]),...(timing.models||[])].sort((a,b)=>a.started_at.localeCompare(b.started_at));box.append(table(['階段','耗時（秒）','輸入字元','輸出字元'],entries.map(x=>[names[x.name]||x.name,x.seconds,x.input_characters??'—',x.output_characters??'—'])));box.append(el('p','字數按 Unicode 字元計算；並行來源耗時不可相加當作總耗時。','muted'));for(const m of timing.models||[]){if(m.components)box.append(el('p',m.name+'：'+Object.entries(m.components).map(([k,v])=>k+' '+v).join('；'),'muted'))}box.append(table(['來源','耗時（秒）','重試','狀態'],(timing.providers||[]).map(x=>[x.signal_id+' · '+x.name,x.seconds,x.retry?'是':'否',x.timed_out?'逾時':x.status==='ok'?'已完成':'失敗'])));host.append(box)}

// Presentation only: relocate existing controls without replacing their handlers.
const footerTools=el('section',undefined,'footer-tools');$('.workspace').append(footerTools);
footerTools.append($('#history-panel'),$('.plan-details'));
const evidencePanel=el('details');evidencePanel.append(el('summary','查閱證據'),$('.evidence-title'),$('#evidence'));footerTools.append(evidencePanel);
const observatoryPanel=el('details');observatoryPanel.append(el('summary','資源觀測站'),$('#observatory'));footerTools.append(observatoryPanel);
$('.header-nav a[href="#observatory"]').addEventListener('click',()=>{observatoryPanel.open=true});
const outlineMenu=el('details',undefined,'outline-menu');outlineMenu.append(el('summary','研究導覽'));$('#report-outline').before(outlineMenu);outlineMenu.append($('#report-outline'));
const wideNavigation=matchMedia('(min-width:1024px)');outlineMenu.open=wideNavigation.matches;wideNavigation.addEventListener('change',e=>{outlineMenu.open=e.matches});

function renderTimeline(job){if(!job.pipeline?.length)return;let root=$('#timeline');if(!root){root=el('details',undefined,'timeline');root.id='timeline';root.append(el('summary'),el('ol'));$('.analysis-layout').before(root)}const done=job.status==='done',failed=job.status==='error';if(root.dataset.job!==job.id){root.dataset.job=job.id;root.open=!done;root.querySelector('ol').replaceChildren()}if(done&&root.dataset.status!=='done')root.open=false;root.dataset.status=job.status;const duration=Math.max(0,Math.round(((done||failed?Date.parse(job.completed_at||job.pipeline.at(-1).ended_at):Date.now())-Date.parse(job.resume_started_at||job.created_at))/1000));const count=(job.sources||[]).filter(s=>s.status==='ok').length;root.querySelector('summary').textContent=(done?'分析完成':failed?'分析中斷':'分析進度')+' · '+Math.floor(duration/60)+' 分 '+duration%60+' 秒 · '+count+' 個訊號';const titles=['理解問題與規劃訊號','拉取市場數據','計算統計與異常檢查','分析核心訊號','生成一眼結論（草稿）','宏觀背景與核對','完成'];const list=root.querySelector('ol');for(let i=1;i<=7;i++){let li=list.children[i-1];if(!li){li=el('li');li.append(el('span',String(i),'timeline-node'));const det=el('details');const sum=el('summary');sum.append(el('strong',titles[i-1]),el('span','','timeline-state'));det.append(sum,el('div',undefined,'timeline-detail'));li.append(det);list.append(li)}const step=job.pipeline.find(x=>x.index===i);let state=step?.status||'waiting';const misses=i===2?(job.sources||[]).filter(s=>s.status==='error'):[];if((failed&&state==='running')||misses.length&&state==='done')state='error';li.dataset.state=state;li.querySelector('.timeline-node').textContent=state==='done'?'✓':state==='error'?'!':String(i);let detail=state==='waiting'?'等待中':state==='running'?'分析中…':'完成 · '+(step?.seconds??0)+' 秒';if(i===2&&state==='running')detail='已取得 '+count+'／'+(job.plan?.signals?.length||0);if(i===3&&job.promotions)detail+=' · 升級 '+job.promotions.length+' 個異常訊號';if(state==='error')detail=misses.length?misses.length+' 個來源失敗，已略過':job.error||'此階段未完成';li.querySelector('.timeline-state').textContent=detail;li.querySelector('.timeline-detail').textContent=i===2?(job.sources||[]).map(s=>s.name+'：'+(labels[s.status]||s.status)+(s.error?'（'+s.error+'）':'')).join('、'):i===3?(job.promotions||[]).map(p=>p.name+'：'+p.reasons.join('；')).join('。'):step?.detail||''}}

$('#download-pdf').onclick=async()=>{if(!last?.report)return;const button=$('#download-pdf'),id=last.id,title=last.report.title;button.disabled=true;button.textContent='正在產生 PDF…';try{const response=await fetch('/api/pdf/'+encodeURIComponent(id),{headers:{'X-Oracle-Token':token}});if(!response.ok){const data=await response.json();throw new Error(data.error||'PDF產生失敗')}const blob=await response.blob(),url=URL.createObjectURL(blob),link=el('a');link.href=url;link.download=(title||'數字先知報告').replace(/[\\/:*?"<>|]/g,'-').slice(0,100)+'.pdf';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),10000)}catch(e){error(e)}finally{button.disabled=!last?.report;button.textContent='下載 PDF 報告 ↓'}};

// Motion & interaction layer (presentation only; never changes report data).
(()=>{
 const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches,fine=matchMedia('(pointer:fine)').matches;
 if(!reduce)document.documentElement.classList.add('js-motion');
 // Header state and reading progress, throttled to one update per frame.
 const header=$('header'),bar=$('.scroll-progress');let ticking=false;
 function onScroll(){ticking=false;const y=scrollY,max=document.documentElement.scrollHeight-innerHeight;header.classList.toggle('scrolled',y>12);bar.style.setProperty('--progress',max>0?Math.min(1,y/max).toFixed(4):0)}
 addEventListener('scroll',()=>{if(!ticking){ticking=true;requestAnimationFrame(onScroll)}},{passive:true});onScroll();
 // Scroll reveal.
 const revealer=reduce?null:new IntersectionObserver(items=>{for(const e of items)if(e.isIntersecting){e.target.classList.add('in');revealer.unobserve(e.target)}},{rootMargin:'0px 0px -8% 0px',threshold:.06});
 function reveal(nodes,step=.06){if(!revealer)return;let i=0;for(const n of nodes){if(!n||n.classList.contains('reveal'))continue;n.classList.add('reveal');n.style.setProperty('--delay',Math.min(i++*step,.36)+'s');revealer.observe(n)}}

 reveal(document.querySelectorAll('.empty li'),.1);
 reveal([$('.footer-tools'),$('.footer-mark')]);
 // Pointer spotlight on surfaces.
 if(fine)document.addEventListener('pointermove',e=>{const t=e.target.closest?.('#ask,.quick-summary,.history-entry');if(!t)return;const r=t.getBoundingClientRect();t.style.setProperty('--mx',(e.clientX-r.left)+'px');t.style.setProperty('--my',(e.clientY-r.top)+'px')},{passive:true});
 // Magnetic primary button.
 const primary=$('#submit');
 if(fine&&!reduce){primary.addEventListener('pointermove',e=>{const r=primary.getBoundingClientRect();primary.style.setProperty('--tx',((e.clientX-r.left-r.width/2)*.18).toFixed(1)+'px');primary.style.setProperty('--ty',((e.clientY-r.top-r.height/2)*.28).toFixed(1)+'px')});primary.addEventListener('pointerleave',()=>{primary.style.setProperty('--tx','0px');primary.style.setProperty('--ty','0px')})}
 // Rotating example questions in the empty console.
 const q=$('#question'),examples=[q.placeholder,'例如：黃金未來一個月的持倉與期權訊號有沒有矛盾？','例如：Bitcoin 三個月內跌穿某個價位的機率有多大？','例如：香港明年平均失業率會升還是跌？','例如：美國國債收益率曲線正在反映甚麼？'];let ex=0;
 if(!reduce)setInterval(()=>{if(q.value||document.activeElement===q||document.hidden)return;q.classList.add('placeholder-out');setTimeout(()=>{ex=(ex+1)%examples.length;q.placeholder=examples[ex];q.classList.remove('placeholder-out')},380)},4200);
 // Count-up for numeric results.
 function countUp(node,dur=1400){
  const text=node.textContent.trim(),m=text.match(/^([^\d-]*)(-?\d+(?:\.\d+)?)(.*)$/s);if(!m||node.dataset.counted===text)return;node.dataset.counted=text;if(reduce||document.hidden)return;
  const [,pre,num,post]=m,target=parseFloat(num),dec=(num.split('.')[1]||'').length,start=performance.now(),first=node.firstChild&&node.firstChild.nodeType===1?node.firstChild:null;
  const textNode=[...node.childNodes].find(n=>n.nodeType===3&&/\d/.test(n.textContent));if(!textNode)return;const original=textNode.textContent;
  const tpre=original.slice(0,original.indexOf(num)),tpost=original.slice(original.indexOf(num)+num.length);
  (function tick(now){const k=Math.min(1,(now-start)/dur),e=1-Math.pow(1-k,4);textNode.textContent=tpre+(target*e).toFixed(dec)+tpost;if(k<1)requestAnimationFrame(tick);else textNode.textContent=original})(start);setTimeout(()=>{textNode.textContent=original},dur+250)
 }
 // Range bar under the headline figure: shows the reported range and centre.
 function rangeBar(){
  const box=$('#quick-summary'),r=last?.report;if(!box||!r)return;box.querySelector('.range-bar')?.remove();
  const p=r.answer||r.probability||{},range=p.range,est=typeof p.estimate==='number'?p.estimate:null;
  if(!Array.isArray(range)||range.length<2||!range.every(v=>typeof v==='number'&&isFinite(v))||range[1]<=range[0])return;
  const unit=r.answer?(p.unit??''):'%',[lo,hi]=range,span=hi-lo,hb=Array.isArray(p.historical_band?.range)?p.historical_band.range:null;let min=Math.min(lo-span*.75,hb?hb[0]-span*.25:Infinity),max=Math.max(hi+span*.75,hb?hb[1]+span*.25:-Infinity);if(unit==='%'&&!r.answer){min=Math.max(0,min);max=Math.min(100,max)}
  const pos=v=>((v-min)/(max-min)*100).toFixed(2)+'%',fmt=v=>(Math.round(v*100)/100)+unit;
  const wrap=el('div',undefined,'range-bar');wrap.setAttribute('role','img');wrap.setAttribute('aria-label','合理範圍 '+fmt(lo)+' 至 '+fmt(hi)+(est!=null?'，中心 '+fmt(est):''));
  const track=el('span',undefined,'track'),band=el('span',undefined,'band');
  if(hb){const h=el('span',undefined,'hist');h.style.left=pos(hb[0]);h.style.width=((hb[1]-hb[0])/(max-min)*100).toFixed(2)+'%';h.title='歷史波動參照（一個標準差）：'+fmt(hb[0])+'–'+fmt(hb[1]);wrap.append(h);const l=el('span','歷史波動 '+fmt(hb[0])+'–'+fmt(hb[1]),'hist-label');wrap.append(l);wrap.classList.add('has-hist')}band.style.left=pos(lo);band.style.width=((hi-lo)/(max-min)*100).toFixed(2)+'%';wrap.append(track,band);
  const tl=el('span',fmt(lo),'tick'),th=el('span',fmt(hi),'tick');tl.style.left=pos(lo);th.style.left=pos(hi);wrap.append(tl,th);
  if(est!=null&&est>=min&&est<=max){const mark=el('span',undefined,'mark');mark.style.left=pos(est);wrap.append(mark)}
  box.querySelector('.summary-top')?.after(wrap)
 }
 // Run an effect once, when the element first becomes visible.
 const seenIO=new IntersectionObserver(items=>{for(const e of items)if(e.isIntersecting){seenIO.unobserve(e.target);const f=e.target._onSeen;e.target._onSeen=null;f&&f()}},{threshold:.35});
 function whenSeen(n,f){if(!n)return;n._onSeen=f;seenIO.unobserve(n);seenIO.observe(n)}
 window.oracleWhenSeen=whenSeen;
 // Enhance every freshly rendered report.
 let pending=0;
 function enhance(){
  pending=0;const answer=$('#answer');if(!answer.children.length)return;
  let n=0;for(const h of answer.querySelectorAll(':scope>h2'))h.dataset.index=String(++n).padStart(2,'0')+' —';
  rangeBar();
  const num=$('.summary-number');if(num)whenSeen(num,()=>countUp(num));
  for(const s of document.querySelectorAll('#research-metrics strong'))whenSeen(s,()=>countUp(s,1100));
  const rb=$('.range-bar');if(rb)whenSeen(rb,()=>rb.classList.add('in'));
  reveal([$('#quick-summary')]);
  reveal(answer.querySelectorAll(':scope>h2,:scope>.layer,:scope>.table-wrap,:scope>.advanced,:scope>.probability-card,:scope>.conclusion,:scope>h3'),.05);
 }
 new MutationObserver(()=>{if(!pending)pending=requestAnimationFrame(enhance)}).observe($('#answer'),{childList:true});
 // Opening a disclosure gently brings its contents in.
 document.addEventListener('toggle',e=>{const d=e.target;if(reduce||d.tagName!=='DETAILS'||!d.open)return;d.classList.add('animating');clearTimeout(d._anim);d._anim=setTimeout(()=>d.classList.remove('animating'),700)},true);
 // Keep the hero source count honest: it mirrors the observatory list.
 new MutationObserver(()=>{const c=document.querySelectorAll('#sources .source').length,n=$('#source-count');if(c&&n)n.textContent=c}).observe($('#sources'),{childList:true});
})();

// Round 2: live analysis console, reactive hero, data bars, citation cards, disclosure motion.
(()=>{
 const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches,fine=matchMedia('(pointer:fine)').matches;
 const energy=d=>document.dispatchEvent(new CustomEvent('oracle:energy',{detail:d}));
 const baseTitle=document.title;
 // ---- Reactive hero: the field listens while you type or browse examples.
 const q=$('#question');let lastLen=0;
 q.addEventListener('input',()=>{energy({pulse:Math.min(1,.35+Math.abs(q.value.length-lastLen)*.08)});lastLen=q.value.length});
 q.addEventListener('focus',()=>energy({pulse:.4}));
 for(const b of document.querySelectorAll('[data-q]'))b.addEventListener('pointerenter',()=>energy({pulse:.5}));
 $('#ask').addEventListener('submit',()=>{if(q.value.trim().length>=3)energy({pulse:1})});
 // Keyboard: "/" focuses the question, ⌘/Ctrl+Enter submits.
 addEventListener('keydown',e=>{
  if(e.key==='/'&&!e.metaKey&&!e.ctrlKey&&!/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName||'')&&!document.activeElement?.isContentEditable){e.preventDefault();q.focus({preventScroll:true});q.scrollIntoView({block:'center',behavior:reduce?'auto':'smooth'})}
 });
 q.addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey)&&!$('#submit').disabled){e.preventDefault();$('#ask').requestSubmit()}});
 // ---- Text decode for mono eyebrows (Latin only; Chinese stays still).
 const glyphs='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/—·';
 function decode(node,dur=900){
  if(reduce||!node||node.dataset.decoded)return;node.dataset.decoded='1';
  const targets=[...node.childNodes].filter(n=>n.nodeType===3&&/[A-Z]/.test(n.textContent));
  for(const t of targets){const final=t.textContent,start=performance.now();(function tick(now){const k=Math.min(1,(now-start)/dur);let out='';for(let i=0;i<final.length;i++){const c=final[i];out+=(c===' '||i<final.length*k)?c:glyphs[(Math.random()*glyphs.length)|0]}t.textContent=out;if(k<1)requestAnimationFrame(tick);else t.textContent=final})(start)}
 }
 setTimeout(()=>decode($('.intro .eyebrow')),150);
 // ---- Live analysis console, driven by the same job object as the timeline.
 const titles=['理解問題與規劃訊號','拉取市場數據','計算統計與異常檢查','分析核心訊號','生成一眼結論（草稿）','宏觀背景與核對','完成'];
 let lastJob=null,watched=false,board=null,boardJob=null,clock=0,startedAt=0,scrolledFor=null;
 function fmt(sec){sec=Math.max(0,Math.floor(sec));const m=Math.floor(sec/60),s=sec%60;return String(m).padStart(2,'0')+':'+String(s).padStart(2,'0')}
 function requestStop(btn,label){
  if(!current||btn.disabled)return;
  if(!btn.classList.contains('armed')){btn.classList.add('armed');btn.textContent='確定停止？';clearTimeout(btn._arm);btn._arm=setTimeout(()=>{btn.classList.remove('armed');btn.textContent=label},4000);return}
  clearTimeout(btn._arm);board?.querySelectorAll('.live-stop,.alert-stop').forEach(b=>{b.disabled=true;b.classList.remove('armed');b.textContent='停止中…'});
  api('/api/cancel',{id:current}).catch(e=>{
   board?.querySelectorAll('.live-stop,.alert-stop').forEach(b=>{b.disabled=false;b.classList.remove('armed');b.textContent='停止分析'});
   // Show the reason right beside the button, not at the top of the page.
   const msg=/not found|unexpected token|not valid json/i.test(e.message)?'停止失敗：server 仍是舊版本，未有停止功能。請關閉 server 的 Terminal 視窗（或按 Ctrl+C）再重新開啟。':'停止失敗：'+e.message;
   let note=board?.querySelector('.stop-note');if(board&&!note){note=el('p','','stop-note');board.querySelector('.live-timer').append(note)}if(note)note.textContent=msg;
  });
 }
 // Waiting notice: shown when a Codex call passes half its limit (at least 60 s).
 let dismissed='';
 function waitingNotice(job){
  let box=board.querySelector('.live-alert');
  if(!box){box=el('div',undefined,'live-alert');box.setAttribute('role','status');box.hidden=true;
   const text=el('p','','alert-text'),acts=el('div',undefined,'alert-actions'),wait=el('button','繼續等','alert-wait'),stopB=el('button','停止分析','alert-stop');
   wait.type=stopB.type='button';wait.onclick=()=>{dismissed=box.dataset.key;box.hidden=true};stopB.onclick=()=>requestStop(stopB,'停止分析');
   acts.append(wait,stopB);box.append(el('strong','Codex 回覆比平時慢'),text,acts);board.querySelector('.live-now').after(box)}
  const calls=Object.values(job.models_active||{}).map(c=>({...c,waited:(Date.now()-Date.parse(c.started_at))/1000})).filter(c=>isFinite(c.waited)&&c.timeout_seconds);
  const worst=calls.sort((a,b)=>b.waited/b.timeout_seconds-a.waited/a.timeout_seconds)[0];
  let retry=board.querySelector('.live-retry');
  if(job.planning_retry){if(!retry){retry=el('p','','live-retry');board.querySelector('.live-now').after(retry)}retry.textContent=(job.pipeline||[]).some(p=>p.index===2)?'第一次規劃未成功，已自動重試並成功。':'第一次規劃未成功（Codex 冇及時回覆），正在自動重試第 2 次…'}else retry?.remove();
  if(!worst||worst.waited<Math.max(60,worst.timeout_seconds*.5)||dismissed===worst.started_at){box.hidden=true;return}
  box.dataset.key=worst.started_at;box.hidden=false;
  const planning=/規劃/.test(worst.phase),limit=Math.round(worst.timeout_seconds/60);
  box.querySelector('.alert-text').textContent=`「${worst.phase}」已等咗 ${fmt(worst.waited)}，仍未收到 Codex 回覆（呢步上限約 ${limit} 分鐘，逾時會${planning&&!job.planning_retry?'自動重試一次':'停止並保存已取得的數據'}）。可能係用量接近上限或者伺服器繁忙。你可以繼續等，或者先停止，稍後再試。`;
 }
 function buildBoard(){
  board=el('section',undefined,'live-board');board.setAttribute('aria-label','分析進行中');
  const head=el('div',undefined,'live-head'),left=el('div');
  const tag=el('p',undefined,'eyebrow live-tag');tag.append(el('span',undefined,'live-dot'),document.createTextNode('LIVE ANALYSIS'));
  left.append(tag,el('p','','live-question'));
  const timer=el('div',undefined,'live-timer');timer.append(el('strong','00:00'),el('span','已用時間'));
  // Stop: first press arms, second press stops (no browser dialogs).
  const stop=el('button','停止分析','live-stop');stop.type='button';stop.setAttribute('aria-live','polite');
  stop.onclick=()=>requestStop(stop,'停止分析');
  timer.append(stop);
  head.append(left,timer);
  const steps=el('div',undefined,'live-steps');for(let i=0;i<7;i++){const seg=el('span');seg.dataset.state='waiting';steps.append(seg)}
  const now=el('div',undefined,'live-now');now.append(el('span','','live-step-no'),el('strong','','live-step-name'),el('span','','live-count'));
  const grid=el('div',undefined,'live-grid');
  const note=el('p','複雜分析一般需時 10–20 分鐘。你可以離開或重新整理此頁，返來會自動接續顯示進度。','live-note');
  board.append(head,steps,now,grid,note);
  (document.querySelector('#timeline')||$('.analysis-layout')).before(board);
 }
 function updateBoard(job){
  const running=job.status==='running';
  if(!running){if(board){board.classList.add('leaving');const b=board;setTimeout(()=>b.remove(),reduce?0:600);board=null}clearInterval(clock);clock=0;energy({base:0});if(!watched)return;watched=false;document.title=job.status==='done'?'✓ 分析完成 · '+baseTitle:job.status==='error'?'! 分析中斷 · '+baseTitle:baseTitle;if(job.status==='done')setTimeout(()=>{if(document.title.startsWith('✓'))document.title=baseTitle},8000);return}
  if(!board)buildBoard();watched=true;
  energy({base:.45});
  if(boardJob!==job.id){boardJob=job.id;board.querySelector('.live-grid').replaceChildren()}
  startedAt=Date.parse(job.resume_started_at||job.created_at)||Date.now();
  board.querySelector('.live-question').textContent=job.question||'';
  const pipe=job.pipeline||[],cur=pipe.filter(x=>x.status==='running').at(-1)||pipe.at(-1),idx=cur?.index||1;
  board.querySelectorAll('.live-steps span').forEach((seg,i)=>{const st=pipe.find(x=>x.index===i+1)?.status||'waiting';seg.dataset.state=st;seg.title=titles[i]});
  board.querySelector('.live-step-no').textContent=String(idx).padStart(2,'0')+' / 07';
  const name=board.querySelector('.live-step-name'),label=titles[idx-1]||job.stage||'';if(name.textContent!==label){name.textContent=label;if(!reduce){name.classList.remove('swap');void name.offsetWidth;name.classList.add('swap')}}
  // Signal board: one cell per planned signal, lit by its real fetch status.
  const grid=board.querySelector('.live-grid'),states=new Map((job.sources||[]).map(s=>[s.id,s])),signals=job.plan?.signals||[];
  for(const [i,sig] of signals.entries()){
   let cell=grid.querySelector(`[data-id="${CSS.escape(sig.id)}"]`);
   if(!cell){cell=el('div',undefined,'live-cell');cell.dataset.id=sig.id;cell.append(el('i'),el('span',sig.label),el('small',sig.layer||''));if(!reduce)cell.style.animationDelay=Math.min(i*30,600)+'ms';grid.append(cell)}
   const st=states.get(sig.id),s=st?.status||'pending';if(cell.dataset.state!==s){cell.dataset.state=s;cell.title=sig.label+(st?.error?'：'+st.error:'')}
  }
  const ok=(job.sources||[]).filter(s=>s.status==='ok').length,bad=(job.sources||[]).filter(s=>s.status==='error').length;
  board.querySelector('.live-count').textContent=signals.length?`${ok} / ${signals.length} 已取得`+(bad?` · ${bad} 失敗`:''):'';
  document.title='('+idx+'/7) '+label+' · 數字先知';
  lastJob=job;waitingNotice(job);
  if(!clock){const t=board.querySelector('.live-timer strong');const tick=()=>{t.textContent=fmt((Date.now()-startedAt)/1000);if(board&&lastJob)waitingNotice(lastJob)};tick();clock=setInterval(tick,1000)}
  if(scrolledFor!==job.id){scrolledFor=job.id;const r=board.getBoundingClientRect();if(r.top>innerHeight*.6||r.bottom<0)board.scrollIntoView({block:'start',behavior:reduce?'auto':'smooth'})}
 }
 // Whenever the app leaves the busy state (done, failed or stopped), close the console,
 // even if no data arrived and the timeline was never re-rendered.
 new MutationObserver(()=>{if(board&&!$('#submit').disabled)updateBoard({status:'stopped'})}).observe($('#submit'),{attributes:true,attributeFilter:['disabled']});
 const originalTimeline=renderTimeline;
 renderTimeline=function(job){originalTimeline(job);try{updateBoard(job)}catch(e){console.warn(e)}};
 // ---- Data bars inside tables: correlations and probabilities become visible magnitudes.
 function bars(){
  for(const t of document.querySelectorAll('#answer table')){
   const heads=[...t.querySelectorAll('thead th')].map(th=>th.textContent);
   heads.forEach((h,col)=>{
    const corr=/相關/.test(h),prob=/概率|機率/.test(h);if(!corr&&!prob)return;
    for(const tr of t.querySelectorAll('tbody tr')){const td=tr.children[col];if(!td||td.dataset.bar)continue;const v=parseFloat(td.textContent.replace('−','-'));if(!isFinite(v))continue;
     const mag=corr?Math.min(1,Math.abs(v)):Math.min(1,Math.max(0,v/100));if(corr&&Math.abs(v)>1)continue;
     td.dataset.bar=corr&&v<0?'neg':'pos';td.style.setProperty('--v',mag.toFixed(3));td.classList.add('has-bar')}
   })
  }
 }
 // ---- Citation hover card with the source's provenance.
 const card=el('div',undefined,'cite-card');card.setAttribute('role','tooltip');card.id='cite-card';card.hidden=true;document.body.append(card);let hideT=0;
 function showCard(a){
  const id=a.hash.replace('#evidence-',''),s=(last?.sources||[]).find(x=>x.id===id);if(!s)return;clearTimeout(hideT);
  card.replaceChildren();const top=el('div',undefined,'cite-top');top.append(el('span','['+s.id+']','cite-id'),badge(s.status));
  card.append(top,el('strong',s.name));
  const meta=[];if(s.quality?.observation_date)meta.push('觀察日期 '+s.quality.observation_date);if(s.checked_at)meta.push('抓取 '+time(s.checked_at));if(s.error)meta.push(s.error);
  card.append(el('p',meta.join(' · ')||'未提供日期'),el('small','點擊查閱完整證據 ↓'));
  card.hidden=false;a.setAttribute('aria-describedby','cite-card');
  const r=a.getBoundingClientRect(),cw=Math.min(320,innerWidth-24);card.style.width=cw+'px';
  let x=Math.min(Math.max(12,r.left+r.width/2-cw/2),innerWidth-cw-12),y=r.top-card.offsetHeight-10;if(y<70)y=r.bottom+10;
  card.style.left=x+'px';card.style.top=y+'px';card.classList.remove('show');void card.offsetWidth;card.classList.add('show')
 }
 function hideCard(){hideT=setTimeout(()=>{card.hidden=true;card.classList.remove('show')},120)}
 if(fine){document.addEventListener('pointerover',e=>{const a=e.target.closest?.('a.citation');if(a)showCard(a)});document.addEventListener('pointerout',e=>{if(e.target.closest?.('a.citation'))hideCard()})}
 document.addEventListener('focusin',e=>{if(e.target.matches?.('a.citation'))showCard(e.target)});document.addEventListener('focusout',e=>{if(e.target.matches?.('a.citation'))hideCard()});
 addEventListener('scroll',()=>{if(!card.hidden){card.hidden=true}},{passive:true});
 // ---- Smooth height for disclosures the reader opens by hand.
 const animated='.layer,.advanced,.revision-history,.footer-tools>details,.question-details,.evidence';
 document.addEventListener('click',e=>{
  const summary=e.target.closest?.('summary');if(!summary||reduce)return;const d=summary.parentElement;if(!d?.matches?.(animated)||d._busy)return;
  e.preventDefault();d._busy=true;const from=d.offsetHeight;
  if(d.open){const to=summary.offsetHeight+parseFloat(getComputedStyle(d).borderTopWidth)*2;d.style.overflow='hidden';const a=d.animate({height:[from+'px',to+'px']},{duration:420,easing:'cubic-bezier(.16,1,.3,1)'});a.onfinish=()=>{d.open=false;d.style.overflow='';d._busy=false}}
  else{d.open=true;const to=d.offsetHeight;d.style.overflow='hidden';const a=d.animate({height:[from+'px',to+'px']},{duration:Math.min(700,380+to/12),easing:'cubic-bezier(.16,1,.3,1)'});a.onfinish=()=>{d.style.overflow='';d._busy=false}}
 });
 // ---- Report arrival: decode the eyebrow, draw data bars.
 let p2=0;new MutationObserver(()=>{if(!p2)p2=requestAnimationFrame(()=>{p2=0;bars();const eb=$('.result-head .eyebrow');if(eb){delete eb.dataset.decoded;window.oracleWhenSeen(eb,()=>decode(eb,700))}for(const t of document.querySelectorAll('#answer table:not(.bars-armed)')){if(!t.querySelector('td.has-bar'))continue;t.classList.add('bars-armed');window.oracleWhenSeen(t,()=>t.classList.add('bars-in'))}})}).observe($('#answer'),{childList:true});
})();

// Round 3 (UAT fixes): report navigation, honest timeline states, resume notice, input validation.
(()=>{
 const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
 const title=$('#report-title');title.tabIndex=-1;
 function goToReport(){const r=$('#result');if(r.hidden)return;r.scrollIntoView({block:'start',behavior:reduce?'auto':'smooth'});setTimeout(()=>title.focus({preventScroll:true}),reduce?0:500)}
 // 1. Opening a saved report takes the reader to it (it renders far above the history list).
 let jump=false;
 document.addEventListener('click',e=>{if(e.target.closest?.('.history-entry'))jump=true},true);
 new MutationObserver(()=>{if(jump){jump=false;requestAnimationFrame(goToReport)}}).observe(title,{childList:true,characterData:true,subtree:true});
 // 5. Shortcuts to the current report, shown only while one is loaded.
 const nav=$('#nav-report'),chip=$('#jump-report');
 function syncShortcuts(){const has=!$('#result').hidden&&!!last?.report;nav.hidden=!has;chip.hidden=!has;if(has)chip.querySelector('span').textContent=last.report.title||last.question||''}
 for(const a of [nav,chip])a.addEventListener('click',e=>{e.preventDefault();goToReport()});
 new MutationObserver(syncShortcuts).observe($('#result'),{attributes:true,attributeFilter:['hidden']});
 new MutationObserver(syncShortcuts).observe(title,{childList:true,characterData:true,subtree:true});
 // 2. Timeline: steps absent from a finished job were reused, not waiting; round the durations.
 const human=s=>{if(s==null||!isFinite(s))return '';if(s<1)return '<1 秒';s=Math.round(s);return s<60?s+' 秒':Math.floor(s/60)+' 分 '+(s%60)+' 秒'};
 const prevTimeline=renderTimeline;
 renderTimeline=function(job){prevTimeline(job);const root=$('#timeline');if(!root||!job.pipeline)return;const finished=job.status==='done'||job.status==='error';
  root.querySelectorAll('ol>li').forEach((li,i)=>{const step=job.pipeline.find(x=>x.index===i+1),state=li.querySelector('.timeline-state'),node=li.querySelector('.timeline-node');
   const first=job.pipeline.length?Math.min(...job.pipeline.map(p=>p.index)):0,reusable=job.resumed_from||(finished&&(job.source_job||job.status==='done'));
   if(!step&&reusable&&i+1<first){li.dataset.state='reused';node.textContent='↺';state.textContent='沿用先前數據'}
   else if(step?.status==='done'&&li.dataset.state==='done')state.textContent='完成 · '+human(step.seconds)})};
 // 4. Resume notice: say which analysis it continues, and that it uses Codex quota.
 const resume=$('#resume'),rq=$('#resume-question');
 new MutationObserver(()=>{rq.textContent=resume.title?'「'+resume.title+'」':'上一份分析'}).observe(resume,{attributes:true,attributeFilter:['title','hidden']});
 rq.textContent=resume.title?'「'+resume.title+'」':'上一份分析';
 // 6. Validation and errors are brought to the reader, next to what caused them.
 const q=$('#question'),err=$('#error'),ask=$('#ask');
 ask.addEventListener('submit',()=>{if(q.value.trim().length<3){q.setAttribute('aria-invalid','true');q.setAttribute('aria-describedby','question-help error');ask.classList.remove('shake');void ask.offsetWidth;ask.classList.add('shake');q.focus({preventScroll:true});requestAnimationFrame(()=>ask.scrollIntoView({block:'nearest',behavior:reduce?'auto':'smooth'}))}});
 q.addEventListener('input',()=>{if(q.getAttribute('aria-invalid')&&q.value.trim().length>=3){q.removeAttribute('aria-invalid');q.setAttribute('aria-describedby','question-help');err.hidden=true}});
 new MutationObserver(()=>{if(!err.hidden){const r=err.getBoundingClientRect();if(r.top<70||r.bottom>innerHeight)err.scrollIntoView({block:'center',behavior:reduce?'auto':'smooth'})}}).observe(err,{attributes:true,attributeFilter:['hidden']});
 // 10. Empty table cells say so instead of looking broken.
 function fillEmpty(){for(const td of document.querySelectorAll('#answer td')){if(!td.textContent.trim()&&!td.children.length){td.textContent='—';td.classList.add('empty-cell');td.title='此欄沒有提供內容'}}}
 let p3=0;new MutationObserver(()=>{if(!p3)p3=requestAnimationFrame(()=>{p3=0;fillEmpty();syncShortcuts();const n=$('.summary-number');if(n){const t=n.textContent.trim(),isNum=/^[-+]?\d[\d,.]*\s*[^\s\d]{0,8}$/.test(t);n.classList.toggle('is-text',!isNum);n.classList.toggle('is-long',!isNum&&t.length>14)}const pv=$('.probability-value');if(pv){const t=[...pv.childNodes].filter(x=>x.nodeType===3).map(x=>x.textContent).join('').trim();pv.classList.toggle('is-long',t.length>14&&!/^[-+]?\d[\d,.]*\s*[^\s\d]{0,8}$/.test(t))}})}).observe($('#answer'),{childList:true});
 fillEmpty();syncShortcuts();
})();
// Topic filters: show a focused set of example questions; "熱門" by default.
(()=>{
 const filters=[...document.querySelectorAll('.topic-filters [data-filter]')],chips=[...document.querySelectorAll('.suggestions [data-q]')];if(!filters.length)return;
 const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
 function apply(key,animate){let i=0;for(const c of chips){const show=key==='all'||(key==='hot'?c.hasAttribute('data-hot'):c.dataset.cat===key);const was=!c.hidden;c.hidden=!show;if(show&&animate&&!reduce){c.classList.remove('enter');c.style.animationDelay=(i*35)+'ms';void c.offsetWidth;c.classList.add('enter')}if(show){i++;const n=c.querySelector('span');if(n)n.textContent=String(i).padStart(2,'0')}}for(const f of filters)f.setAttribute('aria-pressed',String(f.dataset.filter===key))}
 for(const f of filters)f.addEventListener('click',()=>apply(f.dataset.filter,true));
 apply('hot',false);
})();
// Hero rebuild: search-style input, IME-safe Enter, auto-grow, POWERED BY from live source status.
(()=>{
 const q=$('#question'),form=$('#ask');
 // Enter sends, Shift+Enter adds a line. Never send while an IME is composing (Cantonese/Chinese input).
 q.addEventListener('keydown',e=>{if(e.key!=='Enter'||e.shiftKey||e.metaKey||e.ctrlKey||e.altKey)return;if(e.isComposing||e.keyCode===229)return;e.preventDefault();if(!$('#submit').disabled)form.requestSubmit()});
 // Grow with content (Safari has no field-sizing), up to a comfortable limit.
 const grow=()=>{q.style.height='auto';q.style.height=Math.min(q.scrollHeight,200)+'px';form.classList.toggle('multiline',q.scrollHeight>70)};
 q.addEventListener('input',grow);for(const b of document.querySelectorAll('[data-q]'))b.addEventListener('click',()=>requestAnimationFrame(grow));addEventListener('resize',grow);grow();
 // POWERED BY: one pill per data source, mirroring the observatory's latest check.
 const palette={'Polymarket':'#2f6bff','Kalshi':'#f0783c','US Treasury':'#2a4a9c','BIS':'#c23b4e','CFTC COT':'#3b6ea5','Yahoo Finance':'#7b2ff7','Yahoo Options':'#8f4cf5','Deribit':'#4fbf7a','Deribit Options':'#39a86a','CoinLore':'#e0a526','SEC EDGAR':'#23456e','World Bank':'#2fa4d9','Eastmoney':'#d8452f','CNN Fear & Greed':'#f2b53c','FRED 金融序列':'#3f7f8f','香港政府統計處':'#b8883d','香港差餉物業估價署':'#a07a3a','香港金管局':'#0f7c6b','港股通南向資金':'#c0392b','Web Search':'#5b6770'};
 const short={'Polymarket':'PM','Kalshi':'K','US Treasury':'T','BIS':'BIS','CFTC COT':'COT','Yahoo Finance':'Y','Yahoo Options':'OPT','Deribit':'D','Deribit Options':'DO','CoinLore':'CL','SEC EDGAR':'SEC','World Bank':'WB','Eastmoney':'EM','CNN Fear & Greed':'FG','FRED 金融序列':'FRED','香港政府統計處':'HK','香港差餉物業估價署':'RVD','香港金管局':'HKMA','港股通南向資金':'SB','Web Search':'W'};
 const list=$('#powered-list');
 function build(){const rows=[...document.querySelectorAll('#sources .source')];if(!rows.length)return;list.replaceChildren();
  rows.forEach((r,i)=>{const name=r.querySelector('.source-name')?.textContent||'',st=r.querySelector('.badge')?.className.replace('badge','').trim()||'unchecked';
   const pill=el('span',undefined,'source-pill');pill.dataset.state=st;pill.style.setProperty('--c',palette[name]||'#56625d');pill.style.animationDelay=(i*40)+'ms';
   const label={ok:'最近檢查正常',error:'最近一次取數失敗',lead:'只有線索',unchecked:'未檢查'}[st]||st;pill.title=name+' · '+label;
   pill.append(el('b',short[name]||name.slice(0,2).toUpperCase()),el('span',name.replace(' 金融序列','')));list.append(pill)})}
 new MutationObserver(build).observe($('#sources'),{childList:true});build();
})();
// Rich analysis steps: each step says what it is doing and shows what it has collected so far.
(()=>{
 const doing=['理解問題、界定事件與期限，規劃要取得的市場訊號','並行抓取價格、利率、持倉、期權及事件合約','計算回報、波動、相關性，並檢查異常訊號','逐層分析核心訊號：市場反映甚麼、有何限制','生成一眼結論草稿','補充宏觀背景，核對引用與數字，必要時修正','整理最終報告'];
 const kv=(k,v)=>{const d=el('div',undefined,'kv');d.append(el('dt',k),el('dd',v));return d};
 function card(){return el('dl',undefined,'step-card')}
 function content(i,job,state){
  const p=job.plan||{},srcs=job.sources||[],q=job.quantitative,rep=job.report||job.generated_report;
  if(state==='waiting')return null;
  if(i===1){if(!p.core_variable&&!p.horizon)return null;const c=card();if(p.core_variable)c.append(kv('核心變量',p.core_variable));if(p.horizon)c.append(kv('時間窗口',p.horizon));
   const cats=[...new Set((p.signals||[]).map(s=>s.layer).filter(Boolean))];if(cats.length)c.append(kv('分析層面',cats.join('、')));if(p.signals?.length)c.append(kv('規劃訊號',p.signals.length+' 個'));return c}
  if(i===2){const sigs=p.signals||[];if(!sigs.length)return null;const map=new Map(srcs.map(s=>[s.id,s]));const wrap=el('div',undefined,'step-chips');
   for(const s of sigs){const st=map.get(s.id)?.status||'pending',chip=el('span',undefined,'step-chip');chip.dataset.state=st;chip.dataset.id=s.id;chip.title=(s.reason||s.label)+(map.get(s.id)?.error?'\n'+map.get(s.id).error:'');chip.append(el('i',st==='ok'?'✓':st==='error'?'!':''),el('span',s.label));wrap.append(chip)}return wrap}
  if(i===3){if(!q&&!job.promotions)return null;const c=card();if(q){c.append(kv('價格序列',(q.price_series_count??'—')+' 條完整序列'));c.append(kv('共同日期比較',(q.pair_count??'—')+' 組'));const top=q.strongest_pairs?.[0];if(top)c.append(kv('最強相關',top.a+' × '+top.b+'：'+Number(top.return_correlation).toFixed(2)))}
   if(job.promotions?.length)c.append(kv('升級異常訊號',job.promotions.map(x=>x.name).join('、')));return c}
  if(i===4){const layers=rep?.layers;if(!layers?.length)return null;const c=card();c.append(kv('分析層次',layers.map((l,k)=>String(k+1).padStart(2,'0')+' '+l.title.replace(/^[一二三四五六七八九十]+[、．.：:]\s*/,'')).join('\n')));return c}
  if(i===5){if(!rep)return null;const c=card();const a=rep.answer||rep.probability||{};c.append(kv('草稿結論',rep.headline_summary||String(rep.conclusion||'').split(/(?<=[。！？])/)[0]));try{c.append(kv('初步答案',answerValue(rep)+(a.range?'（範圍 '+a.range.join('–')+answerUnit(rep)+'）':'')))}catch(e){}return c}
  if(i===6){const f=job.quality_audit?.qualitative_audit?.findings,rv=job.revisions?.length;if(f==null&&!rv)return null;const c=card();c.append(kv('核對結果',job.quality_audit?.passed===false?'有 '+(f?.length||0)+' 項核對意見':'核對通過'));if(rv)c.append(kv('修訂','已按核對意見修正 '+rv+' 次'));return c}
  if(i===7){if(job.status!=='done'||!job.report)return null;const c=card();c.append(kv('最終答案',answerValue(job.report)));return c}
  return null}
 function sig(node){return node?node.textContent+'|'+[...node.querySelectorAll('[data-state]')].map(x=>x.dataset.state).join(''):''}
 const prev=renderTimeline;
 renderTimeline=function(job){prev(job);const root=$('#timeline');if(!root||!job.pipeline)return;
  root.querySelectorAll('ol>li').forEach((li,k)=>{const i=k+1,state=li.dataset.state;let rich=li.querySelector('.step-rich');
   if(!rich){rich=el('div',undefined,'step-rich');rich.append(el('p','','step-doing'),el('div',undefined,'step-body'));li.append(rich)}
   rich.querySelector('.step-doing').textContent=state==='running'?doing[i-1]+'…':state==='waiting'?'':doing[i-1];
   const body=rich.querySelector('.step-body'),next=content(i,job,state);
   if(i===2&&next&&body.firstChild?.classList?.contains('step-chips')){for(const c of next.children){const old=body.firstChild.querySelector(`[data-id="${CSS.escape(c.dataset.id)}"]`);if(old&&old.dataset.state!==c.dataset.state){old.replaceWith(c);c.classList.add('flip')}else if(!old)body.firstChild.append(c)}return}
   if(sig(next)!==sig(body.firstChild))body.replaceChildren(...(next?[next]:[]))})};
})();
