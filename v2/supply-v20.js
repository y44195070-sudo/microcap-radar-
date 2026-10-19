(()=>{
const M={
STEX:['68,952,618주','확인 필요','68,952,618주 조건부','1:1 교환가능주 68,952,618주. 현재 보통주 Float와 단순 합산하지 않음.'],
YMAT:['525,000주 + 가격연동','확인 필요','525,000주 + 가격연동','Hudson 워런트 525,000주 + F-3 $150M + ELOC $35M. 금액형 통로는 실제 발행가 확정 전 고정 주식수로 환산하지 않음.'],
QTI:['약 41,442,903주+','행사·등록상태 확인 필요','약 41,442,903주+','Lynrock 25,313,508주 + PIPE/PFW 8,246,588주 + PubCo warrants 7,882,807주. S-8 등은 별도 확인.'],
BTTC:['0주 신규확정','0주 신규확정','11/16 안건 결과 대기','현재 추적자료상 고정 신규공급 수량 없음. O/S 14,996,962주는 기존 발행주식이므로 미래 희석에 재합산하지 않음.'],
DRMA:['6,880,824주','등록·행사상태 확인 필요','최대 6,880,824주 조건부','PIPE 933,064 + PFW 1,360,544 + Series E 2,293,608 + Series F 2,293,608. 즉시 매도 가능분은 등록·승인·행사 상태 확인 후 분리.'],
VEEA:['약 129,377,000주+','ATM 실제 판매량 확인 필요','약 94,802,000주+ 조건부','ATM 가정 34.575M + 전환 약 8.43M + 워런트 약 76.514M + 옵션/리저브 약 9.858M. ATM 34.575M은 $0.1259 가정치.'],
AMSS:['3,856,688주 + 가격연동','확인 필요','3,856,688주 + 가격연동','Common Warrants 3,856,688주 + Series C/Streeterville 가격연동 공급.'],
TRUG:['RS후 약 769,000주 + M&A 물량','확인 필요','약 769,000주 + M&A 물량','Series A 잔존 약 7.69M주는 1:10 RS 전 기준 → 단순조정 약 769K. 이미 전환된 2,688,750주는 중복 제외.'],
NIVF:['공모분 + 전환 가격연동','공모 발행분 확인 필요','전환수량 확인 필요','Senior Convertible Note $7,105,468.75는 전환가·잔액에 따라 수량 변동. 공모는 최종 발행/RS 반영 수량 확인 필요.'],
MGN:['0주 신규확정','0주 신규확정','0주 신규확정','2월 공모는 완료된 과거 희석이라 미래 공급에 중복 합산하지 않음.'],
CDT:['225,000주 + 가격연동','EFFECT·전환상태 확인 필요','225,000주 + 전환분','Astor warrant 225,000주 @ $0.9177 + $6.75M 전환금융. 전환분은 전환가·잔액 확정 전 고정수량 환산 금지.'],
WSHP:['9,210,000주','9,210,000주','1,170,000주','Roth 600만 + Sidney 신고/잔여 + Garner를 중복 제거해 분류. WePoints 117만은 조건부로 별도.']
};
const e=s=>String(s??'확인 필요').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
function ticker(){let h=document.querySelector('#view h1');return h?h.textContent.trim().toUpperCase():''}
function card(t){let x=M[t];return `<section class="card supplyCard supplyV20"><div class="supplyHead"><h2>🧱 앞으로 나올 수 있는 주식</h2><b>희석 구조</b></div><div class="supplyHint">💡 WSHP와 같은 기준으로 12종목 모두 표시. 같은 주식은 중복 합산하지 않음.</div><div class="supplyStats"><div><span>시장에 나올 수 있음</span><b>${e(x[0])}</b></div><div><span>지금 바로 팔 수 있음</span><b>${e(x[1])}</b></div><div><span>묶여 있음</span><b>${e(x[2])}</b></div></div><div class="supplyItems"><div class="supplyItem"><div><strong>계산 기준</strong></div><p>${e(x[3])}</p></div></div><p class="muted">※ 확인되지 않은 즉시매도 물량은 숫자를 만들어 넣지 않고 ‘확인 필요’로 표시.</p></section>`}
function apply(){let v=document.querySelector('#view'),t=ticker();if(!v||!M[t])return;if(v.querySelector('.supplyV20'))return;let cards=[...v.querySelectorAll('section.card')];let old=cards.find(c=>{let h=c.querySelector('h2');if(!h)return false;let s=h.textContent;return s.includes('앞으로 나올 수 있는 주식')||(s.includes('희석')&&s.includes('공급'));});if(old){old.outerHTML=card(t);return;}let cash=cards.find(c=>{let h=c.querySelector('h2');return h&&h.textContent.includes('현금');});if(cash)cash.insertAdjacentHTML('afterend',card(t));}
function start(){apply();setInterval(apply,200);let v=document.querySelector('#view');if(v)new MutationObserver(()=>setTimeout(apply,0)).observe(v,{childList:true,subtree:true});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();