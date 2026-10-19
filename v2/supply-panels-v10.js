(()=>{
let overrides={};
const safe=s=>String(s??'확인 필요').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const text=s=>typeof learnText==='function'?learnText(s):safe(s);
const counts={
STEX:{potential:'6,895만주',open:'확인 필요',locked:'6,895만주'},
YMAT:{potential:'가격연동',open:'0주 확인',locked:'52.5만주+'},
QTI:{potential:'약 2,530만주+',open:'확인 필요',locked:'약 2,530만주'},
BTTC:{potential:'0주 확정',open:'0주 확정',locked:'안건 결과 대기'},
DRMA:{potential:'688만주',open:'93.3만주+',locked:'최대 595만주'},
VEEA:{potential:'약 1억2,938만주',open:'ATM 약 3,458만주*',locked:'약 9,480만주'},
AMSS:{potential:'385.7만주+',open:'확인 필요',locked:'385.7만주+'},
TRUG:{potential:'RS후 약 76.9만주+',open:'확인 필요',locked:'약 76.9만주+'},
NIVF:{potential:'가격연동',open:'공모 발행분 확인 필요',locked:'전환수량 확인 필요'},
MGN:{potential:'0주 신규확정',open:'0주 신규확정',locked:'0주 신규확정'},
CDT:{potential:'22.5만주+전환분',open:'EFFECT 확인 필요',locked:'22.5만주+전환분'},
WSHP:{potential:'921만주',open:'921만주',locked:'117만주'}
};
function ladder(d){const a=d?.priceLadder;if(!Array.isArray(a)||!a.length)return'';return `<section class="card ladderCard supplyInjected"><h2>🪜 가격 사다리</h2><div class="ladderHint">💡 매물대 확정이 아니라 <b>행사·전환·취득·계약 조건을 비교하는 참고선</b>이야.</div><div class="ladder">${a.map(x=>`<div class="ladderStep ${safe(x.kind||'reference')}"><div class="ladderPrice"><b>${safe(x.price)}</b><span>${safe(x.distance)}</span></div><div class="ladderInfo"><strong>${text(x.label)}</strong><small>${text(x.note)}</small></div></div>`).join('')}</div></section>`}
function supply(d){const s=d?.supplyMap;if(!s)return'';const m=s.summary||{},items=s.items||[],c=counts[d.ticker]||{};return `<section class="card supplyCard supplyInjected"><div class="supplyHead"><h2>🧱 앞으로 나올 수 있는 주식</h2><b>${safe(m.risk||'⚠️ 미확정')}</b></div><div class="supplyHint">💡 <b>시장에 나올 수 있음</b>은 잠재 신주·재판매 물량, <b>지금 바로 팔 수 있음</b>은 현재 등록·효력·행사조건상 즉시 공급 가능한 물량, <b>묶여 있음</b>은 승인·가격·락업·전환조건이 남은 물량이야. 같은 주식은 중복 합산하지 않아.</div><div class="supplyStats"><div><span>시장에 나올 수 있음</span><b>${safe(c.potential||m.potential||'확인 필요')}</b></div><div><span>지금 바로 팔 수 있음</span><b>${safe(c.open||m.sellableNow||'확인 필요')}</b></div><div><span>묶여 있음</span><b>${safe(c.locked||m.locked||'확인 필요')}</b></div></div><div class="supplyItems">${items.map(x=>`<div class="supplyItem"><div><strong>${text(x.name)}</strong><b>${safe(x.shares)}</b></div><span>${safe(x.status)}</span><p>${text(x.note)}</p></div>`).join('')}</div><p class="muted" style="margin-top:10px">* 금액형 Shelf·ELOC·Convertible은 실제 발행가격이 정해지기 전 고정 주식수로 만들 수 없어 '가격연동/확인 필요'로 표시함. 임의 환산하지 않음.</p></section>`}
function inject(){const view=document.getElementById('view');if(!view)return;const ticker=(new URLSearchParams(location.search).get('ticker')||'').trim().toUpperCase();const d=overrides[ticker];if(!ticker||!d)return;d.ticker=ticker;const hero=[...view.querySelectorAll('h1')].find(x=>x.textContent.trim().toUpperCase()===ticker);if(!hero)return;view.querySelectorAll('.supplyInjected').forEach(x=>x.remove());const headings=[...view.querySelectorAll('section.card h2')];const old=headings.find(h=>(h.textContent.includes('희석')&&h.textContent.includes('공급'))||h.textContent.includes('앞으로 나올 수 있는 주식'))?.closest('section.card');const cash=headings.find(h=>h.textContent.includes('현금')&&h.textContent.includes('자금조달'))?.closest('section.card');const html=ladder(d)+supply(d);if(old)old.outerHTML=html;else if(cash)cash.insertAdjacentHTML('afterend',html);else return;view.dataset.supplyTicker=ticker}
fetch('./data/supply-overrides.json?v=20261019-12',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(`supply data ${r.status}`);return r.json()}).then(x=>{overrides=x||{};inject()}).catch(console.error);
setInterval(inject,300);
})();