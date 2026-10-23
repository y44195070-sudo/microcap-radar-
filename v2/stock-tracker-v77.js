(()=>{
const old=window.render;if(typeof old!=='function')return;
const esc=s=>String(s??'확인 필요').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const val=(o,keys,f='확인 필요')=>{for(const k of keys){if(o&&o[k]!=null&&o[k]!=='')return o[k]}return f};
const arr=x=>Array.isArray(x)?x:[];
const txt=x=>typeof x==='string'?x:(x&&typeof x==='object'?(x.title||x.name||x.summary||JSON.stringify(x)):'확인 필요');
const pct=x=>{const m=String(x||'').match(/([\d.]+)\s*%/);return m?+m[1]:null};
function css(){if(document.getElementById('stockTracker77'))return;const s=document.createElement('style');s.id='stockTracker77';s.textContent=`
.stockTracker{display:grid;gap:13px;margin-bottom:16px}.stCard,.stBox{border:1px solid var(--border,#2b3340);border-radius:16px;padding:16px;background:var(--card,#151a22)}.stKicker{font-size:12px;opacity:.62}.stTitle{font-size:22px;margin:4px 0 9px}.stLead{font-size:14px;line-height:1.68;margin:0}.stStatus{display:inline-flex;margin-top:11px;padding:7px 11px;border-radius:999px;background:rgba(245,184,65,.12);border:1px solid rgba(245,184,65,.32);font-weight:800}.stTwo{display:grid;grid-template-columns:1fr 1fr;gap:10px}.stBox h3,.stCard h3{margin:0 0 10px;font-size:17px}.stItem{padding:9px 0;border-top:1px solid var(--border,#2b3340);line-height:1.5}.stItem:first-of-type{border-top:0}.stItem small{display:block;opacity:.7;margin-top:3px;line-height:1.45}.stGood{color:#57c785}.stBad{color:#ef7777}.stWarn{color:#f0b35a}.stFlow{display:grid;gap:5px;text-align:center;max-width:480px;margin:0 auto}.stStep{border:1px solid var(--border,#2b3340);border-radius:12px;padding:10px}.stNow{border-color:rgba(245,184,65,.65);background:rgba(245,184,65,.1);font-weight:850}.stArrow{opacity:.65;font-size:12px}.stDanger{margin-top:12px;padding:12px;border-radius:12px;background:rgba(239,119,119,.08);border:1px solid rgba(239,119,119,.28);line-height:1.55}.stRows{display:grid}.stRow{padding:10px 0;border-top:1px solid var(--border,#2b3340);line-height:1.5}.stRow:first-child{border-top:0}.stRow small{display:block;opacity:.7;margin-top:3px}.stWhy{margin-top:10px;padding:11px;border-radius:11px;background:rgba(120,140,255,.07);font-size:13px;line-height:1.55}.stCheck{display:grid;gap:8px}.stCheck>div{padding:10px 11px;border:1px solid var(--border,#2b3340);border-radius:11px;line-height:1.45}.stCheck small{display:block;opacity:.68;margin-top:3px}.stScore{font-size:24px;font-weight:900}.stPro{margin-top:2px}.stPro>summary{cursor:pointer;list-style:none;border:1px solid var(--border,#2b3340);border-radius:14px;padding:14px 16px;font-weight:850}.stPro>summary::-webkit-details-marker{display:none}.stPro>summary:after{content:' ▼';float:right;opacity:.6}.stPro[open]>summary:after{content:' ▲'}.stProBody{margin-top:14px}.stFresh{margin-top:9px;font-size:12px;opacity:.72}.stTag{display:inline-block;font-size:12px;padding:4px 8px;border:1px solid var(--border,#2b3340);border-radius:999px;margin:0 5px 5px 0}
@media(max-width:620px){.stTwo{grid-template-columns:1fr}.stCard,.stBox{padding:14px}.stTitle{font-size:20px}}
`;document.head.appendChild(s)}
function derive(d){
 const st=d.structure||{},sh=d.short||{},sm=d.supplyMap||{},sig=d.signal||{};
 const float=val(st,['실제 Float','float','Float','publicFloat','effectiveFloat']);
 const os=val(st,['O/S','os','Class A O/S','10/21 Class A O/S']);
 const rs=val(st,['reverseSplit','추가 RS','직전 RS']);
 const sf=val(sh,['Short Float','shortFloat']); const ctb=val(sh,['CTB','ctb']); const borrow=val(sh,['Borrow','borrow']); const reg=val(sh,['Reg SHO','regsho']); const si=val(sh,['Short Interest','latestSI']);
 const sfN=pct(sf),ctbN=pct(ctb);
 const risks=arr(d.risks).map(txt), dilution=arr(d.dilution).map(txt), events=arr(d.events).map(txt), checks=arr(d.nextChecks).map(txt);
 const supplyRisk=String(sm.summary?.risk||sig.text||'').includes('🔴')||/공급 개방|희석|dilution|전환/i.test(String(sig.text||''));
 const lowFloat=/\b[0-9.]+\s*[KkMm]\b|만|초저|저유통/i.test(String(float));
 const highShort=(sfN!=null&&sfN>=20)||(ctbN!=null&&ctbN>=50);
 let status=supplyRisk?'🚨 공급 경계':highShort?'🟠 수급 관찰':events.length?'🟡 이벤트 관찰':'🟡 관찰';
 if(String(d.tier||'').includes('핵심')&&!supplyRisk)status='⭐ 핵심 추적';
 let lead=sig.summary||val(st,['핵심 구조','핵심'],'');
 if(!lead){lead=lowFloat?'거래 가능한 주식 수가 적을 가능성이 있어 수급 변화에 민감할 수 있는 종목이야.':'현재 구조에서 공급·공매도·촉매를 함께 확인해야 하는 종목이야.'}
 const good=[];
 if(float!=='확인 필요')good.push([`유통주식 · ${float}`,lowFloat?'유통량이 작다면 거래량 유입 때 가격 탄력이 커질 수 있어.':'유통량이 실제로 얼마나 작은지 다른 수급 지표와 함께 봐야 해.']);
 if(ctb!=='확인 필요')good.push([`CTB · ${ctb}`,ctbN!=null&&ctbN>=50?'빌리는 비용이 높은 편이라 공매도 유지 부담이 커.':'대차비용만으로 강한 압박 구조라고 보기는 어려워.']);
 if(sf!=='확인 필요')good.push([`Short Float · ${sf}`,sfN!=null&&sfN>=20?'공매도 비중이 의미 있는 수준이라 수급 압박 시 연료가 될 수 있어.':'공매도 비중 자체는 강한 숏스퀴즈 조건인지 추가 확인이 필요해.']);
 if(events.length)good.push([`추적 이벤트 · ${events[0]}`,'이벤트의 확정 여부와 실제 경제적 효과를 구분해서 봐야 해.']);
 if(!good.length)good.push(['❓ 최신 구조 확인 필요','현재 저장 데이터만으로 강점을 확정하기 어려워.']);
 const bad=[];
 [...risks,...dilution].slice(0,3).forEach(x=>bad.push([x,'실제 시장 공급 또는 구조 악화로 이어지는지 확인해야 해.']));
 if(!bad.length&&supplyRisk)bad.push(['공급 통로 존재','등록과 실제 발행은 다르므로 실제 실행 공시를 확인해야 해.']);
 if(!bad.length)bad.push(['❓ 최신 위험요인 확인 필요','저장 데이터만으로 현재 위험을 확정하지 않아.']);
 const now=sm.summary?.sellableNow||dilution.find(x=>/즉시|closing|클로징|행사|재판매/i.test(x))||'❓ 확인 필요';
 const potential=sm.summary?.potential||dilution.find(x=>/잠재|조건부|warrant|워런트|shelf|셸프|convert|전환|ATM|ELOC/i.test(x))||'❓ 확인 필요';
 const locked=sm.summary?.locked||dilution.find(x=>/락업|제한|locked|제한주/i.test(x))||'❓ 확인 필요';
 let shortAnswer='❓ 최신 데이터 확인 필요';
 if(sfN!=null&&sfN>=20&&ctbN!=null&&ctbN>=50)shortAnswer='🟠 숏스퀴즈 연료가 의미 있는 편';
 else if(sfN!=null&&sfN<10)shortAnswer='🟡 강한 숏스퀴즈형으로 보기 어려움';
 else if(ctbN!=null&&ctbN>=50)shortAnswer='🟡 대차 압박은 있지만 Short Float와 함께 확인 필요';
 const stale=d.asOf&&String(d.asOf)<'2026-10-20';
 return {st,sh,sm,float,os,rs,sf,ctb,borrow,reg,si,risks,dilution,events,checks,status,lead,good:good.slice(0,4),bad:bad.slice(0,4),now,potential,locked,shortAnswer,stale,supplyRisk};
}
function list(items,cls=''){return items.map(([a,b])=>`<div class="stItem"><b class="${cls}">${esc(a)}</b><small>${esc(b)}</small></div>`).join('')}
function ui(d){const x=derive(d),t=esc(d.ticker||'');const score=d.score??'확인 필요';const next=x.checks.length?x.checks.slice(0,5):['최신 SEC/회사 공시','최신 O/S·Float','최신 CTB·Borrow·Short Interest'];
 const eventHtml=x.events.length?x.events.slice(0,5).map((z,i)=>`<div class="stRow"><b>${i===0?'🔵':'🟡'} ${esc(z)}</b><small>${typeof d.events?.[i]==='object'&&d.events[i]?.confirmed===false?'예상/미확정 · 실제 발생 여부 확인 필요':'저장 데이터 기준 · 최신 상태 재확인 필요'}</small></div>`).join(''):'<div class="stRow"><b>❓ 확인 가능한 촉매 데이터 부족</b><small>최신 공식자료 확인 필요</small></div>';
 const scoreParts=d.scoreParts&&Object.keys(d.scoreParts).length?Object.entries(d.scoreParts).map(([k,v])=>`<div class="stRow"><b>${esc(k)}</b><small>${esc(v)}</small></div>`).join(''):'<div class="stRow"><b>❓ 세부 점수 데이터 없음</b><small>기존 총점은 유지하고 세부 산식은 확인 필요</small></div>';
 return `<div class="stockTracker">
 <section class="stCard"><div class="stKicker">${t} 초보자 추적 대시보드 · 데이터 기준 ${esc(d.asOf||'확인 필요')}</div><h2 class="stTitle">${t} — 현재 ${esc(x.status)}</h2><p class="stLead">${esc(x.lead)}</p><span class="stStatus">예측 신호가 아니라 현재 구조 상태</span>${x.stale?'<div class="stFresh">❓ 저장 데이터 기준일이 오래됐어. 최신 공식자료 재확인 필요.</div>':''}</section>
 <section class="stTwo"><div class="stBox"><h3>🟢 왜 관심 있게 봐?</h3>${list(x.good,'stGood')}</div><div class="stBox"><h3>🔴 왜 조심해야 해?</h3>${list(x.bad,'stBad')}</div></section>
 <section class="stCard"><h3>🎯 현재 단계 → 다음 단계</h3><div class="stFlow"><div class="stStep">⚪ 구조 후보</div><div class="stArrow">↓ 저장 데이터로 핵심 구조 확인</div><div class="stStep stNow">${esc(x.status)} · 현재</div><div class="stArrow">↓ ${x.supplyRisk?'실제 공급이 멈추고 핵심 촉매·수급이 개선되면':'거래량·대차·핵심 촉매가 실제로 강화되면'}</div><div class="stStep">🟠 구조 강화 확인</div><div class="stArrow">↓ 여러 조건이 동시에 확인되면</div><div class="stStep">🔥 점화 가능 구조</div></div><div class="stDanger"><b>🚨 구조가 깨지는 경로</b><br>${esc(x.risks[0]||x.dilution[0]||'신규 희석·공급, 핵심 촉매 무산, 유통량 급증 여부를 확인해야 해.')}</div><div class="stWhy">단계표는 미래 주가 예측이 아니야. <b>현재 확인된 조건 → 다음에 확인할 조건</b>을 보여줘.</div></section>
 <section class="stCard"><h3>💰 급등하면 새 주식이 나올 위험은?</h3><p class="stLead"><b>${x.supplyRisk?'⚠️ 공급 위험을 우선 확인':'🟡 실제 공급 가능 여부 확인 필요'}</b></p><div class="stRows"><div class="stRow"><b>① 지금 시장에 나올 수 있는 물량</b><small>${esc(x.now)}</small></div><div class="stRow"><b>② 앞으로 나올 수 있는 물량</b><small>${esc(x.potential)}</small></div><div class="stRow"><b>③ 현재 묶이거나 조건부인 물량</b><small>${esc(x.locked)}</small></div></div><div class="stWhy"><b>👉 그래서 뭘 확인해?</b> ATM · Shelf · ELOC · PIPE · Warrants · Convertible · Resale의 <b>등록과 실제 발행/매도</b>를 구분해서 봐.</div></section>
 <section class="stCard"><h3>🩳 공매도가 급등 연료가 될 수 있어?</h3><p class="stLead"><b>${esc(x.shortAnswer)}</b></p><div class="stRows"><div class="stRow"><b>Short Interest · ${esc(x.si)}</b></div><div class="stRow"><b>Short Float · ${esc(x.sf)}</b></div><div class="stRow"><b>CTB · ${esc(x.ctb)}</b></div><div class="stRow"><b>Borrow · ${esc(x.borrow)}</b></div><div class="stRow"><b>Reg SHO · ${esc(x.reg)}</b></div></div><div class="stWhy">RS 전후 데이터가 섞이거나 기준일이 오래된 경우 숫자를 그대로 비교하면 안 돼. 미확인 값은 숏스퀴즈 근거로 사용하지 않아.</div></section>
 <section class="stCard"><h3>🔥 지금 주가를 움직일 재료가 있어?</h3>${eventHtml}<div class="stWhy"><span class="stTag">✅ 발생</span><span class="stTag">🔵 진행 중</span><span class="stTag">📅 날짜 확정</span><span class="stTag">🟡 예상</span><span class="stTag">❓ 확인 필요</span><br>MOU·계약·임상·Nasdaq·M&A·실적은 실제 확정도와 경제적 효과를 구분해서 봐.</div></section>
 <section class="stTwo"><div class="stBox"><h3>🎯 ${t}가 좋아지려면?</h3>${next.slice(0,4).map((z,i)=>`<div class="stItem">${i+1}. ${esc(z)}<small>좋은 방향으로 실제 확인되는지 추적</small></div>`).join('')}</div><div class="stBox"><h3>🚨 구조가 나빠지는 조건</h3>${(x.risks.length?x.risks:x.dilution.length?x.dilution:['신규 희석·공급','핵심 촉매 무산','O/S·Float 급증']).slice(0,4).map((z,i)=>`<div class="stItem">${i+1}. ${esc(z)}</div>`).join('')}</div></section>
 <section class="stCard"><h3>👀 오늘 ${t}에서 이것만 보면 돼</h3><div class="stKicker">기준 ${esc(d.asOf||'확인 필요')} · 실시간 자동 데이터 아님</div><div class="stCheck">${next.map(z=>`<div>❓ <b>${esc(z)}</b><small>최신 공식자료 또는 최신 수급 데이터 확인 필요</small></div>`).join('')}</div><div class="stWhy"><b>현재 결론:</b> 저장 데이터 이후 변화는 자동으로 단정하지 않아. 새 공시·수급 데이터가 확인되면 구조를 다시 평가해.</div></section>
 <section class="stCard"><h3>📊 현재 구조점수</h3><div class="stScore">${esc(score)}/100</div><p class="stLead">이 점수는 <b>상승확률이 아니라 구조의 질을 비교하기 위한 점수</b>야.</p><details><summary><b>점수 상세 보기</b></summary><div class="stRows">${scoreParts}</div></details></section>
 </div>`}
css();
window.render=function(d){
 old(d);
 if(!d||!d.ticker||String(d.ticker).toUpperCase()==='GLE')return;
 const view=document.getElementById('view');if(!view)return;
 const expert=view.innerHTML;
 view.innerHTML=ui(d)+`<details class="stPro"><summary>📚 전문 분석 보기</summary><div class="stProBody">${expert}</div></details>`;
};
})();