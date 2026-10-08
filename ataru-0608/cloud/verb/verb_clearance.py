"""動詞の包みの資源の確認（README「受付と資源の確認」）を、Ubuntu 版の受付表（同じフォルダの jobs.py）の測り方で作り、30 秒ごとに原子的に書き直す監督。
使い方：python3 verb_clearance.py <確認の根> <本のフォルダ>…   （例 /srv/verb/resource_clearance /srv/verb/measurements_20261009/on100_without_probe …）
各本について <確認の根>/<label>.json に次の欄を書く（label は本のフォルダの名前）：
  runtime_sha256：その本の runtime.json の SHA256。machine_sha256：/etc/machine-id の SHA256。memory_reservation_gb：runtime.json の値。checked_epoch：測った時刻。
  memory_admission_ok：受付表の見込みの合計 ≦ 予算（物理メモリ − 4 GiB）、かつ 今の MemAvailable −（まだ始めていない本なら、その本の予約）≧ 4 GiB。
  swap_stable_10min：jobs.py の条件 2（直近 10 分でスワップが増えていない。記録が 10 分ぶん無ければ偽）。
  thermal_ok：jobs.py の条件 3（Linux の熱の確認。測る欄が無ければ偽）。
  physical_cpu_count：lscpu の Core(s) per socket × Socket(s)。cpu_budget：物理芯数 − 2。
  warning：上のどれかが偽、出力先の空きが 18.5 GiB 未満、又は測れなかったとき真。
  first_pair_decision：<確認の根>/first_pair_decision.json があれば、300 の本にだけ、その中身をそのまま入れる（走行の係が両機械の確認済みの記録から作る。推測では作らない）。
値は測った値だけで、推測で真にしない。測れなかった欄は偽にして warning を真にする。"""
import hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import jobs

ROOT = Path(sys.argv[1]); CASES = [Path(p) for p in sys.argv[2:]]
ROOT.mkdir(parents=True, exist_ok=True)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
lscpu = subprocess.run(["lscpu"], capture_output=True, text=True).stdout
get = lambda k: int(next(l.split(":", 1)[1] for l in lscpu.splitlines() if l.startswith(k)))
PHYS = get("Core(s) per socket") * get("Socket(s)")
MACHINE = sha("/etc/machine-id")
jobs.ensure_sampler()

def one(case):
    v = json.loads((case / "runtime.json").read_text()); res = v["memory_reservation_gb"]
    c = dict(runtime_sha256=sha(case / "runtime.json"), machine_sha256=MACHINE, memory_reservation_gb=res, checked_epoch=time.time(),
             physical_cpu_count=PHYS, cpu_budget=PHYS - 2, source="verb_clearance.py（Ubuntu 版の受付表 jobs.py の測り方）")
    try:
        with jobs.Locked():
            rows, _ = jobs.prune()
        tot = sum(r["mem_gb"] for r in rows); avail = jobs.meminfo()["MemAvailable"] / 1024 ** 3
        started = (case / "pid.json").exists()
        c["memory_admission_ok"] = bool(tot <= jobs.BUDGET_GB and avail - (0 if started else res) >= 4.0)
        ok, msg = jobs.swap_ok(); c["swap_stable_10min"] = bool(ok)
        warn, cur, raw = jobs.therm(); c["thermal_ok"] = not warn
        out = Path(v["output"]); probe = out
        while not probe.exists(): probe = probe.parent
        free = shutil.disk_usage(probe).free / 1024 ** 3
        c["basis"] = dict(registry_total_gb=tot, budget_gb=jobs.BUDGET_GB, mem_available_gib=round(avail, 2), started=started, swap=msg,
                          thermal=raw, thermal_warnings=warn, output_free_gib=round(free, 2))
        c["warning"] = not (c["memory_admission_ok"] and ok and not warn and free >= 18.5)
    except Exception as e:
        c.update(memory_admission_ok=False, swap_stable_10min=False, thermal_ok=False, warning=True, basis=dict(error=repr(e)))
    d = ROOT / "first_pair_decision.json"
    if v.get("completed_trials") == 300 and d.exists():
        c["first_pair_decision"] = json.loads(d.read_text())
    tmp = ROOT / f".{case.name}.json.tmp"; tmp.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n"); os.replace(tmp, ROOT / f"{case.name}.json")

while True:
    for case in CASES:
        if (case / "runtime.json").exists():
            one(case)
    time.sleep(30)
