"""指示24：全原成分を照合し、最初の原字節の差を残す。正規化しない。"""
from pathlib import Path
import datetime,hashlib,json,resource,sys,time

HERE=Path(__file__).resolve().parent
destination=HERE/'component_comparison_03.json'
assert not destination.exists()
began=time.perf_counter()
result=dict(state='running',passed=False,model_changed=False,probe_hash_fields_excluded=False,
    decision_before_results=str(HERE/'gate_plan_01.json'),checks=[])

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def difference(left,right):
    offset=next((i for i,(a,b)in enumerate(zip(left,right))if a!=b),min(len(left),len(right)))
    return dict(byte_offset_zero_based=offset,line_one_based=left[:offset].count(b'\n')+1,
        left_bytes=len(left),right_bytes=len(right),left_sha256=sha(left),right_sha256=sha(right),
        left_hex=left[max(0,offset-32):offset+96].hex(),right_hex=right[max(0,offset-32):offset+96].hex())

cases={side:HERE/(side+'_tau04_200_02') for side in ('left','right')}
snapshots={}
try:
    specs=json.loads((HERE/'commands_02.json').read_text())
    for side,case in cases.items():
        status=json.loads((case/'status.json').read_text())
        assert status['state']=='completed' and status['exit_code']==0 and status['protected_unchanged']
        assert status['command']==specs[side+'_tau04_200_02']
        verified=json.loads((HERE/(side+'_tau04_200_02_verification_03.json')).read_text())
        assert verified['status']=='passed'
        folders=sorted((case/'components').glob('pid*_trial*'))
        assert len(folders)==4
        snapshots[side]={}
        probe_path=next((case/'output/retention').rglob('*.probe_checks.json'))
        probe_checks=json.loads(probe_path.read_text())
        assert [x['trial']for x in probe_checks]==[100,200]
        for folder in folders:
            meta=json.loads((folder/'components.json').read_text())
            assert meta['original_snapshot_reconstructed_exactly']
            assert meta['model_state_restored'] is meta['model_record_ports_flushed'] is False
            raw=(folder/'native_snapshot.original.bin').read_bytes()
            assert sha(raw)==meta['snapshot_sha256']
            expected=next(x for x in probe_checks if x['trial']==meta['trial'])
            assert expected['unchanged'] and expected['before_sha256']==expected['after_sha256']==sha(raw)
            snapshots[side][(meta['trial'],meta['phase'])]=(folder,meta)
            for label,component in meta['components'].items():
                assert sha((folder/component['raw_file']).read_bytes())==component['raw_sha256']
                for entry in component['entries']:
                    i=entry['index']
                    assert (folder/f'{label}.key{i:03d}.bin').read_bytes()==entry['key_repr'].encode()
                    assert sha((folder/f'{label}.value{i:03d}.bin').read_bytes())==entry['value_sha256']
            for port in meta['record_ports']:
                raw=(folder/port['raw_file']).read_bytes()
                assert len(raw)==port['raw_bytes'] and sha(raw)==port['raw_sha256']
        for trial in (100,200):
            before=snapshots[side][(trial,'before')][0]
            after=snapshots[side][(trial,'after')][0]
            for name in ['native_snapshot.original.bin','D.ST.original_repr.bin','AUDIT.original_repr.bin']:
                assert (before/name).read_bytes()==(after/name).read_bytes()
    first=None
    for trial in (100,200):
        for phase in ('before','after'):
            left,lmeta=snapshots['left'][(trial,phase)]
            right,rmeta=snapshots['right'][(trial,phase)]
            for label in ('D.ST','AUDIT'):
                lraw=(left/(label+'.original_repr.bin')).read_bytes()
                rraw=(right/(label+'.original_repr.bin')).read_bytes()
                entries_l=lmeta['components'][label]['entries']
                entries_r=rmeta['components'][label]['entries']
                assert [e['key_repr']for e in entries_l]==[e['key_repr']for e in entries_r]
                keys=[]
                for le,re in zip(entries_l,entries_r):
                    i=le['index'];assert i==re['index']
                    a=(left/f'{label}.value{i:03d}.bin').read_bytes()
                    b=(right/f'{label}.value{i:03d}.bin').read_bytes()
                    item=dict(key_repr=le['key_repr'],raw_bytes_equal=a==b,
                        left_file=str(left/f'{label}.value{i:03d}.bin'),right_file=str(right/f'{label}.value{i:03d}.bin'))
                    lp=le.get('record_port');rp=re.get('record_port')
                    assert bool(lp)==bool(rp)
                    if a!=b:item['difference']=difference(a,b)
                    if lp:
                        item['record_ports']=dict(left=lp,right=rp,
                            raw_file_bytes_equal=(left/lp['raw_file']).read_bytes()==(right/rp['raw_file']).read_bytes(),
                            position_equal=lp['position']==rp['position'],
                            type_mode_encoding_closed_equal=all(lp[k]==rp[k]for k in ('type_name','mode','encoding','closed')))
                    keys.append(item)
                check=dict(trial=trial,phase=phase,component=label,raw_bytes_equal=lraw==rraw,
                    left_file=str(left/(label+'.original_repr.bin')),right_file=str(right/(label+'.original_repr.bin')),
                    all_keys=keys,non_record_port_keys_equal=all(x['raw_bytes_equal']for x in keys if 'record_ports'not in x))
                if lraw!=rraw:
                    check['difference']=difference(lraw,rraw)
                    if first is None:first=check
                result['checks'].append(check)
    result.update(all_side_probe_before_after_equal=True,all_original_snapshots_reconstructed=True,
        first_original_component_difference=first,
        state='stopped' if first else 'components_equal',passed=first is None,
        decision='24.3(b)：D.ST又はAUDITの全原字節に差。原字節を除外せず停止' if first else '原成分は一致。記録口の差と24.3(a)の適合を別途判断',
        subsequent_model_or_comparison_started=False)
except BaseException as error:
    result.update(state='stopped',error=repr(error))
    raise
finally:
    result.update(at_jst=datetime.datetime.now().astimezone().isoformat(),seconds=time.perf_counter()-began,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items()if k not in ('checks','first_original_component_difference')},ensure_ascii=False))
sys.exit(0 if result['passed'] else 1)
