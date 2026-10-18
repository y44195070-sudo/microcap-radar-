"""Exercise the generated artifact under a project subpath, with JSON requests blocked."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import tempfile
import threading
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='radar-pages-') as tmp:
    site = Path(tmp) / 'microcap-radar-'
    subprocess.run(['python3', str(root/'scripts/build-data-index.py'), '--site-dir', str(site)], check=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=tmp))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/microcap-radar-/'
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.add_init_script('AbortSignal.timeout = undefined')
            page.route('**/data/**', lambda route: route.abort())
            page.goto(base+'?ticker=CDT', wait_until='domcontentloaded')
            assert page.locator('#meta').inner_text().startswith('28종목')
            assert page.locator('#memo-CDT').count() == 1
            assert 'Astor' in page.locator('#view').inner_text()
            print('Initial rendering: 28 tickers and CDT without waiting for JSON')
            assert not errors, errors
            page.unroute('**/data/**')
            with page.expect_response(lambda response: response.url.endswith('/data/CDT.json')) as loaded:
                page.goto(base, wait_until='domcontentloaded')
            assert loaded.value.status == 200
            page.locator('#q').fill('CDT')
            page.locator('#go').click()
            page.wait_for_selector('#memo-CDT')
            assert not errors, errors
            print('Project subpath JSON refresh and search passed without AbortSignal.timeout')
            browser.close()
    finally:
        server.shutdown()
