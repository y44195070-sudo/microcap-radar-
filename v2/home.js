(()=>{
const e=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
async function loadHome(){
  const p=new URLSearchParams(location.search); if(p.get('ticker')||p.get('tab')) return;
  try{const d=await fetch('./data/home.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('홈 데이터 '+r.status);return r.json()}); renderHome(d)}catch(err){document.querySelector('#view').innerHTML=`<div class="card error">${e(err.message)}</div>`}
}
function renderHome(d){
 const view=document.querySelector('#view');
 view.innerHTML=`
 <section class="homeSection anomalyPanel"><div class="homeTitle"><b>🚨 이상 감지</b><span>${e(d.asOf)} 업데이트</span></div><div class="anomalyHint">💡 거래량 급증·급락·희석 공시처럼 다시 확인할 신호를 모아둔 곳이에요.</div><div class="anomalyList">${(d.anomalies||[]).map(x=>`<div class="anomalyRow"><span class="aDate">${e(x.date)}</span><b>${e(x.ticker)}</b><span class="aBadge">${e(x.badge)}</span><span class="aText">${e(x.text)}</span></div>`).join('')}</div></section>
 <section class="homeSection"><div class="homeTitle"><b>⭐ 핵심 추적</b><span>${(d.core||[]).length}종목 · 매일 깊게 갱신</span></div><div class="coreGrid">${(d.core||[]).map(x=>`<button class="coreCard" data-ticker="${e(x.ticker)}"><div class="coreTop"><strong>${e(x.ticker)} <em>${e(x.score)}/100</em></strong><span>☆</span></div><div class="coreSignal">${e(x.signal)}</div><small>카드를 눌러 상세 분석 보기</small></button>`).join('')}</div><p class="homeNote">${e(d.note)}</p></section>`;
 view.querySelectorAll('.coreCard').forEach(b=>b.onclick=()=>location.href=`?ticker=${encodeURIComponent(b.dataset.ticker)}`);
 document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('active',b.dataset.tab==='core'));
}
window.addEventListener('load',()=>{
 loadHome();
 const tabs=document.querySelector('#tabs'); if(!tabs)return;
 tabs.addEventListener('click',ev=>{const b=ev.target.closest('button');if(!b)return;if(b.dataset.tab==='core'){ev.stopImmediatePropagation();history.replaceState(null,'',location.pathname);loadHome()}},true);
});
})();