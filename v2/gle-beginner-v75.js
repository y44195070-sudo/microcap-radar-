(()=>{
  if(typeof window.render!=='function') return;
  const originalRender=window.render;
  const e=s=>String(s??'확인 필요').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const get=(o,k,f='확인 필요')=>o&&o[k]!=null?o[k]:f;
  function addStyle(){if(document.getElementById('gleBeginnerStyle'))return;const s=document.createElement('style');s.id='gleBeginnerStyle';s.textContent=`
  .gleBeginner{display:grid;gap:14px;margin-bottom:16px}.gleBeginner .gbCard{border:1px solid var(--border,#2b3340);border-radius:16px;padding:16px;background:var(--card,#151a22)}
  .gbEyebrow{font-size:12px;opacity:.65;margin-bottom:5px}.gbTitle{font-size:22px;margin:0 0 7px}.gbLead{line-height:1.65;margin:0}.gbScoreRow{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:12px}.gbScore{font-size:24px;font-weight:800}.gbBadge{padding:6px 10px;border-radius:999px;background:rgba(245,184,65,.14);border:1px solid rgba(245,184,65,.35);font-size:13px}
  .gbGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.gbMini{border:1px solid var(--border,#2b3340);border-radius:12px;padding:12px;min-width:0}.gbMini span{display:block;font-size:12px;opacity:.7;margin-bottom:5px}.gbMini b{display:block;line-height:1.45}.gbMini small{display:block;opacity:.72;line-height:1.45;margin-top:5px}
  .gbGood{color:#57c785}.gbWarn{color:#f0b35a}.gbBad{color:#ef7777}.gbNeutral{opacity:.75}.gbQuestion{font-size:18px;margin:0 0 10px}.gbExplain{font-size:13px;line-height:1.55;opacity:.78;margin:10px 0 0}.gbRows{display:grid;gap:8px}.gbRow{display:grid;grid-template-columns:minmax(110px,.8fr) minmax(0,1.4fr);gap:10px;padding:10px 0;border-top:1px solid var(--border,#2b3340)}.gbRow:first-child{border-top:0}.gbRow span{font-size:13px;opacity:.72}.gbRow b{line-height:1.5}.gbTerm{font-size:12px;opacity:.62;font-weight:500}.gbList{margin:0;padding-left:20px}.gbList li{margin:8px 0;line-height:1.55}.gbSplit{display:grid;grid-template-columns:1fr 1fr;gap:12px}.gbSubhead{font-size:14px;margin:0 0 7px}.gbWatch{counter-reset:watch;display:grid;gap:8px}.gbWatchItem{display:grid;grid-template-columns:30px 1fr;gap:8px;align-items:start}.gbWatchItem:before{counter-increment:watch;content:counter(watch);display:grid;place-items:center;width:26px;height:26px;border-radius:50%;background:rgba(120,140,255,.14);font-weight:800}.gbWatchItem b{display:block;margin-bottom:3px}.gbWatchItem small{opacity:.72;line-height:1.45}.glePro{margin-top:14px}.glePro>summary{cursor:pointer;list-style:none;border:1px solid var(--border,#2b3340);border-radius:14px;padding:14px 16px;font-weight:800}.glePro>summary::-webkit-details-marker{display:none}.glePro>summary:after{content:' ▼';float:right;opacity:.6}.glePro[open]>summary:after{content:' ▲'}.gleProBody{display:grid;gap:14px;margin-top:14px}
  @media(max-width:620px){.gbGrid,.gbSplit{grid-template-columns:1fr}.gbRow{grid-template-columns:1fr;gap:3px}.gbTitle{font-size:20px}}
  `;document.head.appendChild(s)}
  function beginner(d){
    const st=d.structure||{},sh=d.short||{},sm=d.supplyMap||{},cash=d.cash||{},sp=d.scoreParts||{};
    const float=get(st,'실제 Float'); const ctb=get(sh,'CTB'); const borrow=get(sh,'Borrow'); const sf=get(sh,'Short Float'); const reg=get(sh,'Reg SHO');
    const events=Array.isArray(d.events)?d.events:[];
    const next=Array.isArray(d.nextChecks)?d.nextChecks:[];
    const good=['역분할 뒤 Class A 주식 수가 크게 줄어 수급이 붙을 때 가격 탄력이 커질 수 있어.','대차비용(CTB)이 높은 편이라 공매도 포지션 유지 부담이 작지 않아.'];
    const bad=['최대 $100M F-3 Shelf가 EFFECT 상태라 회사가 향후 증권을 발행할 통로가 열려 있어.','Short Float 자체는 높다고 보기 어려워 “강한 숏스퀴즈주”로 단정하면 안 돼.'];
    const supplyPotential=get(sm.summary,'potential','최대 $100M F-3 Shelf');
    const supplyNow=get(sm.summary,'sellableNow','최신 즉시 매도 물량 확인 필요');
    const supplyLocked=get(sm.summary,'locked','최신 제한조건 확인 필요');
    return `<div class="gleBeginner">
      <section class="gbCard"><div class="gbEyebrow">주린이용 요약 · 전문 데이터는 아래에 그대로 있어</div><h2 class="gbTitle">GLE · 현재 구조 한눈에 보기</h2><p class="gbLead">역분할로 거래 가능한 주식 수가 크게 줄어든 <b>저유통 압축 구조</b>야. 다만 회사 체급에 비해 큰 <b>$100M Shelf</b>가 살아 있어서, “주식이 적으니 무조건 간다”가 아니라 <b>새 주식 공급이 열리는지</b>를 같이 봐야 해.</p><div class="gbScoreRow"><span class="gbScore">${e(d.score)}/100</span><span class="gbBadge">🟡 관심 있게 보되 공급 주의</span></div></section>
      <section class="gbCard"><h3 class="gbQuestion">먼저 이것만 보면 돼</h3><div class="gbGrid">
        <div class="gbMini"><span>왜 보는 종목이야?</span><b>RS 뒤 초저유통 + 높은 대차비용</b><small>거래량이 붙으면 수급 탄력이 커질 수 있는 구조야.</small></div>
        <div class="gbMini"><span>가장 좋은 점</span><b class="gbGood">유통주식이 매우 적을 가능성</b><small>공식 Float 확정치는 아니라 계속 재확인이 필요해.</small></div>
        <div class="gbMini"><span>가장 위험한 점</span><b class="gbBad">$100M Shelf</b><small>급등할 때 신규 Offering/424B가 나오면 공급이 늘 수 있어.</small></div>
        <div class="gbMini"><span>강해지려면?</span><b>거래량 증가 + Borrow 감소 + 신규 확정 재료</b><small>셋이 겹칠수록 수급 구조가 더 흥미로워져.</small></div>
        <div class="gbMini"><span>지금 제일 먼저 확인</span><b class="gbWarn">신규 주식발행 공시</b><small>F-3 Supplement, 424B, Offering, ATM 여부를 우선 확인.</small></div>
        <div class="gbMini"><span>이 점수 뜻은?</span><b>구조의 질 61점</b><small>61% 상승확률이라는 뜻이 절대 아니야.</small></div>
      </div></section>
      <section class="gbCard"><h3 class="gbQuestion">📌 핵심 숫자, 그래서 무슨 뜻이야?</h3><div class="gbRows">
        <div class="gbRow"><span>실제로 거래되는 주식 수<br><span class="gbTerm">Float(플로트, 실제 유통주식)</span></span><b>${e(float)}<br><span class="gbGood">● 매우 적을 가능성</span></b></div>
        <div class="gbRow"><span>공매도 주식을 빌리는 비용<br><span class="gbTerm">CTB(코스트 투 보로우, 대차비용)</span></span><b>${e(ctb)}<br><span class="gbGood">● 높은 편</span></b></div>
        <div class="gbRow"><span>빌릴 수 있는 주식<br><span class="gbTerm">Borrow(보로우, 대차가능주식)</span></span><b>${e(borrow)}<br><span class="gbGood">● 많지 않은 편</span></b></div>
        <div class="gbRow"><span>유통주식 중 공매도 비율<br><span class="gbTerm">Short Float(숏 플로트)</span></span><b>${e(sf)}<br><span class="gbBad">● 낮은 편 · 숏스퀴즈 과장 금지</span></b></div>
        <div class="gbRow"><span>향후 증권 발행 등록 한도<br><span class="gbTerm">Shelf(셸프, 포괄 증권등록)</span></span><b>${e(supplyPotential)}<br><span class="gbBad">● 큰 공급통로 존재</span></b></div>
        <div class="gbRow"><span>최근 거래 상태</span><b>${e(get(st,'최근 가격'))}<br><span class="gbNeutral">● 거래량이 아직 매우 건조함</span></b></div>
      </div></section>
      <section class="gbCard"><h3 class="gbQuestion">💰 새 주식이 쏟아질 위험은?</h3><div class="gbRows">
        <div class="gbRow"><span>① 지금 바로 팔 수 있는 물량</span><b>${e(supplyNow)}</b></div>
        <div class="gbRow"><span>② 앞으로 나올 수 있는 물량</span><b>${e(supplyPotential)}</b></div>
        <div class="gbRow"><span>③ 현재 묶이거나 조건부인 물량</span><b>${e(supplyLocked)}</b></div>
      </div><p class="gbExplain"><b>왜 중요해?</b> 주가가 급등해도 회사나 기존 투자자의 새 주식이 대량으로 시장에 나오면 상승을 눌러버릴 수 있어. <b>등록돼 있다는 것과 오늘 당장 팔 수 있다는 것은 다른 말</b>이야.</p></section>
      <section class="gbCard"><h3 class="gbQuestion">🩳 공매도가 급등 연료가 될 수 있어?</h3><p class="gbLead"><b>일부 연료는 있지만, 강한 숏스퀴즈 구조로 단정하기는 어려워.</b> 빌리는 비용은 높지만 실제 Short Float는 낮은 편이야.</p><div class="gbGrid" style="margin-top:12px"><div class="gbMini"><span>Short Float</span><b>${e(sf)}</b><small>실제 공매도 잔고 비중은 높다고 보기 어려움.</small></div><div class="gbMini"><span>CTB</span><b>${e(ctb)}</b><small>주식을 빌려 공매도를 유지하는 비용은 높은 편.</small></div><div class="gbMini"><span>Borrow</span><b>${e(borrow)}</b><small>빌릴 주식이 더 줄어드는지 확인.</small></div><div class="gbMini"><span>Reg SHO</span><b>${e(reg)}</b><small>Threshold 등재 여부는 별도로 확인.</small></div></div></section>
      <section class="gbCard"><h3 class="gbQuestion">🔥 주가를 움직일 만한 재료는?</h3><ul class="gbList"><li><b>진행 중</b> · Angkasa-X Space-to-AI 협업 — 단순 MOU에서 전략협업계약으로 진전했지만 <b>확정 계약금액은 미공개</b>.</li><li><b>확인 이벤트</b> · Nasdaq 최소호가 compliance 결과 — 상장유지 문제 해결 여부 확인용이지, 그 자체를 상승 촉매로 단정하면 안 돼.</li><li><b>불확실</b> · PoC가 실제 유료 고객·매출 계약으로 전환되는지 아직 확인 필요.</li></ul></section>
      <section class="gbCard"><h3 class="gbQuestion">📊 GLE 구조점수 ${e(d.score)}/100</h3><div class="gbSplit"><div><h4 class="gbSubhead">좋은 부분</h4><ul class="gbList">${good.map(x=>`<li class="gbGood">${e(x)}</li>`).join('')}</ul></div><div><h4 class="gbSubhead">점수를 깎은 부분</h4><ul class="gbList">${bad.map(x=>`<li class="gbBad">${e(x)}</li>`).join('')}</ul></div></div><details style="margin-top:12px"><summary><b>점수 상세 보기</b></summary><div class="gbRows" style="margin-top:8px">${Object.entries(sp).map(([k,v])=>`<div class="gbRow"><span>${e(k)}</span><b>${e(v)}</b></div>`).join('')}</div></details><p class="gbExplain">※ 구조점수는 <b>주가 상승확률이 아니라 현재 구조의 질을 비교하기 위한 점수</b>야.</p></section>
      <section class="gbCard"><h3 class="gbQuestion">👀 그래서 지금 뭘 보면 돼?</h3><div class="gbWatch"><div class="gbWatchItem"><div><b>신규 424B / Offering / ATM</b><small>새 주식 공급이 실제로 열리는지 가장 먼저 확인.</small></div></div><div class="gbWatchItem"><div><b>거래량 급증</b><small>현재는 거래가 매우 말라 있어 실제 수급 점화 여부를 확인.</small></div></div><div class="gbWatchItem"><div><b>Borrow 감소 / CTB 상승</b><small>대차가 더 빡빡해지는지 확인.</small></div></div><div class="gbWatchItem"><div><b>새로운 확정 계약</b><small>MOU나 협업이 아니라 금액·매출이 붙는 계약인지 확인.</small></div></div><div class="gbWatchItem"><div><b>Nasdaq compliance 결과</b><small>RS 이후 상장유지 요건을 실제로 회복했는지 확인.</small></div></div></div></section>
    </div>`;
  }
  window.render=function(d){
    originalRender(d);
    if(!d||String(d.ticker||'').toUpperCase()!=='GLE') return;
    addStyle();
    const view=document.getElementById('view'); if(!view)return;
    const existing=[...view.children];
    const wrap=document.createElement('div');wrap.innerHTML=beginner(d);const beginnerNode=wrap.firstElementChild;
    const pro=document.createElement('details');pro.className='glePro';
    const sum=document.createElement('summary');sum.textContent='📚 전문 분석 보기 · SEC / 공급 / 공매도 / 촉매 / 전체 근거';
    const body=document.createElement('div');body.className='gleProBody';existing.forEach(n=>body.appendChild(n));pro.append(sum,body);
    view.replaceChildren(beginnerNode,pro);
  };
})();