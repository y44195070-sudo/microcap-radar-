from pathlib import Path
import json,re,shutil,os
import step11_retest as base

OUT=Path('timemachine/data/step11-retest-v2')
base.OUT=OUT;base.RAW=OUT/'raw';base.NORM=OUT/'normalized';base.PIT=OUT/'pit';base.TESTS=OUT/'tests'
# Reuse RETEST-v1 official downloads as immutable cache instead of re-calling SEC.
v1=Path(os.getenv('STEP11_RETEST_V1','/tmp/step11-retest-v1'))
if (v1/'raw').exists():
    base.RAW.mkdir(parents=True,exist_ok=True)
    for p in (v1/'raw').glob('*.bin'):
        shutil.copy2(p,base.RAW/p.name)

def strict_symbol_from_doc(b):
    raw=b.decode('utf-8','ignore')
    # Inline XBRL, when present.
    for pat in [r'(?is)<ix:nonNumeric[^>]+name=["\']dei:TradingSymbol["\'][^>]*>\s*([A-Z][A-Z0-9.\-]{0,9})\s*</ix:nonNumeric>',r'(?is)<dei:TradingSymbol[^>]*>\s*([A-Z][A-Z0-9.\-]{0,9})\s*</dei:TradingSymbol>']:
        m=re.search(pat,raw)
        if m:return m.group(1).upper()
    # SEC cover table fallback: only accept an all-caps cell after the Trading symbol(s) header.
    i=raw.lower().find('trading symbol(s)')
    if i<0:i=raw.lower().find('trading symbol')
    if i>=0:
        window=raw[i:i+2400]
        vals=re.findall(r'>\s*([A-Z][A-Z0-9.\-]{0,9})\s*</(?:font|span|td|div)>',window)
        if vals:return vals[0].upper()
    return None

base.symbol_from_doc=strict_symbol_from_doc
base.main()

# Independent post-run audit: expected regression identities may be asserted, but never used to derive history.
tick_path=base.NORM/'official-ticker-evidence.json'; report_path=base.OUT/'step11-retest-report.json'; tests_path=base.TESTS/'regression.json'
tick=json.loads(tick_path.read_text()); report=json.loads(report_path.read_text()); tests=json.loads(tests_path.read_text())
pairs={(x['old_ticker'],x['new_ticker']) for x in tick['transitions']}
obs={(x['CIK'],x['ticker']) for x in tick['observations']}
extra={
 'ticker_parser_no_css_tokens':not any(x[1] in {'FONT','SPAN','STYLE','COLOR'} for x in obs),
 'mmc_mrsh_exact_regression':('MMC','MRSH') in pairs,
 'flgc_zstk_exact_regression':('FLGC','ZSTK') in pairs,
 'ticker_transition_source_hashes':all(x.get('source_response_hash') and x.get('official_source')=='SEC_EDGAR_PRIMARY_DOCUMENT' for x in tick['transitions']),
}
tests.update(extra);report['tests']=tests;report['ticker_parser_audit']=extra
report['final_verdict']='STEP11_PASS' if all(tests.values()) else 'STEP11_CONDITIONAL'
tests_path.write_text(json.dumps(tests,indent=2));report_path.write_text(json.dumps(report,indent=2,ensure_ascii=False))
print(json.dumps({'post_audit':extra,'final_verdict':report['final_verdict']}))
