"""Verify the actual published Pages site, including its project subpath."""
import argparse
import json
import sys
import urllib.request
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('url')
args = parser.parse_args()
base = args.url.rstrip('/') + '/'
diagnostics = []
try:
    for path in ['', 'data/index.json', 'data/CDT.json']:
        with urllib.request.urlopen(base + path, timeout=30) as response:
            body = response.read().decode()
            if path:
                json.loads(body)
            elif 'loadRadarAnalyses' not in body:
                raise AssertionError('Published HTML does not include the external analysis loader')
            diagnostics.append(f'{path or "index.html"}: HTTP {response.status}, {len(body)} chars')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on('console', lambda msg: diagnostics.append(f'console {msg.type}: {msg.text}') if msg.type in ['error', 'warning'] else None)
        page.on('pageerror', lambda error: diagnostics.append(f'JS exception: {error}'))
        page.on('response', lambda r: diagnostics.append(f'JSON response: {r.status} {r.url}') if '/data/' in r.url else None)
        page.goto(base, wait_until='domcontentloaded')
        page.wait_for_function("typeof DB === 'function' && !!DB().CDT", timeout=30000)
        assert page.locator('#meta').inner_text().startswith('28종목'), page.locator('#meta').inner_text()
        page.locator('#q').fill('CDT')
        page.locator('#go').click()
        page.wait_for_selector('#memo-CDT')
        assert page.locator('h1').inner_text().startswith('CDT')
        assert 'Astor' in page.locator('#view').inner_text()
        page.goto(base + '?ticker=CDT', wait_until='domcontentloaded')
        page.wait_for_selector('#memo-CDT')
        assert page.locator('#meta').inner_text().startswith('28종목')
        browser.close()
    print('::notice title=Live Pages verified::28 tickers; CDT search, analysis and direct URL passed. ' + ' | '.join(diagnostics))
except Exception as error:
    message = (str(error) + ' | ' + ' | '.join(diagnostics)).replace('\n', '%0A').replace('\r', '%0D')
    print('::error title=Live Pages diagnosis::' + message)
    sys.exit(1)
