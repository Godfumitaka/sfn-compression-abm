"""gzip容器だけを外し、中身の列順は関門に残す。"""
from pathlib import Path
import gzip
import json
import sys
import pytest

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools')]
from uposition_compare import compare


def pair(tmp_path):
    roots=[tmp_path/'reference',tmp_path/'current']
    for i,root in enumerate(roots):
        side=root/'output/side/cell';side.mkdir(parents=True)
        for path,value in [(side/'seed001.sme.states.jsonl.gz',b'{}\n'*5220),
                           (root/'saved_matcher.jsonl.gz',b'{"nodes":[1,2]}\n')]:
            with path.open('wb') as f:
                with gzip.GzipFile(fileobj=f,mode='wb',mtime=100+i) as z:z.write(value)
        (root/'tie_state.jsonl').write_text('{}\n'*1740)
    return roots


def test_container_time_does_not_fail_gate(tmp_path):
    a,b=pair(tmp_path);out=tmp_path/'proof'
    compare(a,b,out)
    proof=json.loads((out/'gate1.json').read_text())
    assert proof['passed']
    assert any(not row['bytes_equal'] for row in proof['files'])


def test_node_order_difference_still_fails_gate(tmp_path):
    a,b=pair(tmp_path);out=tmp_path/'proof'
    with gzip.open(b/'saved_matcher.jsonl.gz','wb') as f:f.write(b'{"nodes":[2,1]}\n')
    with pytest.raises(SystemExit) as error:compare(a,b,out)
    assert error.value.code==3 and not json.loads((out/'gate1.json').read_text())['passed']
