"""指示18の登録機械と原関門を読む。模型・合格札・原索引は書き換えない。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import sys
from urllib.request import Request, urlopen

COMMON = ('machine_type', 'cpu_type', 'os_image', 'python',
          'package_sha256', 'version_sha')
IDENTITY = ('host', 'machine_id_sha256', 'boot_id_sha256')
C = 'c4cfed12a3944071951775b2c9373ca27705fb25'
CROSS_PHASES = {'receive', 'replay', 'measure'}
CROSS_GATES = {'gate-on1-f0.1.json', 'gate-on1-f0.9.json',
               'gate-receive-replay.json', 'gate-off8-parallel.json'}
LOCAL_GATES = ('gate-components.json', 'gate-off2.json', 'gate-off8.json',
               'gate-off8-parallel.json')


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def child_path(root, relative):
    assert isinstance(relative, str) and not Path(relative).is_absolute()
    p = (root / relative).resolve()
    assert p.is_relative_to(root.resolve()), '証拠の所在がrootの外'
    return p


def package_fingerprint(package):
    # 正規原索引が確定してから、デスクトップが同一の包みの一覧を固定する。
    index = package / 'SHA256SUMS'
    text = index.read_text()
    assert not any(l.startswith(('<<<<<<<', '=======', '>>>>>>>'))
                   for l in text.splitlines()), '原索引の衝突は未解決'
    listed = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        assert match, '原索引の形式が未確定'
        digest, name = match.groups()
        assert name not in listed, '原索引の重複'
        assert sha(child_path(package, name)) == digest, (name, '原索引のSHA不一致')
        listed[name] = digest
    assert listed, '原索引が空'
    manifest = package / 'PACKAGE_MANIFEST_instruction18.json'
    data = read(manifest)
    assert data['schema'] == 1 and isinstance(data['files'], dict)
    required = {'SHA256SUMS', 'run.py', 'compare.py', 'processes.py',
                'observe_independent.py', 'runtime_capture.py',
                'observe_independent_spawn15.py', 'run_spawn15.py',
                'run_cohort18.py', 'cohort18.py', 'measurement_cohort18.py'}
    assert required <= data['files'].keys()
    assert listed.keys() <= data['files'].keys(), '原索引の全行を包みの指紋に残す'
    for name, digest in data['files'].items():
        assert re.fullmatch('[0-9a-f]{64}', digest)
        assert sha(child_path(package, name)) == digest, (name, '包みのSHA不一致')
    return sha(manifest)


def metadata(key):
    req = Request('http://metadata.google.internal/computeMetadata/v1/' + key,
                  headers={'Metadata-Flavor': 'Google'})
    with urlopen(req, timeout=3) as response:
        assert response.headers.get('Metadata-Flavor') == 'Google'
        value = response.read(65536).decode().strip()
    assert value
    return value


def fingerprint(package):
    assert sys.platform.startswith('linux') and sys.version_info[:2] == (3, 12)
    machine = Path('/etc/machine-id').read_bytes()
    boot = Path('/proc/sys/kernel/random/boot_id').read_bytes()
    cpus = sorted({l.split(':', 1)[1].strip()
                   for l in Path('/proc/cpuinfo').read_text().splitlines()
                   if l.startswith('model name')})
    assert len(cpus) == 1, 'CPU型が一意でない'
    return dict(machine_type=metadata('instance/machine-type').split('/')[-1],
                cpu_type=cpus[0], os_image=metadata('instance/image'),
                python=dict(version=sys.version, implementation=platform.python_implementation(),
                            executable_sha256=sha(Path(sys.executable))),
                package_sha256=package_fingerprint(package), version_sha=C,
                machine_id_sha256=hashlib.sha256(machine).hexdigest(),
                boot_id_sha256=hashlib.sha256(boot).hexdigest(),
                host=hashlib.sha256(machine + boot).hexdigest())


def registry(root, package, current_host):
    p = root / 'machine_registry_instruction18.json'
    x = read(p)
    assert x['schema'] == 1 and x['direct_instruction18_authorization'] is True
    assert set(x['cohort']) == set(COMMON)
    assert all(x['cohort'][k] for k in COMMON)
    assert x['cohort']['version_sha'] == C
    members = {}
    for m in x['machines']:
        assert all(m[k] == x['cohort'][k] for k in COMMON), '同じ種類の機械でない'
        assert all(re.fullmatch('[0-9a-f]{64}', m[k]) for k in IDENTITY)
        assert m['host'] not in members, '機械の重複'
        fp = child_path(root, m['fingerprint_file'])
        assert sha(fp) == m['fingerprint_sha256']
        actual = read(fp)['fingerprint']
        assert all(actual[k] == m[k] for k in COMMON + IDENTITY), '機械指紋の控えと一覧が違う'
        members[m['host']] = m
    assert current_host in members, '現在の機械が一覧に無い'
    live = fingerprint(package)
    assert live['host'] == current_host
    assert all(live[k] == members[current_host][k] for k in COMMON + IDENTITY), '現在の機械の実指紋が違う'
    return x, members, dict(path=p.name, sha256=sha(p), fingerprint=live)


def proof(path, expected_host, candidate=C):
    g = read(path)
    assert g['passed'] is True and g['candidate'] == candidate, (path.name, '必要な関門が未合格')
    assert g['host'] == expected_host, (path.name, '機械と起動が違う')
    return dict(path=str(path), sha256=sha(path), host=g['host'])


def check_gates(s, root, package, current_host, complete_pilot):
    root, package = Path(root), Path(package)
    selected = {}
    phased = s['phase'] in {'on1', 'receive', 'replay', 'measure'}
    if not phased:
        for name in s['requires']:
            selected[name] = proof(root / 'gates' / name, current_host)
        return dict(required=selected, registry=None, local=None)
    x, members, reg = registry(root, package, current_host)
    local = {name: proof(root / 'gates' / name, current_host) for name in LOCAL_GATES}
    # 元compare.completeをそのまま使い、20件・原順・版・done実物理サイズ等を減らさない。
    runtime, resource, *_ = complete_pilot(root, 'on1_pilot20')
    assert runtime['host'] == resource['host'] == current_host
    assert runtime['phase'] == 'pilot' and runtime['commit'] == C
    assert int(runtime['argv'][runtime['argv'].index('--trial-count') + 1]) == 20
    local['pilot20'] = {name: sha(root / 'evidence/on1_pilot20' / name)
                        for name in ('runtime.json', 'resource.json')}
    for name in s['requires']:
        imported = x.get('imports', {}).get(name)
        if imported is not None:
            assert s['phase'] in CROSS_PHASES and name in CROSS_GATES, 'この段では別機械の前提を認めない'
            assert imported['host'] in members, '一覧に無い機械の証拠'
            path = child_path(root, imported['path'])
            assert sha(path) == imported['sha256'], '取り込んだ証拠のSHA不一致'
            selected[name] = proof(path, imported['host'])
        else:
            selected[name] = proof(root / 'gates' / name, current_host)
    return dict(required=selected, registry=reg, local=local)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('package', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    result = dict(checked_at=datetime.now(timezone.utc).isoformat(),
                  fingerprint=fingerprint(args.package.resolve()))
    with args.output.open('x') as f:
        f.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
