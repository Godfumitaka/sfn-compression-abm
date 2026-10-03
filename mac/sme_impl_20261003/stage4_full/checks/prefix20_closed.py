"""完了した記録の先頭20行を、run_idだけ空にしてバイトで比べる。模型は呼ばない。"""
from pathlib import Path
from hashlib import sha256
import gzip
import json
import re

root = Path(__file__).resolve().parent
short = root.parent / 'stage3_learning_03/A'
full = root / 'A_seed1'
manifest = json.loads((full / 'manifest.jsonl').read_text())
assert not manifest.get('error') and manifest['smereplay']['updates'] == 1740

def read(folder):
    path = next(folder.glob('ledgers/cells/*/*.gz'))
    with gzip.open(path, 'rb') as stream:
        header = json.loads(stream.readline())
        lines = list(stream)
    return header, lines

hs, ls = read(short)
hf, lf = read(full)
assert len(ls) == 20 and len(lf) == 1740
pattern = rb'("run_id":)"(?:[^"\\]|\\.)*"'
def omit_run_id(line):
    result, count = re.subn(pattern, rb'\1""', line)
    assert count == 1
    return result

body_diff = sorted({key for a, b in zip(ls, lf[:20])
                    for key in set(json.loads(a)) | set(json.loads(b))
                    if json.loads(a).get(key) != json.loads(b).get(key)})
small_bytes = b''.join(map(omit_run_id, ls))
full_bytes = b''.join(map(omit_run_id, lf[:20]))
record = {
    'short_trials': len(ls), 'full_trials': len(lf), 'compared_trials': 20,
    'full_run_finished': True, 'byte_equal_after_one_field': small_bytes == full_bytes,
    'excluded_body_fields': ['run_id'], 'differing_body_fields': body_diff,
    'header_different_fields': sorted(k for k in set(hs) | set(hf) if hs.get(k) != hf.get(k)),
    'short_body_sha_after_one_field': sha256(small_bytes).hexdigest(),
    'full_prefix_sha_after_one_field': sha256(full_bytes).hexdigest(),
}
(root / 'prefix20_closed.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(record, ensure_ascii=False))
assert record['byte_equal_after_one_field'], '完了した全走行の先頭20試行が違う'
