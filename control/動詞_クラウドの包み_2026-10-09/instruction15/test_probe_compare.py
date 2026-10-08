"""指示14の鍵でだけ試験行を除き、原行順の比較を保つ。模型は呼ばない。"""
from pathlib import Path
from random import Random
import gzip,hashlib,json
import pytest
import probe_compare as P

def sample(tmp_path,extra=False,bad_pair=False):
    rows=[{'kind':'pre','trial':99,'rng':{}},{'kind':'prediction','trial':99},{'kind':'post','trial':99}]
    native=[json.dumps(x).encode()+b'\n' for x in rows]
    candidate=native[:2];probes=[]
    for qi in range(48):
        probes.append({'t':100})
        seed=int.from_bytes(hashlib.sha256(f'probe\x1f1\x1f100\x1f{qi}'.encode()).digest()[:8],'big')
        candidate.append(json.dumps({'kind':'pre','trial':99,'rng':P.encoded_rng(Random(seed).getstate())}).encode()+b'\n')
        candidate.append(json.dumps({'kind':'prediction','trial':98 if bad_pair and qi==0 else 99}).encode()+b'\n')
    candidate+=native[2:]
    if extra:candidate.append(json.dumps({'kind':'pre','trial':99,'rng':{}}).encode()+b'\n')
    left=tmp_path/'l.gz';right=tmp_path/'r.gz';probe=tmp_path/'probe.jsonl'
    for name,data in [(left,native),(right,candidate)]:
        with gzip.open(name,'wb') as f:f.write(b''.join(data))
    probe.write_text('\n'.join(json.dumps(x) for x in probes)+'\n')
    return left,right,probe,native

def test_fixed_rng_not_line_position_and_raw_order_preserved(tmp_path):
    l,r,p,n=sample(tmp_path);before=[l.read_bytes(),r.read_bytes()]
    v=P.state_compare(l,r,p,1)
    assert v['equal'] and v['excluded_records']=={'left':0,'right':96} and v['excluded_pair_trial_counts']=={'99':48}
    assert v['left_sha256']==v['right_sha256']==hashlib.sha256(b''.join(n)).hexdigest()
    assert before==[l.read_bytes(),r.read_bytes()]
def test_unidentified_extra_line_is_not_excluded(tmp_path):
    l,r,p,n=sample(tmp_path,extra=True);v=P.state_compare(l,r,p,1)
    assert not v['equal'] and v['mismatching_rows']==1
def test_following_prediction_must_have_same_trial(tmp_path):
    l,r,p,n=sample(tmp_path,bad_pair=True)
    with pytest.raises(AssertionError):P.state_compare(l,r,p,1)
def test_speed200_probe96_cannot_use_exclusion(tmp_path):
    l,r,p,n=sample(tmp_path);p.write_text(p.read_text()*2)
    with pytest.raises(AssertionError):P.state_compare(l,r,p,1)
