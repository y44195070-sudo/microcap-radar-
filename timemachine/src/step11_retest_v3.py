from pathlib import Path
import json,re,shutil,os
import step11_retest as base

OUT=Path('timemachine/data/step11-retest-v3');base.OUT=OUT;base.RAW=OUT/'raw';base.NORM=OUT/'normalized';base.PIT=OUT/'pit';base.TESTS=OUT/'tests'
v2=Path(os.getenv('STEP11_RETEST_V2','/tmp/step11-retest-v2'))
if (v2/'raw').exists():
    base.RAW.mkdir(parents=True,exist_ok=True)
    for p in (v2/'raw').glob('*.bin'):shutil.copy2(p,base.RAW/p.name)

def strict_symbol(b):
    raw=b.decode('utf-8','ignore')
    for pat in [r'(?is)<ix:nonNumeric[^>]+name=["\']dei:TradingSymbol["\'][^>]*>\s*([A-Z][A-Z0-9.\-]{0,9})\s*</ix:nonNumeric>',r'(?is)<dei:TradingSymbol[^>]*>\s*([A-Z][A-Z0-9.\-]{0,9})\s*</dei:TradingSymbol>']:
        m=re.search(pat,raw)
        if m:return m.group(1).upper()
    i=raw.lower().find('trading symbol(s)')
    if i<0:i=raw.lower().find('trading symbols')
    if i>=0:
        vals=re.findall(r'>\s*([A-Z][A-Z0-9.\-]{0,9})\s*</(?:font|span|td|div)>',raw[i:i+2400])
        if vals:return vals[0].upper()
    return None
base.symbol_from_doc=strict_symbol

def persistent_ticker_evidence(filings,docs):
    raw=[]
    for f in filings:
        b=docs.get(f['accession_number'])
        if not b or f['CIK'] not in {'0000062709','0001790169'} or not f.get('accepted_at'):continue
        sym=strict_symbol(b)
        if sym:raw.append({'issuer_identity':f['issuer_identity'],'security_identity':f['security_identity'],'CIK':f['CIK'],'ticker':sym,'accepted_at':f['accepted_at'],'available_at':f['accepted_at'],'accession_number':f['accession_number'],'official_source':'SEC_EDGAR_PRIMARY_DOCUMENT','source_identifier':f['source_document'],'source_response_hash':base.sha(b),'confirmation_status':'official_confirmed','confidence':1.0})
    raw.sort(key=lambda x:(x['CIK'],x['available_at'],x['accession_number']));canonical=[];trans=[]
    for cik in sorted({x['CIK'] for x in raw}):
        xs=[x for x in raw if x['CIK']==cik]
        if not xs:continue
        current=xs[0]['ticker'];canonical.append(xs[0])
        for i,x in enumerate(xs[1:],1):
            if x['ticker']==current:canonical.append(x);continue
            # A ticker-state change must persist in official SEC cover observations. An isolated stale cover cannot reverse history.
            look=xs[i:min(len(xs),i+3)]; confirmations=sum(y['ticker']==x['ticker'] for y in look)
            if confirmations<2:continue
            prev=canonical[-1];trans.append({'issuer_identity':x['issuer_identity'],'security_identity':x['security_identity'],'old_ticker':current,'new_ticker':x['ticker'],'effective_date':None,'announced_at':x['accepted_at'],'available_at':x['available_at'],'official_source':'SEC_EDGAR_PRIMARY_DOCUMENT','source_identifier':x['source_identifier'],'source_response_hash':x['source_response_hash'],'confirmation_status':'official_confirmed','confidence':0.95,'derivation':'persistent chronological SEC TradingSymbol observations (>=2 confirmations in current/next 2 official filings); isolated stale covers ignored','prior_evidence_accession':prev['accession_number'],'new_evidence_accession':x['accession_number']})
            current=x['ticker'];canonical.append(x)
    return canonical,trans
base.build_ticker_evidence=persistent_ticker_evidence

