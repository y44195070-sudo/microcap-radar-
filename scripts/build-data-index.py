"""Build a ticker manifest and optional Pages artifact with an initial data snapshot."""
import argparse
import json
import re
import shutil
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--site-dir', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
analyses = {}
files = []
for path in sorted((root / 'data').glob('*.json')):
    if not re.fullmatch(r'[A-Z][A-Z0-9.-]*', path.stem):
        continue
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get('ticker', path.stem) != path.stem:
        raise ValueError(f'Invalid analysis or ticker/filename mismatch: {path.name}')
    analyses[path.stem] = data
    files.append(path.name)
if args.site_dir:
    dest = args.site_dir.resolve()
    if dest == root or root in dest.parents:
        raise ValueError('Build output must be outside the source checkout')
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / 'data', dest / 'data', dirs_exist_ok=True)
    html = (root / 'index.html').read_text()
    marker = '<script type="application/json" id="radar-external-data">{}</script>'
    if html.count(marker) != 1:
        raise ValueError('Expected exactly one external data snapshot marker')
    # Escape markup so analysis text cannot close the inert JSON script element.
    payload = json.dumps(analyses, ensure_ascii=False).replace('<', r'\u003c')
    html = html.replace(marker, marker.replace('{}', payload))
    (dest / 'index.html').write_text(html)
else:
    dest = root
(dest / 'data' / 'index.json').write_text(json.dumps(files, indent=2) + '\n')
print(f'Built {len(files)} external analyses in {dest}')
