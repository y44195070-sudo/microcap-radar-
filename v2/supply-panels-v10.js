(()=>{
let overrides={};
const safe=s=>String(s??'확인 필요').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const text=s=>typeof learnText==='function'?learnText(s):safe(s);
/* 숫자는 현재 V2에 저장된 SEC 분석 자료에서 고정 주식수로 확인 가능한 것만 표시.
   금액형 Shelf/ELOC/Convertible, 승인 전 안건, 실제 행사/등록 상태 미확인은 임의 환산하지 않는다. */
const counts={
STEX:{potential:'6,895만주',open:'확인 필요',locked:'6,895만주',note:'교환가능주 68,952,618주. 실제 Float와 동일하지 않으며 교환·락업 상태 확인 필요.'},
YMAT:{potential:'52.5만주 + 가격연동',open:'확인 필요',locked:'52.5만주+',note:'Hudson 워런트 525K는 수량 확인. F-3 $150M·ELOC $35M은 발행가격에 따라 주식수가 달라 별도.'},
QTI:{potential:'약 2,530만주+',open:'확인 필요',locked:'약 2,530만주',note:'Lynrock 관련 워런트 약 25.3M주. S-8/Baby Shelf는 최신 잔존량 재확인 필요.'},
BTTC:{potential:'0주 확정',open:'0주 확정',locked:'안건 결과 대기',note:'현재 추적자료에서 새로 확정된 고정 희석수량 없음. 11/16 주총 결과 후 재계산.'},
DRMA:{potential:'688만주',open:'229.4만주*',locked:'458.7만주*',note:'PIPE 933,064 + PFW 1,360,544 + Series E/F 각 2,293,608. *PFW/E/F의 실제 즉시매도 가능 여부는 등록·승인 상태에 따라 변동.'},
VEEA:{potential:'약 1억2,924만주+',open:'ATM 약 3,458만주*',locked:'약 9,466만주+',note:'ATM 가정 34.575M + 전환 약 8.43M + 워런트 약 76.514M + 옵션/리저브 약 9.858M. ATM 수량은 $0.1259 가정치.'},
AMSS:{potential:'385.7만주 + 가격연동',open:'확인 필요',locked:'385.7만주+',note:'Common Warrants 3,856,688주. Series C·Streeterville는 조건/가격에 따라 수량 변동.'},
TRUG:{potential:'RS후 약 76.9만주 + M&A',open:'확인 필요',locked:'약 76.9만주+',note:'Series A 잔존분은 RS 전 약 7.69M주 → 1:10 단순 조정 약 769K주. M&A 지급증권은 최종 수량 확인 필요.'},
NIVF:{potential:'공모 RS후 약 446.4만주 + 가격연동',open:'공모분 확인 필요',locked:'전환수량 확인 필요',note:'9/28 공모 17.857M주 기준을 1:4 RS 단순조정하면 약 4.464M주. Senior Convertible Note $7.105M은 전환가/잔액 확인 전 고정수량 환산 금지.'},
MGN:{potential:'0주 신규확정',open:'0주 신규확정',locked:'0주 신규확정',note:'2월 공모는 완료된 과거 희석이라 미래 공급에 중복 합산하지 않음.'},
CDT:{potential:'22.5만주 + 가격연동',open:'확인 필요',locked:'22.5만주 + 전환분',note:'Astor warrant 225,000주 수량 확인. $6.75M 전환금융은 전환가/잔액에 따라 수량 변동.'},
WSHP:{potential:'921만주',open:'921만주',locked:'117만주',note:'기존 V2 분석 기준. 중복 물량은 합산하지 않음.'}
};
function ladder(d){const a=d?.priceLadder;if(!Array.isArray(a)||!a.length)return'';return `<section class="card ladderCard supplyInjected"><h2>🪜 가격 사다리</h2><div class="ladderHint">💡 매물대 확정이 아니라 <b>행사·전환·취득·계약 조건을 비교하는 참고선</b>이야.</div><div class="ladder">${a.map(x=>`<div class="ladderStep ${safe(x.kind||'reference')}"><div class="ladderPrice"><b>${safe(x.price)}</b><span>${safe(x.distance)}</span></div><div class="ladderInfo"><strong>${text(x.label)}</strong><small>${text(x.note)}</small></div></div>`).join('')}</div></section>`}
function supply(d){const s=d?.supplyMap;if(!s)return'';const m=s.summary||{},items=s.items||[],c=counts[d.ticker]||{};return `<section class="card supplyCard supplyInjected"><div class="supplyHead"><h2>🧱 앞으로 나올 수 있는 주식</h2><b>${safe(m.risk||'⚠️ 미확정')}</b></div><div class="supplyHint">💡 <b>시장에 나올 수 있음</b>은 잠재 신주·재판매 물량, <b>지금 바로 팔 수 있음</b>은 현재 등록·효력·행사조건상 즉시 공급 가능한 물량, <b>묶여 있음</b>은 승인·가격·락업·전환조건이 남은 물량이야. 같은 주식은 중복 합산하지 않아.</div><div class="supplyStats"><div><span>시장에 나올 수 있음</span><b>${safe(c.potential||m.potential||'확인 필요')}</b></div><div><span>지금 바로 팔 수 있음</span><b>${safe(c.open||m.sellableNow||'확인 필요')}</b></div><div><span>묶여 있음</span><b>${safe(c.locked||m.locked||'확인 필요')}</b></div></div>${c.note?`<p class="muted" style="margin:10px 0">${text(c.note)}</p>`:''}<div class="supplyItems">${items.map(x=>`<div class="supplyItem"><div><strong>${text(x.name)}</strong><b>${safe(x.shares)}</b></div><span>${safe(x.status)}</span><p>${text(x.note)}</p></div>`).join('')}</div><p class="muted" style="margin-top:10px">* 금액형 Shelf·ELOC·Convertible은 실제 발행가격이 정해지기 전 고정 주식수로 만들 수 없어 '가격연동/확인 필요'로 표시함. 임의 환산하지 않음.</p></section>`}
function inject(){const view=document.getElementById('view');if(!view)return;const ticker=(new URLSearchParams(location.search).get('ticker')||'').trim().toUpperCase();const d=overrides[ticker];if(!ticker||!d)return;d.ticker=ticker;const hero=[...view.querySelectorAll('h1')].find(x=>x.textContent.trim().toUpperCase()===ticker);if(!hero)return;view.querySelectorAll('.supplyInjected').forEach(x=>x.remove());const headings=[...view.querySelectorAll('section.card h2')];const old=headings.find(h=>(h.textContent.includes('희석')&&h.textContent.includes('공급'))||h.textContent.includes('앞으로 나올 수 있는 주식'))?.closest('section.card');const cash=headings.find(h=>h.textContent.includes('현금')&&h.textContent.includes('자금조달'))?.closest('section.card');const html=ladder(d)+supply(d);if(old)old.outerHTML=html;else if(cash)cash.insertAdjacentHTML('afterend',html);else return;view.dataset.supplyTicker=ticker}
fetch('./data/supply-overrides.json?v=20261019-16',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(`supply data ${r.status}`);return r.json()}).then(x=>{overrides=x||{};inject()}).catch(console.error);
setInterval(inject,300);
})();