"""受け箱・列・既存処理を読むだけの30分確認。模型を起動しない。"""
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
import fcntl, json, re, subprocess, sys

R = Path(__file__).resolve().parent
TIME = R.parent / 'codex_sme_time_evict_2026-10-06'
REPO = R.parent / 'codex_worldv4_2026-10-01/results'
LOCK = R.parent / 'codex_sme_light_2026-10-04/control_writer_01.lock'
sys.path.insert(0, str(TIME))
sys.path.insert(0, str(R.parent / 'codex_logp_main_2026-10-06'))
from common_01 import conditions, ps
from cpu_guard_05 import cpu_reading

phase = sys.argv[1]
assert re.fullmatch(r'heartbeat_\d{8}_\d{4}', phase)
target = R / (phase + '.json')
assert not target.exists(), '同じ確認の上書きはしない'
def git(*args):
    p = subprocess.run(['git', *args], cwd=REPO, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return p.stdout
try:
    with LOCK.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert not git('status', '--porcelain').strip(), '汚れた作業状態。解決しない'
        git('fetch', 'origin', 'results-2026-09-27')
        git('rebase', 'origin/results-2026-09-27')
        commit = git('rev-parse', 'origin/results-2026-09-27').strip()
        files = {}
        for path in ['control/受け箱/README.md', 'control/受け箱/SMEの係.md', 'control/走行の列_2026-10-08.md']:
            files[path] = git('show', commit + ':' + path)
    status = json.loads((TIME / 'priority_status.json').read_text())
    claims = [x['claim_pid'] for x in status.get('cases', {}).values() if x.get('claim_pid')]
    pending = json.loads((R/'pending_01.json').read_text())
    if pending.get('state') == 'running_components_full_gate' and pending.get('component_full_claim_pid'):
        claims.append(pending['component_full_claim_pid'])
    if pending.get('state') == 'running_instruction9_profile' and pending.get('profile_claim_pid'):
        claims.append(pending['profile_claim_pid'])
    if pending.get('state') == 'waiting_or_running_instruction10_match_timing' and pending.get('match_timing_claim_pid'):
        claims.append(pending['match_timing_claim_pid'])
    if pending.get('state') == 'waiting_or_running_instruction13_fast_gates' and pending.get('fast_gate_claim_pid'):
        claims.append(pending['fast_gate_claim_pid'])
    if pending.get('state') in ('running_full_cstar_gates','running_parallel_full_cstar_gates','separating_full_gates_instruction7') and pending.get('full_claim_pid'):
        claims.append(pending['full_claim_pid'])
    if pending.get('instruction15_small_claim_pid'):
        claims.append(pending['instruction15_small_claim_pid'])
    if pending.get('structure_full_claim_pid'):
        claims.append(pending['structure_full_claim_pid'])
    if pending.get('deep_memory_claim_pid'):
        claims.append(pending['deep_memory_claim_pid'])
    parallel=R.parent/'codex_cstar_2026-10-07/parallel_instruction7_01'
    parallel_status={}
    if parallel.exists():
        for name in ('coordinator_started','on_own_claim','on_keep_claim','comparison_claim','on_own_started','on_keep_started','on_own_job_done','on_keep_job_done','complete','STOP'):
            p=parallel/(name+'.json')
            if p.exists():
                value=json.loads(p.read_text())
                parallel_status[name]=value
                if name.endswith('_claim'):claims.append(value['claim_pid'])
    queue19p_case = Path(pending['queue19p_case']) if pending.get('queue19p_case') else None
    if pending.get('queue19p_claim_pid'):
        claims.append(pending['queue19p_claim_pid'])
    queue19p_status = {}
    if queue19p_case:
        for name in ('queue_claim_published', 'launcher_pid', 'admission_command', 'status', 'pid', 'result', 'STOP'):
            p = queue19p_case / (name + '.json')
            if p.exists(): queue19p_status[name] = json.loads(p.read_text())
        log = queue19p_case / 'jobs.log'
        if log.exists(): queue19p_status['jobs_log_tail'] = log.read_text()[-2400:]
        warnings = queue19p_case / 'resource_warnings.jsonl'
        if warnings.exists(): queue19p_status['warnings_tail'] = warnings.read_text()[-2400:]
    rows = ps()
    claims = sorted({p for p in claims if p in rows and 'Z' not in rows[p]['stat']})
    cpu = cpu_reading([{'child': SimpleNamespace(pid=p)} for p in claims])
    diagnostics = {}
    for key, cmd in [('swap', ['/usr/sbin/sysctl', 'vm.swapusage']),
                     ('thermal', ['/usr/bin/pmset', '-g', 'therm']), ('memory', ['/usr/bin/vm_stat'])]:
        p = subprocess.run(cmd, capture_output=True, text=True)
        diagnostics[key] = {'exit': p.returncode, 'out': p.stdout, 'err': p.stderr}
    inbox = files['control/受け箱/SMEの係.md']
    sections = re.findall(r'^## 指示 .*?(?=^## 指示 |\Z)', inbox, re.M | re.S)
    instructions = [{'header': s.splitlines()[0], 'received': bool(re.search(r'受領（', s)),
                     'done': bool(re.search(r'済み（', s)), 'held': '保留：アストラの承認待ち' in s,
                     'text': s} for s in sections]
    queue_rows = []
    header = None
    for line in files['control/走行の列_2026-10-08.md'].splitlines():
        if not line.startswith('| '):
            continue
        cells = [s.strip() for s in line.split('|')[1:-1]]
        if cells[0] == '#':
            header = cells
        elif re.fullmatch(r'\d+[a-z]?(?:\s*/\s*\d+[a-z]?)*', cells[0]):
            assert header and len(header) == len(cells)
            queue_rows.append(dict(zip(header, cells)))
    ready = [x for x in queue_rows if x['状態'] == '未着手' and x['版・旗・出力先']
             and x['機械'] in ('マック', 'Mac', 'どちらでも')]
    native = R.parent/'codex_cstar_2026-10-07/native_full_01'
    component = R.parent/'codex_cstar_2026-10-07/components_full_gate_01'
    component_status = {}
    if component.exists():
        for name in ('claim','started','current','complete','STOP','STOP_instruction9_administrative','off_A_comparison',
                     'off_L_comparison','online_Cstar_comparison','candidate_comparison'):
            p = component/(name+'.json')
            if p.exists():
                value=json.loads(p.read_text())
                component_status[name]=value
        for name in ('off_A','off_L','online_Cstar','replay_Cstar'):
            p=component/name/'finished.json'
            if p.exists(): component_status.setdefault('finished_cases',{})[name]=json.loads(p.read_text())
    native_status = {}
    if native.exists():
        for name in ('current','complete','STOP','resource_hold'):
            p=native/(name+'.json')
            if p.exists(): native_status[name]=json.loads(p.read_text())
        for name in ('base_A','off_A','base_L','off_L','on_own','on_keep'):
            p=native/(name+'.json')
            if p.exists():native_status.setdefault('finished_cases',{})[name]=json.loads(p.read_text())
            else:
                answers=list((native/name/'output/side').rglob('*.answers.csv'))
                if answers:native_status.setdefault('incomplete_case_written_rows',{})[name]=max(0,len(answers[0].read_text().splitlines())-1)
        for name in ('off_A','off_L','material_same_flags'):
            p=native/(name+'_comparison.json')
            if p.exists():
                v=json.loads(p.read_text())
                native_status.setdefault('comparisons',{})[name]={'passed':v['passed'],'files':len(v['files'])}
        current=native_status.get('current',{}).get('case')
        if current:
            answers=list((native/current/'output/side').rglob('*.answers.csv'))
            if answers:native_status['written_answer_rows_lower_bound']=max(0,len(answers[0].read_text().splitlines())-1)
    profile_root = R.parent/'codex_cstar_profile_2026-10-08'
    profile_status = {}
    for name in ('claim','started','complete','STOP','guard_instruction11_started','guard_instruction11_complete','guard_instruction11_STOP'):
        p=profile_root/(name+'.json')
        if p.exists():profile_status[name]=json.loads(p.read_text())
    for case in ('preflight20_01','profile1740_01'):
        case_status={}
        for name in ('started','finished','comparison','complete','resource_hold'):
            p=profile_root/case/(name+'.json')
            if p.exists():case_status[name]=json.loads(p.read_text())
        timing=profile_root/case/'sec_trial.csv'
        if timing.exists():
            measured=timing.read_text().splitlines()
            case_status['measured_rows_written']=max(0,len(measured)-1)
            if len(measured)>1:case_status['last_measured_trial_number']=int(measured[-1].split(',')[0])+1
        profile_status[case]=case_status
    match_root=profile_root/'match_times_instruction10_01'
    match_status={}
    for name in ('claim','started','complete','STOP'):
        p=match_root/(name+'.json')
        if p.exists():match_status[name]=json.loads(p.read_text())
    log=match_root/'claim.log'
    if log.exists():match_status['claim_log_tail']=log.read_text()[-1800:]
    for case in ('preflight20_01','full1740_01'):
        item={}
        for name in ('started','finished','comparison','complete','observations_complete','analysis'):
            p=match_root/case/(name+'.json')
            if p.exists():item[name]=json.loads(p.read_text())
        if item:match_status[case]=item
    fast_root=R.parent/'codex_cstar_fast_2026-10-08'
    fast_status={}
    for name in ('preparation_01','encode_checks_01','diagnostic_saved_state_example_01','reported_preparation_01'):
        p=fast_root/(name+'.json')
        if p.exists():fast_status[name]=json.loads(p.read_text())
    for name in ('claim','started','current','complete','STOP'):
        p=fast_root/'gates_01'/(name+'.json')
        if p.exists():fast_status[name]=json.loads(p.read_text())
    log=fast_root/'gates_01/claim.log'
    if log.exists():fast_status['claim_log_tail']=log.read_text()[-1800:]
    plan=fast_root/'gate_plan_01.json'
    if plan.exists():
        for case in json.loads(plan.read_text())['cases']:
            item={}
            for name in ('started','finished','comparison','complete','whole_cpu'):
                p=fast_root/'gates_01'/case['name']/(name+'.json')
                if p.exists():item[name]=json.loads(p.read_text())
            if item:fast_status.setdefault('cases',{})[case['name']]=item
    small_root=fast_root/'gates200_instruction15_01'
    small_status={}
    for name in ('claim','started','current','complete','STOP','waiting'):
        p=small_root/(name+'.json')
        if p.exists():small_status[name]=json.loads(p.read_text())
    for case in ('original_C','off_C','gc_C','encode_C','both_C'):
        item={}
        for name in ('started','finished','comparison','complete','whole_cpu','resource_hold'):
            p=small_root/case/(name+'.json')
            if p.exists():item[name]=json.loads(p.read_text())
        if item:small_status.setdefault('cases',{})[case]=item
    structure_root=R.parent/'codex_cstar_structure_2026-10-08'
    structure_status={}
    for phase_name in ('preflight20_01','full1740_01'):
        phase_status={}
        for name in ('claim','started','current','complete','STOP'):
            p=structure_root/phase_name/(name+'.json')
            if p.exists():phase_status[name]=json.loads(p.read_text())
        for case in ('off_A','off_L','off_Cstar','structure_Cstar'):
            item={}
            for name in ('started','finished','comparison','complete','whole_cpu'):
                p=structure_root/phase_name/case/(name+'.json')
                if p.exists():item[name]=json.loads(p.read_text())
            if item:phase_status.setdefault('cases',{})[case]=item
        if phase_status:structure_status[phase_name]=phase_status
    memory_root=profile_root/'deep_memory_instruction12_01'
    memory_status={}
    for phase_name in ('preflight20_01','full1740_01'):
        item={}
        for name in ('claim','started','finished','comparison','complete','STOP','observation_check','observations_complete','analysis'):
            p=memory_root/phase_name/(name+'.json')
            if p.exists():item[name]=json.loads(p.read_text())
        if item:memory_status[phase_name]=item
    for name in ('full_memory_check_01','execution_prepared_01','reported_execution_preparation_01',
                 'analysis_prepared_01','analysis_claim_01','reported_analysis_preparation_01','reported_full_memory_01'):
        p=memory_root/(name+'.json')
        if p.exists():memory_status[name]=json.loads(p.read_text())
    result = {'at': datetime.now().astimezone().isoformat(), 'fetched_commit': commit, 'files': files,
              'instructions': instructions, 'queue_rows': queue_rows, 'eligible_mac_rows': ready,
              'status': status, 'cpu': cpu, 'resources': conditions(), 'diagnostics': diagnostics,
              'queue19p_status': queue19p_status,
              'own_controllers': {p: x for p, x in rows.items() if ((queue19p_case and str(queue19p_case) in x['command'])
                                  or str(TIME / 'workflow_parallel25_05.py') in x['command']
                                  or str(R.parent/'codex_cstar_2026-10-07/native_full_01.py') in x['command']
                                  or str(R.parent/'codex_cstar_2026-10-07/parallel_instruction7_01.py') in x['command']
                                  or str(R.parent/'codex_cstar_2026-10-07/components_full_gate_01.py') in x['command']
                                  or str(profile_root/'run_profile_01.py') in x['command']
                                  or str(profile_root/'guard_instruction11_01.py') in x['command']
                                  or str(profile_root/'run_match_timing_01.py') in x['command']
                                  or str(fast_root/'run_gates_01.py') in x['command']
                                  or str(fast_root/'run_gates200_instruction15_01.py') in x['command']
                                  or str(structure_root/'run_gates_01.py') in x['command']
                                  or str(memory_root/'run_memory_01.py') in x['command']
                                  or profile_root.name+'/guard_instruction11_01.py' in x['command'])},
              'native_full_status':native_status,
              'component_full_status':component_status,
              'parallel_full_status':parallel_status,
              'instruction9_profile_status':profile_status,
              'instruction10_match_timing_status':match_status,
              'instruction13_fast_status':fast_status,
              'instruction15_small_status':small_status,
              'instruction12_structure_status':structure_status,
              'instruction12_deep_memory_status':memory_status,
              'completion_record': (TIME / 'all_complete_priority25.json').exists(),
              'proposals_reported': (TIME / 'reported_二本の内訳と案.json').exists()}
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    brief = {k: v for k, v in result.items() if k not in ('files', 'status', 'cpu', 'queue_rows')}
    brief['cpu'] = {k: v for k, v in cpu.items() if k != 'external_compute_processes'}
    brief['cases'] = status.get('cases', {})
    brief['queue_states'] = [{'row': x['#'], 'state': x['状態']} for x in queue_rows]
    print(json.dumps(brief, ensure_ascii=False, indent=2), flush=True)
except Exception as e:
    (R / (phase + '_check_stop.json')).write_text(json.dumps({'at': datetime.now().astimezone().isoformat(),
                                                            'reason': str(e), 'conflicts_not_resolved': True},
                                                           ensure_ascii=False, indent=2) + '\n')
    raise
