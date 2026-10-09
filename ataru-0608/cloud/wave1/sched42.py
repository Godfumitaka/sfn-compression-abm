"""受け箱の指示 42：3a・5a・6a の種 3〜20（108 本）を、芯と記憶が空いた機械から順に始める（5a → 6a → 3a の順、長くかかりそうな本から）。
2 分ごとに各機械を見て、模型の本が 30 本未満（32 芯のうち 2 芯を残す）で、
  （この台本が始めて走っている本の予約の合計）＋（ほかの模型の本の今の常駐の合計）＋（次の本の予約）≦ 物理メモリ − 4GiB
なら、次の本を一本始める（wave1_start.py、setsid・time -v・PYTHONHASHSEED=0・LANG/LC_* を外す）。
始めた本は s42_<機械>.json に足す（見張りがそれを見て持ち帰る）。全部始めたら抜ける。走っている本は止めない。"""
import json, os, subprocess, time
W=os.path.expanduser("~/cloud/wave1/"); K=os.path.expanduser("~/.ssh/sfn-runner.pem")
cmds=json.load(open(W+"wave1_s42_commands.json"))
machines={"m0":open(os.path.expanduser("~/cloud/wave1_machine")).read().split()[1]}
for i in (1,2,3,4): machines[f"m{i}"]=open(W+f"machine_m{i}").read().split()[1]
assigned={m:(json.load(open(W+f"s42_{m}.json")) if os.path.exists(W+f"s42_{m}.json") else []) for m in machines}
started={c["name"] for a in assigned.values() for c in a}
queue=[c for c in cmds if c["name"] not in started]
log=lambda s: open(W+"sched42.log","a").write(time.strftime("%F %T ")+s+"\n")
PROBE=r'''python3 - <<"P"
import os,json
mt=int([l for l in open("/proc/meminfo") if l.startswith("MemTotal")][0].split()[1])*1024
procs={}
for p in os.listdir("/proc"):
    if not p.isdigit(): continue
    try:
        a=open(f"/proc/{p}/cmdline","rb").read().split(b"\0"); pp=open(f"/proc/{p}/stat").read().rsplit(")",1)[1].split()
        procs[p]=(a,pp[1],int(pp[21])*4096)
    except Exception: pass
runs={}
for p,(a,pp,rss) in procs.items():
    if len(a)>3 and a[0]==b"python3.12" and a[1]==b"tools/v3_run.py":
        tot=rss+sum(r for q,(aa,ppq,r) in procs.items() if ppq==p)
        runs[os.path.dirname(a[3].decode())]=tot
print(json.dumps(dict(memtotal=mt,runs=runs)))
P'''
log(f"始めた：残り {len(queue)} 本")
while queue:
    for m,ip in machines.items():
        if not queue: break
        try:
            st=json.loads(subprocess.run(["ssh","-n","-i",K,"-o","ConnectTimeout=15",f"ubuntu@{ip}",PROBE],capture_output=True,text=True,timeout=60).stdout)
        except Exception as e:
            log(f"★ {m} を測れなかった {e!r}"); continue
        runs=st["runs"]; mine={c["rundir"]:c["mem_gb"] for c in assigned[m]}
        committed=sum(mine[d]*1e9 for d in runs if d in mine)+sum(r for d,r in runs.items() if d not in mine)
        nxt=queue[0]; budget=st["memtotal"]-4*2**30
        if len(runs)<30 and committed+nxt["mem_gb"]*1e9<=budget:
            json.dump([nxt],open(W+"s42_one.json","w"))
            r=subprocess.run(f"scp -q -i {K} {W}s42_one.json ubuntu@{ip}:~/wave1/s42_one.json && ssh -n -i {K} ubuntu@{ip} 'export PATH=$HOME/.local/bin:$PATH; python3.12 ~/wave1/wave1_start.py ~/wave1/s42_one.json'",shell=True,capture_output=True,text=True)
            if r.returncode==0 and "始めた" in r.stdout:
                assigned[m].append(nxt); json.dump(assigned[m],open(W+f"s42_{m}.json","w"),ensure_ascii=False,indent=1); queue.pop(0)
                log(f"{m} で始めた {nxt['name']}（模型 {len(runs)+1} 本、見込みの合計 {(committed+nxt['mem_gb']*1e9)/1e9:.1f}GB / {budget/1e9:.1f}GB）")
            else: log(f"★ {m} で {nxt['name']} を始められなかった：{r.stdout[-200:]} {r.stderr[-200:]}")
    if queue: time.sleep(120)
log("108 本を全部始めた")
