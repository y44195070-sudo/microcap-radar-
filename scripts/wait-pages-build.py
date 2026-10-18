"""When Pages still uses a branch source, publish our generated artifact last."""
import json
import os
import subprocess
import time

repo = os.environ['GITHUB_REPOSITORY']
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
source = subprocess.check_output(['gh', 'api', f'repos/{repo}/pages', '--jq', '.build_type'], text=True).strip()
if source == 'workflow':
    print('::notice title=Pages deployment order::Pages already uses workflow deployments')
else:
    for attempt in range(54):
        result = json.loads(subprocess.check_output(['gh', 'api', f'repos/{repo}/actions/runs?head_sha={sha}&per_page=100'], text=True))
        runs = [run for run in result['workflow_runs'] if run.get('path') == 'dynamic/pages/pages-build-deployment']
        pending = [run for run in runs if run['status'] != 'completed']
        if runs and not pending:
            print('::notice title=Pages deployment order::Branch Pages build completed; publishing the generated artifact afterward')
            break
        if not runs and attempt >= 5:
            print('::notice title=Pages deployment order::No competing branch Pages build found')
            break
        time.sleep(10)
    else:
        raise TimeoutError('Competing branch Pages build did not finish; refusing to race deployments')
