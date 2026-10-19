(()=>{
/* WSHP-style supply classification for every V2 ticker.
   Fixed share counts are separated from variable-price facilities so dollar facilities are never fabricated into shares. */
const MAP={
STEX:{p:'68,952,618주',o:'즉시매도 수량 확인 필요',l:'68,952,618주 조건부',note:'1:1 교환가능주. 현재 보통주 Float와 단순 합산 금지.'},
YMAT:{p:'525,000주 + 가격연동',o:'즉시매도 수량 확인 필요',l:'525,000주 + 가격연동',note:'Hudson 워런트 525K + F-3 $150M + ELOC $35M. 금액형 통로는 실제 발행가 확정 전 주식수 계산 금지.'},
QTI:{p:'약 41,442,903주+',o:'PFW 등 행사상태 확인 필요',l:'약 41,442,903주+',note:'6/30 기준 Lynrock 25,313,508 + PIPE/PFW 8,246,588 + PubCo warrants 7,882,807. S-8 등 별도 등록분은 +α.'},
BTTC:{p:'0주 신규확정',o:'0주 신규확정',l:'11/16 안건 결과 대기',note:'현재 추적자료상 고정 신규공급 수량 없음. O/S 14,996,962주는 기존 발행주식이라 잠재 희석에 재합산하지 않음.'},
DRMA:{p:'6,880,824주',o:'2,293,608주*',l:'4,587,216주*',note:'PIPE 933,064 + PFW 1,360,544 + Series E 2,293,608 + Series F 2,293,608. *등록·주주승인·행사상태에 따라 open/locked 변동.'},
VEEA:{p:'약 129,377,000주+',o:'ATM 약 34,575,059주*',l:'약 94,802,000주+',note:'ATM 가정 34.575M + 전환 약 8.43M + 워런트 약 76.514M + 옵션/리저브 약 9.858M. *ATM은 $0.1259 가정치라 실제 판매량과 다를 수 있음.'},
AMSS:{p:'3,856,688주 + 가격연동',o:'즉시매도 수량 확인 필요',l:'3,856,688주 + 가격연동',note:'Common Warrants 3,856,688주 + Series C/Streeterville 가격연동 공급.'},
TRUG:{p:'RS후 약 769,000주 + M&A 물량',o:'즉시매도 수량 확인 필요',l:'약 769,000주 + M&A 물량',note:'Series A 잔존 약 7.69M주는 9/29 1:10 RS 전 기준 → 단순조정 약 769K. 이미 전환된 2,688,750주는 중복 제외.'},
NIVF:{p:'공모분 + 전환 가격연동',o:'공모 발행분 확인 필요',l:'전환수량 확인 필요',note:'Senior Convertible Note $7,105,468.75는 전환가·잔액에 따라 수량 변동. 공모는 최종 발행/RS 반영 수량 기준으로 확인.'},
MGN:{p:'0주 신규확정',o:'0주 신규확정',l:'0주 신규확정',note:'2월 공모는 완료된 과거 희석이라 미래 공급에 중복 합산하지 않음.'},
CDT:{p:'225,000주 + 가격연동',o:'EFFECT/전환상태 확인 필요',l:'225,000주 + 전환분',note:'Astor warrant 225K @ $0.9177 + $6.75M 전환금융. 전환분은 전환가·잔액 확정 전 주식수 임의환산 금지.'},
WSHP:{p:'9,210,000주',o:'9,210,000주',l:'1,170,000주',note:'Roth 600만 + Sidney 신고/잔여 + Garner를 중복 제거해 분류. WePoints 117만은 조건부로 별도.'}
};
let OV={};
const E=s=>String(s??'확인 필요').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function currentTicker(){const h=document.querySelector('#view h1');return h?h.textContent.trim().toUpperCase():''}
function detailItems(t){const items=OV[t]?.supplyMap?.items||[];return items.map(x=>`<div class="supplyItem"><div><strong>${E(x.name)}</strong><b>${E(x.shares)}</b></div><span>${E(x.status)}</span><p>${E(x.note)}</p></div>`).join('')}
function html(t){const m=MAP[t],risk=OV[t]?.supplyMap?.summary?.risk||'⚠️ 확인 필요';return `<section class="card supplyCard supplyV19" data-ticker="${E(t)}"><div class="supplyHead"><h2>🧱 앞으로 나올 수 있는 주식</h2><b>${E(risk)}</b></div><div class="supplyHint">💡 WSHP와 같은 기준으로 분류: <b>시장에 나올 수 있음</b> = 중복 제거한 잠재 공급, <b>지금 바로 팔 수 있음</b> = 현재 즉시 공급 가능분, <b>묶여 있음</b> = 승인·가격·락업·행사·전환 조건부 물량.</div><div class="supplyStats"><div><span>시장에 나올 수 있음</span><b>${E(m.p)}</b></div><div><span>지금 바로 팔 수 있음</span><b>${E(m.o)}</b></div><div><span>묶여 있음</span><b>${E(m.l)}</b></div></div><p class="muted" style="margin:10px 0"><b>계산 기준:</b> ${E(m.note)}</p><div class="supplyItems">${detailItems(t)}</div><p class="muted" style="margin-top:10px">※ 기존 O/S에 이미 반영된 발행주식은 미래 희석에 다시 더하지 않음. Shelf·ELOC·Convertible처럼 발행가격에 따라 수량이 바뀌는 통로는 숫자를 조작하지 않고 가격연동/확인 필요로 표시.</p></section>`}
function apply(){const v=document.querySelector('#view'),t=currentTicker();if(!v||!MAP[t]||!OV[t])return;if(v.querySelector(`.supplyV19[data-ticker="${t}"]`))return;const hs=[...v.querySelectorAll('section.card h2')];let target=hs.find(h=>h.textContent.includes('앞으로 나올 수 있는 주식'))?.closest('section.card')||hs.find(h=>h.textContent.includes('희석')&&h.textContent.includes('공급'))?.closest('section.card');if(target)target.outerHTML=html(t);else{const cash=hs.find(h=>h.textContent.includes('현금')&&h.textContent.includes('자금조달'))?.closest('section.card');if(cash)cash.insertAdjacentHTML('afterend',html(t))}}
fetch('./data/supply-overrides.json?v=20261019-19',{cache:'no-store'}).then(r=>r.json()).then(x=>{OV=x||{};apply();new MutationObserver(apply).observe(document.querySelector('#view'),{childList:true,subtree:true});setInterval(apply,250)}).catch(console.error);
})();