"""第 1 波の表の準備を新しく持ち帰った本に広げる（受け箱の指示 44）：wave1_view.py で見え方を足し、2a・2b の再生の見え方と命令を足す。
再生（replay.py）が走っていなければ始める（再生の途中の写しは D:、SURFACE_TMP）。何度走らせてもよい。率は出さない。"""
import csv, json, os, subprocess
from pathlib import Path
H=Path.home(); V=H/"surface/wave1_view"; RV=H/"surface/wave1_replay_view"; W=H/"cloud/wave1"
subprocess.run(["python3", str(H/"surface/wave1_view.py")], check=True)
sel=[r for r in csv.DictReader(open(V/"selection.tsv"),delimiter="\t") if r["row"][0]=="2" and r["run"]]
src={c["name"]:c for f in ("wave1_s12_commands.json","wave1_s3_20_commands.json") for c in json.load(open(W/f))}
cmds={"e9":[],"c574":[]}
for r in sel:
    s=int(r["seed"]); w=int(r["world"]); grp="e9" if s<=2 else "c574"; arm=f"q{r['row']}_w{w}"
    link=RV/f"2a_{grp}"/arm/f"seed{s:03d}"; link.parent.mkdir(parents=True,exist_ok=True)
    tgt=os.readlink(V/r["row"]/arm/f"seed{s:03d}")
    if not link.exists(): link.symlink_to(tgt)
    c=src[r["run"]]; argv=list(c["argv"]); argv[0]="python3.12"
    argv[2]=str(W/("configs" if s<=2 else "configs35")/c["config_rel"]); argv[3]=str(link)
    cmds[grp].append(dict(arm=arm,seed=s,command=argv))
for g in cmds: json.dump(cmds[g],open(H/f"surface/wave1_replay_cmds_{g}.json","w"),ensure_ascii=False,indent=1)
running=subprocess.run("ps -eo args | grep -c '^python3.12 -u replay.py --configs /home/tatsu/surface/configs_wave1_replay.json'",shell=True,capture_output=True,text=True).stdout.strip()
if running=="0":
    subprocess.run(["tmux","new-session","-d","-s","replay2a",f"cd {H}/surface && SURFACE_TMP=/mnt/d/sfn_runs/surface_tmp python3.12 -u replay.py --configs {H}/surface/configs_wave1_replay.json --maxpar 4 --total 12 2>&1 | tee -a {H}/surface/replay2a.log"])
    print("再生を始めた")
print({g:len(v) for g,v in cmds.items()})
