(()=>{
const L={
AMSS:[['확인 필요','조건식','Series C / Streeterville 전환 조건','gate','고정 전환가가 확인되지 않아 임의 가격을 넣지 않음.'],['확인 필요','행사가','Common Warrants 3,856,688주','warrant','행사가 최신값 확인 필요.']],
BTTC:[['$1.00','Nasdaq 기준선','최소호가 기준','gate','자금조달 가격이 아니라 상장유지 참고선.'],['확인 필요','조건식','신규 고정 희석 가격','reference','현재 추적자료상 확정된 신규 고정 공급 가격 없음.']],
CDT:[['$3.00','추가 자금 조건','Astor 추가 $2M funding gate','gate','5일 가격이 $3 이상일 때 추가 자금 조건.'],['$0.9177','행사가','Astor Warrant 225,000주','warrant','워런트 행사가.'],['가격연동','전환가','Astor Convertible Note','convertible','$6.75M 전환금융은 실제 전환가에 따라 주식수가 달라짐.']],
DRMA:[['확인 필요','전환/행사','Series E · Series F · PFW','convertible','승인·등록·행사 상태와 가격을 함께 확인해야 함.'],['$1.00','Nasdaq 참고','최소호가 기준선','gate','희석 행사가가 아닌 상장유지 참고선.']],
MGN:[['$1.00','Nasdaq 참고','최소호가 기준선','gate','최근 1:30 RS 이후 상장유지 참고선.'],['확인 필요','신규 공급','현재 신규 고정 희석 가격 없음','reference','과거 공모가는 미래 공급 가격으로 재사용하지 않음.']],
NIVF:[['$0.07','공모 기준가','9/28 Best-Efforts Offering','offering','공모 기준 가격. 1:4 RS 전후 기준은 최종 서류와 함께 확인.'],['$0.00001','PFW 행사가','Pre-Funded Warrant','warrant','PFW 명목 행사가.'],['가격연동','전환가','Senior Convertible Note','convertible','$7.105M 노트는 전환가·잔액에 따라 실제 공급수량 변동.']],
QTI:[['확인 필요','행사가','Lynrock Warrants 25,313,508주','warrant','최신 행사가 확인 필요.'],['확인 필요','행사가','PIPE/PFW 8,246,588주','warrant','실제 행사·등록 상태와 함께 확인.'],['확인 필요','행사가','PubCo Warrants 7,882,807주','warrant','최신 행사가 확인 필요.']],
STEX:[['$1.00','Nasdaq 기준선','최소호가 compliance','gate','2027-04-05 초기 cure deadline. 희석 가격이 아니라 상장유지 기준선.'],['확인 필요','교환비율 1:1','Exchangeable Shares 68,952,618주','reference','가격 게이트가 아닌 1:1 교환 구조라 임의 가격을 넣지 않음.']],
TRUG:[['$1.00','Nasdaq 참고','최소호가 기준선','gate','상장유지 참고선.'],['가격연동','전환가','Series A 잔존분','convertible','1:10 RS 반영 후 실제 전환 조건 확인 필요.'],['확인 필요','M&A 조건','Polymath consideration securities','reference','취득·재판매 조건 확인 전 가격 확정 금지.']],
VEEA:[['$11.50','행사가','VEEAW Public Warrant','warrant','공개 워런트 행사가.'],['약 $4.16','가중평균','기타 Warrants 약 76.514M주','warrant','기존 분석의 가중평균 행사가 참고값. 개별 워런트 조건은 다를 수 있음.'],['$0.1259','계산 참고','ATM 수량 가정에 사용한 가격','reference','매도벽이나 확정 발행가가 아니라 ATM 잠재수량 계산에 사용한 가정값.'],['가격연동','전환가','Convertible Notes','convertible','실제 전환가에 따라 공급량 변동.']],
WSHP:[['확인 필요','조건선','Roth · Sidney · Garner 공급','reference','현재 저장된 분석에서 가격조건이 확정되지 않은 물량은 임의 가격을 넣지 않음.'],['확인 필요','조건부','WePoints 1,170,000주','gate','조건 충족 가격·시점 확인 필요.']],
YMAT:[['$2.50','핵심 조건선','Financing Gate','gate','확정 목표가가 아니라 자금조달 조건을 추적하는 가격선.'],['가격연동','ELOC','Hudson 최대 $35M','convertible','실제 draw 가격에 따라 발행주식수 변동.'],['가격연동','Shelf','F-3 최대 $150M','offering','등록한도이며 실제 발행가는 Prospectus Supplement 확인 필요.']]
};
const e=s=>String(s??'확인 필요').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
function ticker(){let h=document.querySelector('#view h1');return h?h.textContent.trim().toUpperCase():''}
function card(t){let a=L[t]||[];return `<section class="card ladderCard ladderV23"><h2>🪜 가격 사다리</h2><div class="ladderHint">💡 목표가가 아니라 <b>행사·전환·공모·계약·Nasdaq 조건 가격</b>을 비교하는 참고선. 확인 안 된 가격은 숫자를 만들지 않음.</div><div class="ladder">${a.map(x=>`<div class="ladderStep ${e(x[3])}"><div class="ladderPrice"><b>${e(x[0])}</b><span>${e(x[1])}</span></div><div class="ladderInfo"><strong>${e(x[2])}</strong><small>${e(x[4])}</small></div></div>`).join('')}</div></section>`}
function apply(){let v=document.querySelector('#view'),t=ticker();if(!v||!L[t])return;if(v.querySelector('.ladderV23'))return;let native=v.querySelector('.ladderCard');if(native){native.outerHTML=card(t);return;}let cards=[...v.querySelectorAll('section.card')],cash=cards.find(c=>{let h=c.querySelector('h2');return h&&h.textContent.includes('현금');});if(cash)cash.insertAdjacentHTML('afterend',card(t));}
function start(){apply();setInterval(apply,250);let v=document.querySelector('#view');if(v)new MutationObserver(()=>setTimeout(apply,0)).observe(v,{childList:true,subtree:true});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();