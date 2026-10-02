/* Print the same report renderer as the web app, including collapsed analysis. */
const fs=require('fs');
const {chromium}=require(process.env.ORACLE_PLAYWRIGHT_MODULE);
(async()=>{
 const [input,output,port]=process.argv.slice(2),job=JSON.parse(fs.readFileSync(input,'utf8'));
 const origin='http://127.0.0.1:'+port;
 const browser=await chromium.launch({executablePath:process.env.ORACLE_CHROME,headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:900},reducedMotion:'reduce',bypassCSP:true});
  await page.route('**/*',async route=>{
   const u=new URL(route.request().url());
   if(u.origin!==origin)return route.abort();
   const mocks={'/api/status':{busy:false,sources:[]},'/api/history':[],'/api/last':{...job,answer:job.report.conclusion},'/api/recoverable':{}};
   if(u.pathname in mocks)return route.fulfill({json:mocks[u.pathname]});
   if(!['/','/app.js','/style.css'].includes(u.pathname))return route.abort();
   return route.continue();
  });
  await page.goto(origin,{waitUntil:'networkidle',timeout:20000});
  await page.waitForSelector('#quick-summary',{timeout:10000});
  await page.evaluate(job=>{
   clearTimeout(timer);render(job);
   const report=document.querySelector('#result');report.hidden=false;
   report.querySelectorAll('button,nav,.back-top').forEach(e=>e.remove());
   report.querySelectorAll('details').forEach(e=>e.open=true);
   report.querySelectorAll('.revision-history').forEach(e=>e.remove());
   report.querySelectorAll('details.advanced').forEach(e=>{if(e.querySelector('summary')?.textContent==='分析耗時')e.remove()});
   const allSources=new Map((job.sources||[]).map(s=>[s.id,s]));
   report.querySelectorAll('a').forEach(a=>{
    if(a.hash.startsWith('#evidence-')){const s=allSources.get(a.hash.slice(10));a.setAttribute('href',s?.url?.startsWith('https://')?s.url:'#pdf-sources')}
    else if(a.getAttribute('href')?.startsWith('#'))a.removeAttribute('href');
   });
   const append=document.createElement('section');append.id='pdf-sources';
   const h=document.createElement('h2');h.textContent='資料來源與觀察日期';append.append(h);
   for(const [i,s] of (job.sources||[]).entries()){
    const section=document.createElement('div');section.className='pdf-source';
    const name=document.createElement('h3');name.textContent=(i+1)+'. '+s.name+' · '+(s.status==='ok'?'已取得資料':s.status==='lead'?'只有線索':'取數失敗');section.append(name);
    const date=document.createElement('p');date.textContent='抓取時間：'+time(s.checked_at)+' HKT · 觀察日期：'+(s.quality?.observation_date||'見分層數據')+(s.error?' · '+s.error:'');section.append(date);
    const urls=[s.url,s.data?.url,...(Array.isArray(s.data)?s.data.map(x=>x?.url):[])].filter(u=>typeof u==='string'&&u.startsWith('https://'));
    for(const url of [...new Set(urls)]){const line=document.createElement('p'),a=document.createElement('a');a.href=url;a.textContent=url;line.append(a);section.append(line)}append.append(section);
   }
   const auditTitle=document.createElement('h2');auditTitle.textContent='核對狀態';append.append(auditTitle);const auditNote=document.createElement('p');auditNote.textContent=job.preview?'待核對草稿，結論仍可能更新。':job.quality_audit?.passed?'內容核對已完成。'+(job.revisions?.length?'報告已按核對意見修訂，本文呈示修訂後內容。':''):'內容核對尚未通過，請留意正文中的核對意見。';append.append(auditNote);
   const note=document.createElement('p');note.textContent='本報告記錄分析時點的資料與研究判斷，不代表即時行情或保證的未來結果。';append.append(note);
   document.body.replaceChildren(report,append);document.body.className='pdf-report';
   document.title=job.report.title;
  },job);
  await page.addStyleTag({path:__dirname+'/static/pdf.css'});
  await page.emulateMedia({media:'print'});await page.evaluate(()=>document.fonts.ready);
  await page.pdf({path:output,format:'A4',printBackground:true,margin:{top:'18mm',bottom:'18mm',left:'16mm',right:'16mm'},displayHeaderFooter:true,headerTemplate:'<div style="font-size:8px;width:100%;padding:0 16mm;color:#52645c">DIGITAL ORACLE · 數字先知研究報告</div>',footerTemplate:'<div style="font-size:8px;width:100%;padding:0 16mm;color:#52645c;text-align:right"><span class="pageNumber"></span> / <span class="totalPages"></span></div>'});
 }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
