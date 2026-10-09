"""動詞の指示 27・28 の包み（run_registered.py）が求める資源の確認を、Ubuntu 版の受付表 jobs.py の測り方で 30 秒ごとに原子的に書き直す（受け箱の指示 64 の 1）。
欄：spec_sha256（case/spec.json）、machine_boot_sha256（/etc/machine-id の SHA256。run_registered.py の Linux の作り方と同じ）、checked_epoch、memory_reservation_gb（spec の値）、
memory_admission_ok（受付表の見込みの合計 ≦ 予算、かつ MemAvailable −（まだ始めていない本ならその予約）≧ 4GiB）、swap_stable_10min・thermal_ok（jobs.py の条件 2・3）、
physical_cpu_count（lscpu の Core×Socket）、cpu_budget（物理芯数 − 2）、warning（どれかが偽、空き 20GiB 未満、測れないとき真）。推測で真にしない。
使い方：python verb27_clearance.py <確認の根> <case>…"""
import hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path.home()/"jobs")); import jobs
ROOT=Path(sys.argv[1]); CASES=[Path(p) for p in sys.argv[2:]]; ROOT.mkdir(parents=True, exist_ok=True)
sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
ls=subprocess.run(["lscpu"],capture_output=True,text=True).stdout
get=lambda k: int(next(l.split(":",1)[1] for l in ls.splitlines() if l.startswith(k)))
PHYS=get("Core(s) per socket")*get("Socket(s)"); BOOT=sha("/etc/machine-id"); jobs.ensure_sampler()
def one(case):
    spec=json.loads((case/"spec.json").read_text()); res=spec["memory_reservation_gb"]
    c=dict(spec_sha256=sha(case/"spec.json"), machine_boot_sha256=BOOT, checked_epoch=time.time(), memory_reservation_gb=res,
           physical_cpu_count=PHYS, cpu_budget=PHYS-2, source="verb27_clearance.py（Ubuntu 版の受付表 jobs.py の測り方）")
    try:
        with jobs.Locked(): rows,_=jobs.prune()
        tot=sum(r["mem_gb"] for r in rows); avail=jobs.meminfo()["MemAvailable"]/1024**3
        started=(case/"output").exists()
        c["memory_admission_ok"]=bool(tot<=jobs.BUDGET_GB and avail-(0 if started else res)>=4.0)
        ok,msg=jobs.swap_ok(); c["swap_stable_10min"]=bool(ok)
        warn,cur,raw=jobs.therm(); c["thermal_ok"]=not warn
        free=shutil.disk_usage(case).free/1024**3
        c["basis"]=dict(registry_total_gb=tot,budget_gb=jobs.BUDGET_GB,mem_available_gib=round(avail,2),swap=msg,thermal=raw,thermal_warnings=warn,free_gib=round(free,2))
        c["warning"]=not (c["memory_admission_ok"] and ok and not warn and free>=20)
    except Exception as e:
        c.update(memory_admission_ok=False,swap_stable_10min=False,thermal_ok=False,warning=True,basis=dict(error=repr(e)))
    tmp=ROOT/f".{case.name}.json.tmp"; tmp.write_text(json.dumps(c,ensure_ascii=False,indent=2)+"\n"); os.replace(tmp,ROOT/f"{case.name}.json")
while True:
    for case in CASES:
        if (case/"spec.json").exists(): one(case)
    time.sleep(30)
