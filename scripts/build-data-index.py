"""Generate the static ticker manifest; no application or analysis files are modified."""
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = []
for path in sorted((root / 'data').glob('*.json')):
    if not re.fullmatch(r'[A-Z][A-Z0-9.-]*', path.stem):
        continue
    data = json.loads(path.read_text())
    if data.get('ticker', path.stem) != path.stem:
        raise ValueError(f'Ticker/filename mismatch: {path.name}')
    files.append(path.name)
(root / 'data' / 'index.json').write_text(json.dumps(files, indent=2) + '\n')
