"""指示26：保存済みの時間記録だけを読む。模型をimport・実行しない。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib, json, resource, time

W = Path('/Users/tatsu-admin/Documents/ChatGPT/New project')
T = W / 'codex_intervention_port_2026-10-07'
HERE = T / 'instruction26'
started = time.perf_counter()
fingerprints = {}

def read(path):
    raw = path.read_bytes()
    fingerprints[str(path)] = hashlib.sha256(raw).hexdigest()
    return raw

def records(path):
    return [json.loads(line) for line in read(path).splitlines() if line.strip()]

cases = {}
for name, root in {
    'B5_c4_on200': T/'instruction12/B5/B5_on200_before',
    'B5_929_on200': T/'instruction12/B5/B5_on200_after',
    'B5_c4_on20': T/'instruction12/B5/B5_pilot20_before_dependency01',
    'B6_e96_flags_off_on200': T/'instruction21/B6_gate_03/B6_off_on200_candidate03',
}.items():
    status = json.loads(read(root/'status.json'))
    rows = records(root/'agent0.performance.jsonl')
    blocks = []
    for lo in range(0,len(rows),100):
        group = rows[lo:lo+100]
        last = group[-1]['elapsed_seconds']
        initial = rows[lo-1]['elapsed_seconds'] if lo else 0.0
        checkpoints = [r for r in group if (r['trial']+1)%100 == 0]
        rest = [r for r in group if (r['trial']+1)%100 != 0]
        blocks.append(dict(trials_zero_based=[group[0]['trial'],group[-1]['trial']],
            count=len(group),elapsed_delta=last-initial,
            trial_seconds_including_wait_and_probe_sum=sum(r['seconds_including_wait_and_probe'] for r in group),
            checkpoint_seconds_including_trial=sum(r['seconds_including_wait_and_probe'] for r in checkpoints),
            noncheckpoint_seconds=sum(r['seconds_including_wait_and_probe'] for r in rest),
            checkpoint_rows=checkpoints,
            last_noncheckpoint_mean20=sum(r['seconds_including_wait_and_probe'] for r in rest[-20:])/len(rest[-20:]) if rest else None,
            active_seconds_increments=[group[-1].get('active_seconds'),rows[lo-1].get('active_seconds') if lo else 0],
            last_timer_totals=group[-1].get('timer_totals')))
    cases[name]=dict(root=str(root),status=status,records=len(rows),blocks=blocks,
        first=rows[0],last=rows[-1],record_time_basis='個体のelapsed_secondsは実時間。seconds_including_wait_and_probeは試行の待ちと試験も含む。active_secondsを純模型CPUと仮定しない。')

old8 = {}
for rel in ['sme-evict-20261007/q0_8_evict200','sme-evict-20261007/q0_8_plain200',
            'new-port-20261007/off_q0_8_200']:
    root=W/'codex_coll8_2026-10-03/evidence'/rel
    agents={}
    for p in sorted(root.glob('agent*.performance.jsonl')):
        rows=records(p)
        blocks=[]
        for lo in range(0,len(rows),100):
            g=rows[lo:lo+100]
            last=g[-1].get('elapsed_seconds')
            previous=rows[lo-1].get('elapsed_seconds',0) if lo else 0
            blocks.append(dict(count=len(g),elapsed_delta=last-previous if last is not None else None,
                active_seconds=g[-1].get('active_seconds'),first=g[0],last=g[-1]))
        agents[p.stem]=dict(count=len(rows),blocks=blocks)
    old8[rel]=dict(root=str(root),agents=agents,
        comparable_to_allin=False,reason='旧版又は新旗off、価格・通信・監査条件差。全部入りの倍率には代用しない。')

specs={}
for p in sorted((T/'instruction21/production_specs_01').glob('*.json')):
    d=json.loads(read(p)); argv=d['model_argv']
    def option(name):return argv[argv.index(name)+1] if name in argv else None
    specs[p.name]=dict(commit=d['commit'],models=d['models'],seeds=d['seeds'],
        serial='--v311c-serial' in argv,parallel_metadata=d['parallel'],
        stage2=option('--stage2'),birth_hu=option('--stage2-birth-hu'),tau=option('--use-forget'),
        f=option('--v311c-f'),q=option('--v311c-q'),m=option('--v311c-m'),
        B=option('--v39-price'),E=option('--e-price'),trial_count=option('--trial-count'),
        horizon=option('--horizon'),probe_every=option('--v311c-probe-every'))

unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in fingerprints.items())
result=dict(at_jst=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(),cases=cases,old8=old8,
    production_drafts=specs,input_sha256=fingerprints,input_unchanged=unchanged,
    new_model_starts=0,seconds=time.perf_counter()-started,max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    cloud_A_B2_per100='未測定：当地に実performance原記録が無い。公開報告の全200実時間だけ別に読む。',
    allin_eight_body_parallel_efficiency='未測定',human_D_on_collective200='未測定')
(HERE/'existing_times_analysis_01.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(input_unchanged=unchanged,new_model_starts=0,seconds=result['seconds'],max_rss_bytes=result['max_rss_bytes'])))
assert unchanged
