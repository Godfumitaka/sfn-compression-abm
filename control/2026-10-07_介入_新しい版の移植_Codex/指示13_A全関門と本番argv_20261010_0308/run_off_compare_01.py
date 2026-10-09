"""保存済みoff100を固定した比較入口へ一度通し、待ちと解析を別保存する。"""
from pathlib import Path
import datetime, hashlib, json, os, resource, shutil, subprocess, sys, time

admitted = time.time()
here = Path(__file__).resolve().parent
port = here.parent
sys.path.insert(0, str(port))
from admission_guard import census

def now():
    return datetime.datetime.now().astimezone().isoformat()

def save(name, value):
    (here / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

assert datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat("2026-10-13T09:00:00+09:00")
assert not (here / "A_off_comparison_01.json").exists()
assert not (here / "off_comparison_01_status.json").exists()
waiting = time.perf_counter()
rows, active, paused = census()
parents = set()
for pid in active | paused:
    parent = rows[pid]["parent"]
    seen = set()
    while parent in rows and parent not in seen:
        seen.add(parent)
        if parent in active | paused:
            parents.add(parent)
        parent = rows[parent]["parent"]
active -= parents
paused -= parents
output = here / "A_fixed_off100/output"
free = shutil.disk_usage(output).free
save("off_comparison_before_start_01.json", dict(
    at_jst=now(), active=len(active), paused=len(paused), excluded_parents=sorted(parents),
    processes=[dict(pid=pid, **rows[pid]) for pid in sorted(active | paused)],
    free_disk_bytes=free,
    thermal=subprocess.check_output(["pmset", "-g", "therm"], text=True),
    swap=subprocess.check_output(["sysctl", "vm.swapusage"], text=True),
))
assert len(active) < 8 and free >= 20 * 2**30
protected = json.loads((here / "protected_sources_before.json").read_text())
def fingerprints():
    return {root: {name: hashlib.sha256((Path(root) / name).read_bytes()).hexdigest()
                   for name in files} for root, files in protected.items()}
assert fingerprints() == protected
status = dict(state="running", started_at_jst=now(), wrapper_pid=os.getpid(),
    admission_wait_seconds=admitted-float(os.environ["INTERVENTION_ADMISSION_SUBMITTED_EPOCH"]),
    cpu_wait_seconds=time.perf_counter()-waiting, production_started=False)
save("off_comparison_01_status.json", status)
began = time.perf_counter()
with (here / "off_comparison_01.log").open("xb") as log:
    code = subprocess.call([sys.executable, str(here / "compare_A.py")], stdout=log, stderr=subprocess.STDOUT)
elapsed = time.perf_counter() - began
after = fingerprints()
save("off_comparison_protected_after_01.json", after)
status.update(state="completed" if code == 0 and after == protected else "stopped",
    exit_code=code, ended_at_jst=now(), analysis_seconds=elapsed,
    protected_unchanged=after == protected,
    peak_children_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
save("off_comparison_01_status.json", status)
print(json.dumps(status, ensure_ascii=False), flush=True)
sys.exit(code or (0 if after == protected else 1))
