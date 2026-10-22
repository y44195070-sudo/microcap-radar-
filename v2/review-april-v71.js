(()=>{const april={
'💥 무뉴스/약한 PR + 저유통 Volume Shock':'AIXI · BBGI · UCAR · SNAL · BIRD · MYSE · AKAN',
'💣 급등 직후 공급/희석 붕괴 · Spike-and-Raise':'BIRD',
'🔁 멀티데이 지속·재점화형':'AIXI · BBGI · SNAL · PBM',
'🤝 M&A/역합병·인수 + 동시 자금조달/재평가':'KRSA/CYCN',
'🔥 RS 후 초저유통 압축형':'AKAN',
'📑 회사 체급 대비 대형 계약·주문형':'해당 사례 없음',
'🚧 공급 차단 + 수요 창출형':'해당 사례 없음',
'📅 사전 이벤트 2단 점화형':'PBM · LPCN ⚠️ 실패 대조군',
'👤 내부자 매수 + 상장유지/컴플라이언스형':'해당 사례 없음',
'📈 실적 질 개선형':'해당 사례 없음',
'🌊 동일 세션 저유통 클러스터형':'BIRD → MYSE(다음 세션 AI 피벗 확산)'};
function apply(){const root=document.querySelector('[data-pattern-master-v55]');if(!root)return;root.querySelectorAll('details.pattern').forEach(d=>{const s=d.querySelector('summary');if(!s)return;const key=Object.keys(april).find(k=>s.textContent.includes(k));if(!key)return;const items=d.querySelector('.items');if(!items||items.querySelector('[data-april-v71]'))return;const row=document.createElement('div');row.className='item';row.dataset.aprilV71='1';row.innerHTML=`<b>→ 4월</b>: ${esc(april[key])}`;items.prepend(row);});const p=root.querySelector('.muted');if(p&&!p.dataset.aprilV71){p.dataset.aprilV71='1';p.textContent=p.textContent.replace('5·6·7·8·9·10월','4·5·6·7·8·9·10월');}}
const old=window.openReview;if(typeof old==='function'){window.openReview=async function(...args){const r=await old.apply(this,args);apply();requestAnimationFrame(apply);setTimeout(apply,80);setTimeout(apply,180);return r;};}document.addEventListener('click',e=>{if(e.target.closest('#tabs button[data-tab="review"]'))setTimeout(apply,180);});})();