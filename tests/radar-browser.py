"""Run against a local server: python3 -m http.server 8000."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=browser.new_page()
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8000/?ticker=CDT')
    page.wait_for_function("!!DB().CDT")
    page.wait_for_function("!!document.querySelector('#memo-CDT')")
    assert page.locator('h1').inner_text().startswith('CDT')
    text=page.locator('#view').inner_text()
    assert '32' in text and 'Astor' in text
    assert page.evaluate('DB().CDT.events[0].title').startswith('10/2')
    assert page.evaluate('DB().CDT.frames.kkung').startswith('핵심')
    tickers=page.evaluate('Object.keys(DB())')
    for ticker in tickers:
        page.evaluate('(t)=>nav(t)',ticker)
        assert page.locator('h1').inner_text().startswith(ticker),ticker
    print('All',len(tickers),'ticker analysis screens rendered')
    for tab in page.locator('#tabs [data-tab]').evaluate_all('(els)=>els.map(e=>e.dataset.tab)'):
        page.locator('#tabs [data-tab="'+tab+'"]').click()
        assert page.locator('#view').inner_text().strip(),tab
    page.locator('#q').fill('CDT')
    page.locator('#go').click()
    page.locator('#memo-CDT').fill('persistent test memo')
    page.wait_for_timeout(500)
    page.reload()
    page.wait_for_selector('#memo-CDT')
    assert page.locator('#memo-CDT').input_value()=='persistent test memo'
    page.set_viewport_size({'width':390,'height':844})
    assert page.locator('h1').is_visible()
    assert not errors,errors
    print('11 tabs, CDT search, memo persistence, mobile, runtime errors: passed')
    # Failure isolation: a bad external analysis must not remove embedded tickers.
    page.route('**/data/CDT.json',lambda r:r.fulfill(status=200,body='{broken'))
    page.reload()
    page.wait_for_timeout(1000)
    assert page.evaluate('Object.keys(DB()).length')==27
    assert page.locator('#req').count()==1
    assert not errors,errors
    print('Malformed JSON fallback: passed')
    page.unroute('**/data/CDT.json')
    # Pages cannot list directories: test manifest discovery independently.
    page.route('**/data/',lambda r:r.fulfill(status=404))
    page.goto('http://127.0.0.1:8000/?ticker=CDT')
    page.wait_for_selector('#memo-CDT')
    print('Static manifest discovery: passed')
    page.unroute('**/data/')
    # Adding a file alone must make it searchable without editing HTML.
    extra=Path(__file__).resolve().parents[1]/'data'/'ZZTEST.json'
    assert not extra.exists()
    try:
        extra.write_text(json.dumps({'ticker':'ZZTEST','company':'Auto discovery test','score':42,'signal':{'color':'yellow','text':'Test'}}))
        page.goto('http://127.0.0.1:8000/?ticker=ZZTEST')
        page.wait_for_selector('#memo-ZZTEST')
        assert 'Auto discovery test' in page.locator('#view').inner_text()
        print('New JSON file discovered without HTML edits: passed')
    finally:
        extra.unlink()
    assert not errors,errors
    browser.close()
