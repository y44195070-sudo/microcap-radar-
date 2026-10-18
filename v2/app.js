const $=s=>document.querySelector(s);let manifest=[],db={};const esc=s=>String(s??'확인 필요').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
async function boot(){try{manifest=await fetch('./data/manifest.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('manifest '+r.status);return r.json()});$('#status').textContent=`${manifest.length}종목 · V2`;tabs();let t=new URLSearchParams(location.search).get('ticker');if(t){$('#q').value=t.toUpperCase();openTicker(t)}}catch(e){$('#status').textContent='데이터 오류';$('#view').innerHTML=`<div class="card error">${esc(e.message)}</div>`}}
function tabs(){const groups=['⭐ 핵심 추적','👀 감시','🐷 저금통','🔎 발굴','🌙 종배','👥 도감','📚 복기'];$('#tabs').innerHTML=groups.map(x=>`<button>${x}</button>`).join('')}
async function openTicker(raw){let t=raw.trim().toUpperCase();if(!t)return;history.replaceState(null,'',`?ticker=${encodeURIComponent(t)}`);try{if(!db[t]){if(!manifest.includes(t))throw Error(`${t} 데이터가 없습니다.`);db[t]=await fetch(`./data/stocks/${encodeURIComponent(t)}.json`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(`${t} JSON ${r.status}`);return r.json()})}render(db[t])}catch(e){$('#view').innerHTML=`<div class="card error">${esc(e.message)}</div>`}}
function val(v){return esc(typeof v==='object'?JSON.stringify(v):v)}
function rows(o){if(!o||typeof o!=='object')return `<p>${esc(o)}</p>`;return Object.entries(o).map(([k,v])=>`<div class="row"><span class="key">${esc(k)}</span><strong>${val(v)}</strong></div>`).join('')}
function list(v){if(!v)return '<p class="muted">확인 필요</p>';if(!Array.isArray(v))return `<p>${esc(v)}</p>`;return `<div class="items">${v.map(x=>`<div class="item">${esc(typeof x==='object'?(x.text||x.title||x.summary||JSON.stringify(x)):x)}</div>`).join('')}</div>`}
function section(title,body,cls=''){return `<section class="card ${cls}"><h2>${title}</h2>${body}</section>`}
function factSummary(d){let facts=[];let s=d.structure||{};let sh=d.short||d.shortData||{};for(const k of ['실제 Float','O/S','최근 RS','거래량'])if(s[k])facts.push([k,s[k]]);for(const k of ['CTB','대차','Short Float','Reg SHO'])if(sh[k])facts.push([k,sh[k]]);return facts.length?`<div class="metricgrid">${facts.map(([k,v])=>`<div class="metric"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('')}</div>`:''}
function render(d){let sig=d.signal||{};let color=sig.color||'yellow';let conclusions=d.conclusion||d.conclusions;let objective=d.companyObjective;let awaited=d.awaitedFilings;let pattern=d.financingPattern;$('#view').innerHTML=`
<section class="card hero ${esc(color)}Border"><div class="heroTop"><div><h1>${esc(d.ticker)}</h1><div class="sub">${esc(d.company)} · 기준 ${esc(d.asOf)}</div></div><div class="score ${esc(color)}">${esc(d.score)}/100</div></div><div class="badges"><span>${esc(d.tier)}</span><span class="${esc(color)}">${esc(sig.text||sig)}</span></div><p class="lead">${esc(sig.summary||'')}</p></section>
${factSummary(d)}
${section('🏗️ 구조',rows(d.structure||d.capitalStructure))}
${section('💵 현금 · 자금조달',rows(d.cash||d.financials||d.financing))}
${section('🚨 희석 · 실제 공급 통로',list(d.dilution||d.supply),'danger')}
${conclusions?section('🧭 결론 · 사실/추정/시나리오',list(conclusions)):''}
${objective?section('🎯 회사가 필요한 것',typeof objective==='object'?rows(objective):list(objective)):''}
${section('🩳 공매 · 대차',rows(d.short||d.shortData))}
${section('📅 다가오는 일정',list(d.events||d.schedule),'schedule')}
${awaited?section('📨 기다리는 공시',list(awaited)):''}
${section('🔁 이전 분석 · 외부 의견 검증',list(d.externalValidation||d.validation||d.correctionToPost),'validation')}
${pattern?section('🏦 회사 조달 패턴',list(pattern)):''}
${section('⚠️ 가장 조심할 점',list(d.risks||d.risk),'danger')}
${section('🔍 다음 확인',list(d.nextChecks||d.checklist))}
${section('✍️ 토스 복붙 메모',`<p class="memo">${esc(d.memo)}</p>`,'memoCard')}`}
$('#go').onclick=()=>openTicker($('#q').value);$('#q').addEventListener('keydown',e=>{if(e.key==='Enter')openTicker(e.target.value)});boot();