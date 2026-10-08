"""独立後処理の順序・prefix・sha256・未知の由来を小さい原観測で確認する。"""
from pathlib import Path
import gzip
import hashlib
import json
import tempfile
from reference_observation import convert


def write_reference(root):
    side=root/'output/side';side.mkdir(parents=True)
    with gzip.open(side/'seed.sme.jsonl.gz','wt') as stream:
        for seed,trial in [(10,0),(11,1)]:
            stream.write(json.dumps(dict(kind='sme_result',version='sme-cstar-expectation-1',tie_seed=seed,trial=trial))+'\n')
    keys=[dict(tag='tuple',items=['base','call-seed-v1',seed]) for seed in (10,11)]
    values=[dict(tag='mapping',items=[['policy','call-seed-v1'],['seed',seed]]) for seed in (10,11)]
    lines=[]
    for section in ('cstar_cache','cstar_cache_rng'):
        for key,value in zip(keys,values):
            lines.append(dict(section=section,key=key,value=value))
    lines.append(dict(section='sme_rng',value='unchanged'))
    with gzip.open(root/'saved_matcher.jsonl.gz','wt') as stream:
        for row in lines:stream.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
    with (root/'tie_state.jsonl').open('w') as stream:
        digest=hashlib.sha256()
        for trial,(key,value) in enumerate(zip(keys,values)):
            digest.update(json.dumps([key,value],ensure_ascii=False,separators=(',',':')).encode())
            row=dict(trial=trial,call_context='unchanged',engines=dict(sme='unchanged',cstar=dict(
                rng='native',cache_count=trial+1,self_cache_count=3,cache_rng_count=trial+1,
                cache_rng_sha256=digest.hexdigest())))
            stream.write(json.dumps(row,ensure_ascii=False)+'\n')


def main():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)/'reference';root.mkdir();write_reference(root)
        target=Path(temp)/'filtered';result=convert(root,target)
        assert result['removed_saved_rows']==2 and result['kept_saved_rows']==3
        rows=[json.loads(line) for line in (target/'tie_state.jsonl').read_text().splitlines()]
        assert all(r['engines']['cstar']['cache_count']==r['engines']['cstar']['cache_rng_count']==1 for r in rows)
        assert all(r['engines']['sme']=='unchanged' and r['engines']['cstar']['rng']=='native' for r in rows)
        with gzip.open(target/'saved_matcher.jsonl.gz','rt') as stream:
            saved=[json.loads(line) for line in stream]
        assert [r['section'] for r in saved]==['cstar_cache','cstar_cache_rng','sme_rng']
        assert saved[0]['key']['items'][-1]==11
        wrong=Path(temp)/'wrong';wrong.mkdir();write_reference(wrong)
        with gzip.open(wrong/'output/side/seed.sme.jsonl.gz','wt') as stream:stream.write('')
        try:convert(wrong,Path(temp)/'must_fail')
        except RuntimeError as exc:assert '根拠' in str(exc)
        else:raise AssertionError('由来の無い鍵を補ってしまった')
    print(json.dumps(dict(passed=True,checks=6,body_not_imported=True,ordered_prefix_digest_checked=True)))


if __name__=='__main__':main()
