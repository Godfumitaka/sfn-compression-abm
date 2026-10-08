"""委任書46の固定した種1だけを、新しい土台で読み直す全バイト関門。

模型を走らせず、旧形式の結果を順序も欄も変えずに照合する。
最初の不一致で停止し、修正・並べ替え・許容差を追加しない。
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
import time

SOURCE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE)]
NEW_FLAGS = ('match_cstar', 'select_cstar', 'sme_online', 'sme_fast',
             'score_logp', 'tie_random', 'attn', 'attn_stage2', 'stage2_birth_hu',
             'stage2_rematch_reuse', 'sme_gc_every', 'dump_sme_fast_encode', 'no_forget')


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1048576), b''):
            h.update(data)
    return h.hexdigest()


def compare(left, right):
    opener = gzip.open if left.suffix == '.gz' else open
    position = 0
    with opener(left, 'rb') as a, opener(right, 'rb') as b:
        while True:
            x, y = a.read(1048576), b.read(1048576)
            if x != y:
                first = next((i for i, pair in enumerate(zip(x, y)) if pair[0] != pair[1]), min(len(x), len(y)))
                return dict(match=False, first_byte=position + first,
                            reference_sample=x[max(0, first-40):first+80].hex(),
                            ported_sample=y[max(0, first-40):first+80].hex())
            position += len(x)
            if not x:
                return dict(match=True, compared_bytes=position, gzip_expanded=left.suffix == '.gz')


def material(label, workspace):
    old = workspace / 'codex_seal_intervention_2026-10-04'
    attention = workspace / 'codex_attn_2026-10-03'
    if label == 'N3_w1':
        return attention / 'world1_rebuild/n3_w1_A_L50', 1
    if label == 'N3_w2':
        return attention / 'material_rebuild_2026-10-04/n3_w2_A_L50', 2
    if label in ('fg_f050_A_L50', 'fg_f050_C_L50', 'lg_w2_A_lam0.065'):
        return old / 'memory_rebuild_2026-10-05' / label, None
    raise ValueError('固定した五件以外を走らせない')


def one(reference, destination, workspace):
    import seal_intervention_diag as diagnostic
    import seal_intervention_batch as batch
    import seal_mac_intervention as mac
    label = reference['label']
    if reference['seed'] != 1:
        raise ValueError('この関門は種1だけ')
    root, world = material(label, workspace)
    flags = json.loads((root / 'flag.json').read_text())
    if any(flags.get(k) for k in NEW_FLAGS):
        raise ValueError('旧材料に新しい旗が入っている')
    for entry in reference['files']:
        path = Path(entry['path'])
        if path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
            raise RuntimeError('準備で固定した比較元の指紋が違う')
    before = batch.fingerprints(root, 1)
    destination.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    batch.ATTN = workspace / 'codex_attn_2026-10-03'
    batch.ROOTS = {world: root} if world else {}
    if world:
        diagnostic.one(root, destination, 1, all_doors=True)
        batch.export(world, 1, destination)
    else:
        mac.one(root, destination, 1)
    after = batch.fingerprints(root, 1)
    if before != after:
        raise RuntimeError('旧入力の全バイトが変わった')
    comparisons = []
    for entry in reference['files']:
        path = Path(entry['path'])
        result = dict(file=path.name, reference=str(path), ported=str(destination / path.name),
                      **compare(path, destination / path.name))
        comparisons.append(result)
        if not result['match']:
            save(destination / 'off_gate.json', dict(status='stopped_mismatch', label=label,
                 comparisons=comparisons, inputs_unchanged=True, input_files=len(before)))
            raise RuntimeError('全バイト関門の不一致。修正せず停止：' + json.dumps(result, ensure_ascii=False))
    proof = dict(status='passed', label=label, seed=1, comparisons=comparisons,
                 inputs_unchanged=True, input_files=len(before), input_fingerprints=before,
                 seconds=time.perf_counter()-started)
    save(destination / 'off_gate.json', proof)
    return proof


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('references', type=Path)
    ap.add_argument('destination', type=Path)
    ap.add_argument('--workspace', type=Path, required=True)
    ap.add_argument('--case')
    a = ap.parse_args()
    os.chdir(SOURCE)
    references = json.loads(a.references.read_text())
    if a.case:
        entries = [r for r in references if r['label'] == a.case]
        if len(entries) != 1:
            raise ValueError('固定した比較元の一件を指定する')
        print(json.dumps(one(entries[0], a.destination, a.workspace), ensure_ascii=False))
        return
    a.destination.mkdir(parents=True, exist_ok=False)
    results = []
    save(a.destination / 'status.json', dict(status='running', completed=[], pid=os.getpid()))
    for entry in references:
        command = [sys.executable, __file__, str(a.references.resolve()),
                   str(a.destination.resolve()/entry['label']), '--workspace', str(a.workspace),
                   '--case', entry['label']]
        with (a.destination / (entry['label'] + '.log')).open('w') as log:
            proc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if proc.returncode:
            save(a.destination / 'status.json', dict(status='stopped', failed=entry['label'],
                 returncode=proc.returncode, completed=results, retry_authorized=False))
            raise SystemExit(proc.returncode)
        results.append(json.loads((a.destination/entry['label']/'off_gate.json').read_text()))
        save(a.destination / 'status.json', dict(status='running', completed=results, pid=os.getpid()))
    save(a.destination / 'status.json', dict(status='passed', completed=results, fixed_cases=5))


if __name__ == '__main__':
    main()
