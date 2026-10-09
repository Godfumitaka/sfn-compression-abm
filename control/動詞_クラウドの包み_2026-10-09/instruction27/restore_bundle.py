"""土台を持つ専用cloneだけを作り、固定したbundleを取り出す。模型起動なし。"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent


def restore(base_repository, destination):
    version = json.loads((HERE/'versions.json').read_text())
    bundle = HERE/'birth_workers.bundle'
    assert bundle.stat().st_size == version['bundle_bytes'] and bundle.stat().st_size < 50_000_000
    assert hashlib.sha256(bundle.read_bytes()).hexdigest() == version['bundle_sha256']
    dest = Path(destination).resolve()
    assert not dest.exists(), '既存checkoutには書き込まない'
    base = Path(base_repository).resolve()
    subprocess.run(['git', 'cat-file', '-e', version['base_commit']+'^{commit}'], cwd=base, check=True)
    subprocess.run(['git', 'clone', '--shared', '--no-checkout', str(base), str(dest)], check=True)
    subprocess.run(['git', 'bundle', 'verify', str(bundle.resolve())], cwd=dest, check=True)
    subprocess.run(['git', 'fetch', '--no-tags', str(bundle.resolve()), version['bundle_ref']], cwd=dest, check=True)
    subprocess.run(['git', 'checkout', '--detach', version['source_commit']], cwd=dest, check=True)
    for expression, expected in (('HEAD', version['source_commit']), ('HEAD^{tree}', version['source_tree'])):
        assert subprocess.check_output(['git', 'rev-parse', expression], cwd=dest, text=True).strip() == expected
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=dest)
    return dict(restored=str(dest), head=version['source_commit'], tree=version['source_tree'], clean=True, model_starts=0)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-repository', required=True); p.add_argument('--destination', required=True)
    a = p.parse_args()
    print(json.dumps(restore(a.base_repository, a.destination), ensure_ascii=False))
