"""指示25の指定欄だけを、原成分の証拠を保持して扱う。"""
from pathlib import Path
import hashlib,json,re
HERE=Path(__file__).resolve().parent
PORT=HERE.parent

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while raw:=stream.read(1024*1024):h.update(raw)
    return h.hexdigest()

def component_proof():
    evidence=PORT/'instruction24/component_comparison_03.json'
    result=json.loads(evidence.read_text())
    assert result['state']=='stopped' and result['all_side_probe_before_after_equal'] and result['all_original_snapshots_reconstructed']
    checks=result['checks'];assert len(checks)==8
    assert {(c['trial'],c['phase'],c['component']) for c in checks}=={(t,p,c) for t in (100,200) for p in ('before','after') for c in ('D.ST','AUDIT')}
    captures={};confirmed=[];original_files={}
    for c in checks:
        assert c['non_record_port_keys_equal']
        nonports=[k for k in c['all_keys'] if 'record_ports' not in k]
        assert len(nonports)==(12 if c['component']=='D.ST' else 10)
        ports=[k for k in c['all_keys'] if 'record_ports' in k]
        assert len(ports)==1 and ports[0]['key_repr']=="'f'"
        for key in c['all_keys']:
            a,b=Path(key['left_file']),Path(key['right_file'])
            original_files[str(a)]=digest(a);original_files[str(b)]=digest(b)
            if 'record_ports' not in key:assert a.read_bytes()==b.read_bytes() and key['raw_bytes_equal']
            else:
                rec=key['record_ports'];assert rec['raw_file_bytes_equal'] and rec['position_equal'] and rec['type_mode_encoding_closed_equal']
                lp,rp=rec['left'],rec['right']
                assert all(lp[k]==rp[k] for k in ('position','type_name','mode','encoding','closed','raw_bytes','raw_sha256'))
                av,bv=a.read_bytes(),b.read_bytes()
                assert av.replace(b'/left_tau04_200_02/',b'/right_tau04_200_02/')==bv
                for p,port in [(a,lp),(b,rp)]:
                    q=p.parent/port['raw_file'];assert digest(q)==port['raw_sha256'] and q.stat().st_size==port['raw_bytes'];original_files[str(q)]=digest(q)
        for side in ('left','right'):
            q=Path(c[side+'_file']);folder=q.parent;meta=json.loads((folder/'components.json').read_text())
            assert meta['original_snapshot_reconstructed_exactly'] and not meta['model_state_restored'] and not meta['model_record_ports_flushed']
            assert digest(q)==meta['components'][c['component']]['raw_sha256']
            original_files[str(q)]=digest(q);original_files[str(folder/'components.json')]=digest(folder/'components.json')
            raw=folder/'native_snapshot.original.bin';assert digest(raw)==meta['snapshot_sha256'];original_files[str(raw)]=digest(raw)
            captures[(side,c['trial'],c['phase'])]=raw
        confirmed.append(dict(trial=c['trial'],phase=c['phase'],component=c['component'],non_record_port_count=len(nonports),non_record_port_raw_bytes_equal=True,all_record_port_properties_and_original_bytes_equal=True,only_original_absolute_output_name_differs=True))
    for side in ('left','right'):
        case=PORT/'instruction24'/(side+'_tau04_200_02')
        verified=json.loads((PORT/'instruction24'/(side+'_tau04_200_02_verification_03.json')).read_text());assert verified['status']=='passed'
        rows=json.loads(next((case/'output/retention').rglob('*.probe_checks.json')).read_text());assert [x['trial']for x in rows]==[100,200]
        for row in rows:
            a=captures[(side,row['trial'],'before')];b=captures[(side,row['trial'],'after')]
            assert a.read_bytes()==b.read_bytes()
            assert row['unchanged'] and row['before_sha256']==row['after_sha256']==digest(a)
    return dict(passed=True,source=str(evidence),source_sha256=digest(evidence),checks=confirmed,all_side_before_after_equal=True,original_files_sha256=original_files,reason='指示25：全非記録口原字節と記録口位置・原ファイル字節・型/mode/encoding/closedは一致。既存fのreprの絶対出力先名だけの差。')

def probe_row(rel,left,right,proof,excluded,byte_row):
    assert proof['passed'] and str(rel).endswith('.probe_checks.json') and rel.parts[0]=='retention'
    raw=[left.read_bytes(),right.read_bytes()];records=[json.loads(x) for x in raw]
    assert all([x['trial']for x in rows]==[100,200] for rows in records)
    pattern=re.compile(rb'("(before_sha256|after_sha256)"\s*:\s*)"([a-f0-9]{64})"')
    normalized=[]
    for side,path,data,rows in zip(('left','right'),(left,right),raw,records):
        assert all(row['unchanged'] and row['before_sha256']==row['after_sha256'] for row in rows)
        matches=list(pattern.finditer(data));assert len(matches)==4
        for index,m in enumerate(matches):
            field=m.group(2).decode();value=m.group(3).decode();trial=rows[index//2]['trial']
            assert value==rows[index//2][field]
            excluded.append(dict(side=side,file=str(path),line=data[:m.start()].count(b'\n')+1,field=field,trial=trial,original_value=value,reason=proof['reason'],component_evidence=proof['source'],component_evidence_sha256=proof['source_sha256']))
        normalized.append(pattern.sub(lambda m:m.group(1)+b'"'+b'0'*64+b'"',data))
    row=byte_row(rel,*normalized,mode='指示25のbefore_sha256/after_sha256だけを原成分証拠へ置換。全残余原字節。')
    row['original_sha256']=[hashlib.sha256(x).hexdigest() for x in raw]
    row['component_substitution_passed']=True
    return row
