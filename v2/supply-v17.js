(()=>{
const esc2=s=>String(s??'확인 필요').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const learn2=s=>typeof learnText==='function'?learnText(s):esc2(s);
const counts={
STEX:['6,895만주','확인 필요','6,895만주'],
YMAT:['52.5만주 + 가격연동','확인 필요','52.5만주+'],
QTI:['약 2,530만주+','확인 필요','약 2,530만주'],
BTTC:['0주 확정','0주 확정','안건 결과 대기'],
DRMA:['688만주','229.4만주*','458.7만주*'],
VEEA:['약 1억2,924만주+','ATM 약 3,458만주*','약 9,466만주+'],
AMSS:['385.7만주 + 가격연동','확인 필요','385.7만주+'],
TRUG:['RS후 약 76.9만주 + M&A','확인 필요','약 76.9만주+'],
NIVF:['공모 RS후 약 446.4만주 + 가격연동','공모분 확인 필요','전환수량 확인 필요'],
MGN:['0주 신규확정','0주 신규확정','0주 신규확정'],
CDT:['22.5만주 + 가격연동','확인 필요','22.5만주 + 전환분'],
WSHP:['921만주','921만주','117만주']
};
let ov={};
function apply(d){const x=ov[d?.ticker];if(!x)return d;if(!d.priceLadder&&x.priceLadder)d.priceLadder=x.priceLadder;if(!d.supplyMap&&x.supplyMap)d.supplyMap=x.supplyMap;return d}
// app.js의 기본 렌더러 자체를 교체한다. DOM을 나중에 덮는 방식이 아니라 render()가 처음부터 이 카드를 만든다.
window.supplySection=supplySection=function(d){d=apply(d);const s=d?.supplyMap;if(!s)return'';const m=s.summary||{},items=s.items||[],c=counts[d.ticker]||['확인 필요','확인 필요','확인 필요'];return `<section class="card supplyCard"><div class="supplyHead"><h2>🧱 앞으로 나올 수 있는 주식</h2><b>${esc2(m.risk||'⚠️ 미확정')}</b></div><div class="supplyHint">💡 <b>시장에 나올 수 있음</b>은 잠재 신주·재판매 물량, <b>지금 바로 팔 수 있음</b>은 현재 등록·효력·행사조건상 즉시 공급 가능한 물량, <b>묶여 있음</b>은 승인·가격·락업·전환조건이 남은 물량이야. 같은 주식은 중복 합산하지 않아.</div><div class="supplyStats"><div><span>시장에 나올 수 있음</span><b>${esc2(c[0])}</b></div><div><span>지금 바로 팔 수 있음</span><b>${esc2(c[1])}</b></div><div><span>묶여 있음</span><b>${esc2(c[2])}</b></div></div><div class="supplyItems">${items.map(x=>`<div class="supplyItem"><div><strong>${learn2(x.name)}</strong><b>${esc2(x.shares)}</b></div><span>${esc2(x.status)}</span><p>${learn2(x.note)}</p></div>`).join('')}</div><p class="muted" style="margin-top:10px">* 금액형 Shelf·ELOC·Convertible은 발행가격 확정 전 고정 주식수로 임의 환산하지 않음.</p></section>`};
const oldRender=render;
window.render=render=function(d){return oldRender(apply(d))};
fetch('./data/supply-overrides.json?v=20261019-17',{cache:'no-store'}).then(r=>r.json()).then(x=>{ov=x||{};const t=(new URLSearchParams(location.search).get('ticker')||'').toUpperCase();if(t&&db?.[t])render(db[t])}).catch(console.error);
})();