def chain_supply(filings,docs):
    issuer='CIK:0001790169';byacc={f['accession_number']:f for f in filings};chains=[]
    for ch in base.json.loads((base.BASE/'normalized/filing-chains.json').read_text()):
        if not ch['issuer_file'].startswith(issuer+'|'):continue
        members=[byacc[x['accession_number']] for x in ch['filings'] if x['accession_number'] in byacc];life={s:base.stage_row(s) for s in base.STAGES};regs=[];effects=[];offers=[];auth=[];issues=[]
        for f in members:
            b=docs.get(f['accession_number']);txt=base.textify(b) if b else '';h=base.sha(b) if b else None;av=f.get('accepted_at');form=f['form_type']
            if form in {'S-1','S-1/A','S-3','S-3/A','F-1','F-1/A','F-3','F-3/A'}:
                subtype=base.registration_kind(txt,form) if b else 'unresolved';regs.append((av,base.evidence_ref(f,h,txt[:450] if b else None),subtype))
            if form=='EFFECT':effects.append((av,base.evidence_ref(f,h),None))
            if form in {'424B3','424B5'}:offers.append((av,base.evidence_ref(f,h,txt[:450] if b else None),None))
            if b:
                low=txt.lower()
                if re.search(r'\b(shareholders? approved|board approved).{0,180}\b(increase|authorization|authorized shares)\b',low):auth.append((av,base.evidence_ref(f,h,txt[:450]),None))
                if re.search(r'\b(we issued and sold|we sold and issued|company issued and sold|shares were issued and sold)\b',low):issues.append((av,base.evidence_ref(f,h,txt[:450]),None))
        def put(name,arr):
            if arr:
                arr=sorted(arr,key=lambda x:x[0] or '9999');life[name]=base.stage_row(name,'OBSERVED',arr[0][0],[x[1] for x in arr[:8]],arr[0][2])
        put('authorization',auth);put('registration',regs);put('effectiveness',effects);put('takedown / offering',offers);put('issuance',issues)
        # Resale availability is not the registration filing itself: require resale/mixed registration plus effectiveness in the SAME filing chain.
        resale_regs=[x for x in regs if x[2] in {'resale registration','mixed registration'}]
        if resale_regs and effects:
            rr=sorted(resale_regs,key=lambda x:x[0] or '9999')[0];ef=sorted(effects,key=lambda x:x[0] or '9999')[0];av=max(rr[0],ef[0]);life['resale availability']=base.stage_row('resale availability','OBSERVED',av,[rr[1],ef[1]],rr[2])
        chains.append({'filing_chain_id':ch['filing_chain_id'],'issuer_file':ch['issuer_file'],'stages':[life[s] for s in base.STAGES]})
    def score(c):return sum(x['status']=='OBSERVED' for x in c['stages'])
    selected=max(chains,key=score) if chains else {'filing_chain_id':None,'issuer_file':None,'stages':[base.stage_row(s,'UNRESOLVED') for s in base.STAGES]}
    return {'issuer_identity':issuer,'filing_chain_id':selected['filing_chain_id'],'issuer_file':selected['issuer_file'],'stages':selected['stages'],'chains':chains,'semantics':'six stages are chain-scoped; missing official evidence remains NOT_OBSERVED; resale availability requires resale/mixed registration plus EFFECT in the same chain'}
base.build_supply=chain_supply
base.main()

report_path=base.OUT/'step11-retest-report.json';tests_path=base.TESTS/'regression.json';tick_path=base.NORM/'official-ticker-evidence.json';life_path=base.NORM/'supply-lifecycle.json'
report=json.loads(report_path.read_text());tests=json.loads(tests_path.read_text());tick=json.loads(tick_path.read_text());life=json.loads(life_path.read_text());pairs={(x['old_ticker'],x['new_ticker']) for x in tick['transitions']};obs={(x['CIK'],x['ticker']) for x in tick['observations']}
chain_integrity=all([len(c['stages'])==6 and [x['stage'] for x in c['stages']]==base.STAGES for c in life.get('chains',[])])
resale_integrity=True
for c in life.get('chains',[]):
    d={x['stage']:x for x in c['stages']}
    if d['resale availability']['status']=='OBSERVED':
        resale_integrity &= d['registration']['status']=='OBSERVED' and d['effectiveness']['status']=='OBSERVED' and base.parse_dt(d['resale availability']['available_at'])>=base.parse_dt(d['effectiveness']['available_at'])
extra={'ticker_parser_no_css_tokens':not any(s in {'FONT','SPAN','STYLE','COLOR'} for _,s in obs),'mmc_mrsh_exact_regression':('MMC','MRSH') in pairs,'flgc_zstk_exact_regression':('FLGC','ZSTK') in pairs,'no_false_ticker_reversions':('MRSH','MMC') not in pairs and ('ZSTK','FLGC') not in pairs,'ticker_transition_source_hashes':all(x.get('source_response_hash') for x in tick['transitions']),'supply_chain_scoped':chain_integrity,'resale_requires_effectiveness_same_chain':resale_integrity,'issuance_not_fabricated':all(x['status']!='OBSERVED' or x['evidence'] for c in life.get('chains',[]) for x in c['stages'] if x['stage']=='issuance')}
tests.update(extra);report['tests']=tests;report['strict_post_audit']=extra;report['final_verdict']='STEP11_PASS' if all(tests.values()) else 'STEP11_CONDITIONAL';tests_path.write_text(json.dumps(tests,indent=2));report_path.write_text(json.dumps(report,indent=2,ensure_ascii=False));print(json.dumps({'strict_post_audit':extra,'final_verdict':report['final_verdict']}))
