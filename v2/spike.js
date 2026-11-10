(()=>{const $=s=>document.querySelector(s);let horizon=5;
const style=`
#spikePanel{--spike-accent:#ef4358;--spike-muted:#8792a2}
.spikePage{display:grid;gap:14px}.spikeNotice{border:1px solid #755a1d;background:#211b10;color:#ffe5a3;padding:13px 15px;border-radius:14px;line-height:1.55;font-size:13px}
.spikeHero{border:1px solid var(--line);border-left:4px solid var(--spike-accent);background:linear-gradient(145deg,#171d2b,#101722);border-radius:17px;padding:18px}
.spikeHero h1{font-size:25px;margin:0 0 7px}.spikeMuted{color:var(--muted);font-size:13px;line-height:1.6}
.spikePeriods{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:14px 0}
.spikePeriod{border:1px solid var(--line);background:#172033;color:var(--muted);border-radius:13px;padding:11px 8px;text-align:center;font-weight:800}
.spikePeriod.active{background:#ef4358;color:white;border-color:#ef4358}
.spikeGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.spikeMetric{border:1px solid var(--line);background:#141f31;border-radius:13px;padding:14px}
.spikeMetric small{display:block;color:var(--muted);font-size:12px;margin-bottom:8px}
.spikeMetric strong{font-size:20px;display:block}.spikeMetric .pending{color:#ffd166;font-size:15px}
.spikeEmpty{border:1px dashed #45536a;background:#111a29;border-radius:16px;padding:24px 18px;text-align:center}
.spikeEmpty b{font-size:16px}.spikeEmpty p{color:var(--muted);font-size:13px;line-height:1.65;margin:9px auto 0;max-width:620px}
.spikeHow{border:1px solid var(--line);background:#111a29;border-radius:16px;padding:16px}
.spikeHow h2{font-size:16px;margin:0 0 10px}.spikeSteps{display:grid;gap:8px;color:var(--muted);font-size:13px;line-height:1.55}
.spikeTag{display:inline-block;border:1px solid #654e19;background:#292211;color:#ffdc8c;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:800}
@media(max-width:620px){.spikeHero{padding:15px}.spikeGrid{grid-template-columns:1fr 1fr}.spikeMetric{padding:12px}.spikeMetric strong{font-size:17px}}
`;
if(!document.querySelector('#spikeStyles')){let s=document.createElement('style');s.id='spikeStyles';s.textContent=style;document.head.appendChild(s)}
function render(){const view=$('#view');if(!view)return;document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('active',b.dataset.tab==='spike'));
history.replaceState(null,'','?tab=spike');
view.innerHTML=`<div id="spikePanel" class="spikePage">
<section class="spikeNotice"><b>급등 포착 탭 · 개발 중</b><br>기존 종목분석 탭은 그대로 유지됩니다. 이 탭은 기간별 급등 가능성, 진입가·목표가를 보여주도록 준비 중입니다.</section>
<section class="spikeHero"><div class="heroTop"><div><h1>🚀 급등 포착</h1><div class="spikeMuted">급등 가능성 후보와 진입·목표 가격을 기간별로 확인하는 별도 탭</div></div><span class="spikeTag">모델 연결 대기</span></div>
<div class="spikePeriods" role="tablist" aria-label="예측 기간">
<button class="spikePeriod ${horizon===1?'active':''}" data-horizon="1">1거래일</button><button class="spikePeriod ${horizon===5?'active':''}" data-horizon="5">5거래일</button><button class="spikePeriod ${horizon===10?'active':''}" data-horizon="10">10거래일</button></div>
<div class="spikeGrid"><div class="spikeMetric"><small>${horizon}거래일 급등 확률</small><strong class="pending">미산출</strong></div><div class="spikeMetric"><small>급등 후보</small><strong class="pending">모델 결과 대기</strong></div><div class="spikeMetric"><small>진입가</small><strong class="pending">가격 데이터 연결 전</strong></div><div class="spikeMetric"><small>목표가 · 상승여력</small><strong class="pending">예측값 미산출</strong></div></div></section>
<section class="spikeEmpty"><b>아직 표시할 급등 포착 결과가 없습니다</b><p>현재 저장소에 있는 구조점수는 급등 확률이 아니므로 확률·진입가·목표가로 바꿔 표시하지 않습니다. 검증된 예측 출력이 연결되면 이 화면에 종목별 결과와 출처 기준시각을 표시합니다.</p></section>
<section class="spikeHow"><h2>결과 카드에 표시될 항목</h2><div class="spikeSteps"><div>① 티커·회사명과 포착 시각, 분석 기준일</div><div>② 진입가 → 목표가, 예상 상승여력</div><div>③ 1·5·10거래일 급등 확률 및 예측 엔진별 순위</div><div>④ ATM·ELOC·워런트 등 희석/공급 위험 태그와 미확인 데이터</div></div></section></div>`;
view.querySelectorAll('[data-horizon]').forEach(b=>b.onclick=()=>{horizon=Number(b.dataset.horizon);render()});
}
function addTab(){const nav=$('#tabs');if(!nav)return;let b=nav.querySelector('[data-tab="spike"]');if(!b){b=document.createElement('button');b.dataset.tab='spike';b.textContent='🚀 급등';nav.appendChild(b);b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();render()})}if(new URLSearchParams(location.search).get('tab')==='spike'&&!b.classList.contains('active'))render()}
let nav=$('#tabs');if(nav)new MutationObserver(addTab).observe(nav,{childList:true});
addTab();setTimeout(addTab,350);window.openSpikeTab=render;
})();