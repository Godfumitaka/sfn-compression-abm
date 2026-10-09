"""受け箱の指示 57：第 2 波の D・D＋注意（#10〜#13・#17・#18、100 本）を Google Cloud（無料の枠、全地域で 12 vCPU）の二台に順に始める。
順：#12 → #10 → #13 → #11 → #17 → #18（各行は種 1〜10、世界 1・2）。一台の同時の本数は 芯の数 − 1（c3d-standard-8 は 7、c3d-standard-4 は 3）。
各本：wave2_start.py（版の作業場所の HEAD ときれいな作業木、--v39-price・--e-price・--shop-exc の期待の値、設定の sha256 を確かめる。setsid・time -v・PYTHONHASHSEED=0・LANG/LC_* を外す）。
始めた本は s57_<機械>.json に足す（見張り wave2d_watch_gcp.sh が持ち帰る）。走っている本は止めない。"""
import json, os, subprocess, time
W=os.path.expanduser("~/cloud/wave1/"); K=os.path.expanduser("~/.ssh/google_compute_engine")
GO=f"-i {K} -o UserKnownHostsFile={os.path.expanduser('~/.ssh/gcp_known_hosts')} -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15"
machines={"g8":("34.57.154.198",7),"g4":("34.45.150.3",3),"g16a":("136.107.100.7",15),"g16b":("35.243.229.179",15)}   # 10/10 00:55：枠が 96 に広がったので、c3d-standard-16 を us-east4・us-east1 に足した（C3D は地域ごとに 24 vCPU まで）
cmds=json.load(open(W+"wave2d_commands.json"))
for c in cmds:
    c["argv"]=[a.replace("/home/USER/","/home/tatsu/").replace("/home/ubuntu/","/home/tatsu/") for a in c["argv"]]
    c["rundir"]=os.path.dirname(c["argv"][3])
assigned={m:(json.load(open(W+f"s57_{m}.json")) if os.path.exists(W+f"s57_{m}.json") else []) for m in machines}
started={c["name"] for m in ("g8","g4","g16a","g16b") if os.path.exists(W+f"s57_{m}.json") for c in json.load(open(W+f"s57_{m}.json"))}
queue=[c for c in cmds if c["name"] not in started]
log=lambda s: open(W+"sched57.log","a").write(time.strftime("%F %T ")+s+"\n")
log(f"始めた：残り {len(queue)} 本")
while queue:
    for m,(ip,cap) in machines.items():
        if not queue: break
        n=subprocess.run(f"ssh -n {GO} tatsu@{ip} 'ps -eo args | grep -c \"^python3.12 tools/v3_run.py\"'",shell=True,capture_output=True,text=True).stdout.strip()
        if not n.isdigit() or int(n)>=cap: continue
        nxt=queue[0]; json.dump([nxt],open(W+"s57_one.json","w"))
        r=subprocess.run(f"scp -q {GO} {W}s57_one.json tatsu@{ip}:~/wave1/ && ssh -n {GO} tatsu@{ip} 'export PATH=$HOME/.local/bin:$PATH; python3.12 ~/wave1/wave2_start.py ~/wave1/s57_one.json'",shell=True,capture_output=True,text=True)
        if r.returncode==0 and "始めた" in r.stdout:
            assigned[m].append(nxt); json.dump(assigned[m],open(W+f"s57_{m}.json","w"),ensure_ascii=False,indent=1); queue.pop(0)
            log(f"{m} で始めた {nxt['name']}（模型 {int(n)+1} 本）"); time.sleep(3); continue
        log(f"★ {m} で {nxt['name']} を始められなかった：{r.stdout[-200:]} {r.stderr[-300:]}"); time.sleep(60)
    if queue: time.sleep(60)
log("100 本を全部始めた")
