"""指示32の指定二本を別々の受付へ渡す。再試行・模型シグナルを持たない。"""
from pathlib import Path
import hashlib, importlib.util, json, os, subprocess, sys, time

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('readonly_resource', ROOT.parent/'instruction19_speed_gate/gate.py')
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)

def write(path, value):
    with path.open('x') as out: out.write(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def verify(case):
    source = Path(case['source'])
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip() == case['commit']
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=source,text=True).strip()
    assert hashlib.sha256(Path(case['native_command'][2]).read_bytes()).hexdigest() == case['configuration_sha256']
    assert G.stamp()[:19] < '2026-10-11T09:00:00'

def resource_ok(case, registered):
    m = G.machine()
    # 同じ過程の診断workerも全体8本へ追加して数える。
    assert G.start_ok(m) and m['model_children']+1 <= 8
    assert sum(x['mem_gb'] for x in m['registered'])+(0 if registered else case['mem_gb']) <= 24
    return m

if __name__ == '__main__':
    action, version = sys.argv[1:]
    case = json.loads((ROOT/'preparation_manifest.json').read_text())['cases'][version]
    folder = Path(case['folder'])
    verify(case)
    assert not (folder/'output').exists()
    if action == 'entry':
        assert not (folder/'entry_started.json').exists()
        m = resource_ok(case, True)
        write(folder/'entry_started.json', dict(at=G.stamp(), machine=m, source_commit=case['commit'],
            same_process_worker_additional_models=1, actual_global_model_count_on_start=m['model_children']+1,
            actual_native_command=case['native_command'], production_started=False))
        os.execv(G.PY,[G.PY,str(ROOT/'trace_worker.py'),version])
    assert action == 'run'
    assert not (folder/'receipt_submitted.json').exists()
    m = resource_ok(case, False)
    command = [G.PY,G.JOBS,'run','--wait','--owner','Codex2 指示32 '+version+' 世界1 種1 6試行診断',
        '--mem',str(case['mem_gb']),'--disk-path',str(folder/'output'),'--',G.PY,str(ROOT/'launch.py'),'entry',version]
    env = os.environ.copy(); env.update(case['environment'])
    with (folder/'run.log').open('x') as log:
        proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)
        write(folder/'receipt_submitted.json', dict(at=G.stamp(), pid=proc.pid, command=command,
            machine=m, mem_gb=case['mem_gb'], mem_basis='先頭20試行約63MBと200試行最大約350MBに余裕を置いた1GB',
            automatic_retry=False, production_started=False))
        code = proc.wait()
    write(folder/'receipt_ended.json', dict(at=G.stamp(), pid=proc.pid, exit_code=code,
        actual_child_exit_code=True, automatic_retry=False, model_signals=0))
    print(json.dumps(dict(version=version, receipt_exit_code=code,
        worker_failure=json.loads((folder/'worker_failure.json').read_text()) if (folder/'worker_failure.json').exists() else None),ensure_ascii=False))
