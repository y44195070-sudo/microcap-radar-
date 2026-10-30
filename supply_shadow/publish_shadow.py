#!/usr/bin/env python3
"""PRODUCT-1B-1I publication (separate job, contents: write). Copies staged files into the checkout, verifies path scope,
commits as bot, pushes. Non-fast-forward -> fetch + rebase ONCE -> re-verify scope + decision_payload_sha256 -> push ONCE. Never force-push.
--dry-run: everything except push."""
import argparse, json, os, re, subprocess, sys, hashlib
ALLOWED = re.compile(r'^v2/data/supply-shadow/(latest\.json|history/\d{4}-\d{2}-\d{2}(\.rerun-[A-Za-z0-9_-]+)?\.json)$')
class Fail(Exception): pass
def git(repo, *a, check=True):
    r = subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True)
    if check and r.returncode: raise Fail('GIT_' + a[0].upper())
    return r
def payload_sha(path):
    w = json.load(open(path)); return hashlib.sha256(json.dumps(w['decision_payload'], sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
def changed_paths(repo):
    out = git(repo, 'diff', '--cached', '--name-only').stdout.split()
    return sorted(set(out))
def verify_scope(repo, plan):
    ch = changed_paths(repo)
    if not ch: raise Fail('NOTHING_TO_COMMIT')
    if any(not ALLOWED.match(p) for p in ch): raise Fail('PUBLICATION_PATH_SCOPE_VIOLATION')
    if set(ch) - set(plan['files']): raise Fail('PUBLICATION_PATH_SCOPE_VIOLATION')
    return ch
def publish(repo, staging, branch='main', dry_run=False, remote='origin'):
    plan = json.load(open(os.path.join(staging, 'publish_plan.json')))
    for rel in plan['files']:
        if not ALLOWED.match(rel): raise Fail('PUBLICATION_PATH_SCOPE_VIOLATION')
        src = os.path.join(staging, rel)
        if payload_sha(src) != plan['decision_payload_sha256']: raise Fail('STAGED_PAYLOAD_SHA_MISMATCH')
        hist = rel.startswith('v2/data/supply-shadow/history/')
        dst = os.path.join(repo, rel)
        if hist and os.path.exists(dst): raise Fail('HISTORY_OVERWRITE_PROHIBITED')
        os.makedirs(os.path.dirname(dst), exist_ok=True); open(dst, 'wb').write(open(src, 'rb').read())
        git(repo, 'add', '--', rel)
    verify_scope(repo, plan)
    git(repo, '-c', 'user.name=supply-shadow-bot', '-c', 'user.email=supply-shadow-bot@users.noreply.github.com', 'commit', '-m',
        f"supply-shadow: {plan['target_date']} payload {plan['decision_payload_sha256'][:12]}")
    if dry_run: return {'PUBLISH_STATUS': 'DRY_RUN_COMMITTED_LOCALLY', 'files': plan['files']}
    if git(repo, 'push', remote, f'HEAD:{branch}', check=False).returncode == 0: return {'PUBLISH_STATUS': 'PUSHED', 'attempts': 1}
    git(repo, 'fetch', remote, branch)
    if git(repo, 'rebase', f'{remote}/{branch}', check=False).returncode != 0:
        git(repo, 'rebase', '--abort', check=False); raise Fail('REBASE_CONFLICT')
    ch = git(repo, 'diff', '--name-only', f'{remote}/{branch}', 'HEAD').stdout.split()
    if any(not ALLOWED.match(p) for p in ch) or set(ch) - set(plan['files']): raise Fail('PUBLICATION_PATH_SCOPE_VIOLATION_AFTER_REBASE')
    for rel in plan['files']:
        if payload_sha(os.path.join(repo, rel)) != plan['decision_payload_sha256']: raise Fail('DECISION_PAYLOAD_CHANGED_AFTER_REBASE')
        if rel.startswith('v2/data/supply-shadow/history/') and git(repo, 'cat-file', '-e', f'{remote}/{branch}:{rel}', check=False).returncode == 0:
            raise Fail('HISTORY_OVERWRITE_PROHIBITED')
    if git(repo, 'push', remote, f'HEAD:{branch}', check=False).returncode == 0: return {'PUBLISH_STATUS': 'PUSHED', 'attempts': 2}
    raise Fail('PUSH_FAILED_AFTER_SINGLE_REBASE')
def main(argv=None):
    ap = argparse.ArgumentParser(allow_abbrev=False); ap.add_argument('--repo-root', required=True); ap.add_argument('--staging-dir', required=True)
    ap.add_argument('--branch', default='main'); ap.add_argument('--dry-run', action='store_true'); a = ap.parse_args(argv)
    try: r = publish(a.repo_root, a.staging_dir, a.branch, a.dry_run)
    except Fail as e: print(json.dumps({'PUBLISH_STATUS': 'FAILED', 'reason': str(e)})); return 1
    print(json.dumps(r)); return 0
if __name__ == '__main__': sys.exit(main())
