"""P10の本体を読み込まず、元の観測へ後から同じ試行境界の捨て方を当てる。

種の試行は元sideのsme_resultからだけ読み、最終控えの挿入順と
各試行の原件数から、境界で消す前の行を特定する。欠けた根拠は補わない。
"""
from pathlib import Path
import gzip
import hashlib
import json
import sqlite3
import sys


def seed_of(encoded):
    if not isinstance(encoded,dict) or encoded.get('tag')!='tuple': return None
    items=encoded['items']
    return str(items[-1]) if len(items)>=2 and items[-2]=='call-seed-v1' else None


def convert(reference, destination):
    reference,destination=Path(reference),Path(destination)
    destination.mkdir(exist_ok=False)
    db=sqlite3.connect(destination/'ordered_reference.sqlite')
    db.execute('CREATE TABLE origins(seed TEXT PRIMARY KEY, trial INTEGER NOT NULL)')
    db.execute('CREATE TABLE rows(section TEXT, ordinal INTEGER, origin INTEGER, seed TEXT, digest_bytes BLOB)')
    for file in sorted((reference/'output/side').glob('**/*.sme.jsonl.gz')):
        with gzip.open(file,'rt',encoding='utf-8') as stream:
            for line in stream:
                row=json.loads(line)
                if row.get('kind')!='sme_result' or row.get('version')!='sme-cstar-expectation-1': continue
                if 'tie_seed' not in row or 'trial' not in row: raise RuntimeError('原C*の呼び出し種又は試行が無い')
                seed,trial=str(row['tie_seed']),row['trial']
                previous=db.execute('SELECT trial FROM origins WHERE seed=?',(seed,)).fetchone()
                if previous and previous[0]!=trial: raise RuntimeError('同じ種の由来の試行が複数ある')
                if not previous: db.execute('INSERT INTO origins VALUES (?,?)',(seed,trial))
    count={'cstar_cache':0,'cstar_cache_rng':0}
    with gzip.open(reference/'saved_matcher.jsonl.gz','rb') as stream:
        for line in stream:
            row=json.loads(line); section=row['section']
            if section not in count: continue
            seed=seed_of(row['key']);origin=None
            if seed is not None:
                found=db.execute('SELECT trial FROM origins WHERE seed=?',(seed,)).fetchone()
                if found is None: raise RuntimeError(('原観測の控えに試行の根拠が無い',seed))
                origin=found[0]
            digest=json.dumps([row['key'],row['value']],ensure_ascii=False,separators=(',',':')).encode()
            db.execute('INSERT INTO rows VALUES (?,?,?,?,?)',(section,count[section],origin,seed,digest))
            count[section]+=1
    db.commit()
    trials=0;last=None
    with (reference/'tie_state.jsonl').open('rb') as src,(destination/'tie_state.jsonl').open('xb') as dst:
        for line in src:
            row=json.loads(line); trial=row['trial']; eng=row['engines']['cstar']
            if last is not None and trial<=last: raise RuntimeError('原試行が昇順でない')
            for section,field in [('cstar_cache','cache_count'),('cstar_cache_rng','cache_rng_count')]:
                original_count=eng[field]
                if original_count>count[section]: raise RuntimeError('原控えの件数が最終保存を超える')
                seen=0;digest=hashlib.sha256();old_digest=hashlib.sha256()
                for origin,content in db.execute('SELECT origin,digest_bytes FROM rows WHERE section=? AND ordinal<? ORDER BY ordinal',
                                                (section,original_count)):
                    if origin is not None and origin>trial: raise RuntimeError('未来の行が試行の控えにある')
                    if section=='cstar_cache_rng': old_digest.update(content)
                    if origin is None or origin==trial:
                        seen+=1
                        if section=='cstar_cache_rng': digest.update(content)
                if section=='cstar_cache_rng':
                    if old_digest.hexdigest()!=eng['cache_rng_sha256']:
                        raise RuntimeError('元のcache_rngの順つきsha256を独立に復元できない')
                    eng['cache_rng_sha256']=digest.hexdigest()
                eng[field]=seen
            dst.write((json.dumps(row,ensure_ascii=False)+'\n').encode())
            trials+=1;last=trial
    if last is None: raise RuntimeError('原控え観測の試行が無い')
    kept=removed=0
    with gzip.open(reference/'saved_matcher.jsonl.gz','rb') as src,gzip.open(destination/'saved_matcher.jsonl.gz','wb') as dst:
        for line in src:
            row=json.loads(line);seed=seed_of(row.get('key'))
            if row['section'] in count and seed is not None:
                origin=db.execute('SELECT trial FROM origins WHERE seed=?',(seed,)).fetchone()[0]
                if origin!=last: removed+=1;continue
            dst.write(line);kept+=1
    result=dict(passed=True,reference=str(reference),trials=trials,last_trial=last,
                original_cache_rows=count,kept_saved_rows=kept,removed_saved_rows=removed,
                original_rng_digest_reconstructed=True,order_preserved=True,
                model_files_changed=False,P10_body_imported=False)
    (destination/'transformation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    db.close();return result


if __name__=='__main__':
    print(json.dumps(convert(sys.argv[1],sys.argv[2]),ensure_ascii=False))
