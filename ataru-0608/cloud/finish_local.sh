#!/bin/bash
# 受け箱の指示 23 の 3：クラウドの 13 本が全部終わり、D: への持ち帰りと sha256 の確かめが済んだら、
# 手元の較正 12 本（一時停止中）の模型の過程に SIGTERM を送って終わらせる（止まっている過程が受け取れるよう、続けて SIGCONT）。途中までの出力は消さない。
# クラウドで失敗した本があれば、何もせずに待つ（cloud_watch が機械を消さずに待つ）。
# 終わらせた時刻と、どの本をどちらで使ったか（指示 19 の決まり：先に 1,740 試行を終えた方）を報告と受け箱に書いて push する。
set -u
LOG=$HOME/cloud/cloud_watch.log; DONE=$HOME/cloud/calib13_done.tsv; RES=$HOME/v33prod/results
until grep -q "13 本を全部持ってきたので" $LOG 2>/dev/null; do sleep 300; done
grep -q "失敗" $DONE && { echo "クラウドに失敗した本がある。何もしない"; exit 3; }
T=$(date '+%F %T')
PIDS=$(python3 - <<'PY'
import os
procs={}
for p in os.listdir("/proc"):
    if not p.isdigit(): continue
    try:
        a=open(f"/proc/{p}/cmdline","rb").read().split(b"\0"); pp=open(f"/proc/{p}/stat").read().rsplit(")",1)[1].split()[1]; procs[p]=(a,pp)
    except Exception: pass
roots=[p for p,(a,_) in procs.items() if len(a)>3 and a[1]==b"tools/v3_run.py" and (b"/calib_w1/" in a[3] or b"/calib_w2/" in a[3])]
out,todo=set(roots),list(roots)
while todo:
    q=todo.pop()
    for p,(_,pp) in procs.items():
        if pp==q and p not in out: out.add(p); todo.append(p)
print(" ".join(sorted(out,key=int)))
PY
)
[ -n "$PIDS" ] && kill -TERM $PIDS && kill -CONT $PIDS
echo -e "$T\tterm\t-\t$(echo $PIDS | wc -w)\t$PIDS" >> $RES/ataru-0608/game_mode/pause_log.tsv
sleep 30
TABLE=$(python3 - <<'PY'
import csv, glob, os, re
done={r["run"]:r for r in csv.DictReader(open(os.path.expanduser("~/cloud/calib13_done.tsv")),delimiter="\t")}
local={"w1_seed041":"/home/tatsu/calib_w1/birth_hu_on","w1_seed042":"/home/tatsu/calib_w1/w1_seed042","w1_seed043":"/home/tatsu/calib_w1/w1_seed043","w1_seed044":"/home/tatsu/calib_w1/w1_seed044",
       "w1_seed045":"/home/tatsu/calib_w1/w1_seed045","w1_seed046":"/home/tatsu/calib_w1/w1_seed046","w1_seed047":"/home/tatsu/calib_w1/w1_seed047","w1_seed048":"/home/tatsu/calib_w1/w1_seed048",
       "w2_seed045":"/home/tatsu/calib_w2/w2_seed045","w2_seed046":"/home/tatsu/calib_w2/w2_seed046","w2_seed047":"/home/tatsu/calib_w2/w2_seed047","w2_seed048":"/home/tatsu/calib_w2/w2_seed048"}
print("| 本 | クラウドで 1,740 試行を終えた時刻 | 手元 | 使う方 |"); print("|---|---|---|---|")
for r in sorted(done):
    L=local.get(r)
    if L is None: lt="手元の本は無い（マックの種でもない）"
    else:
        fin=glob.glob(L+"/output/ledgers/cells/*/seed*.done")
        lt="1,740 試行を終えていた" if fin else "終えていない（一時停止の後、SIGTERM で終わらせた。途中までの出力は残してある）"
    use="クラウド" if (L is None or "終えていない" in lt) else "要確認（両方が終えていた）"
    print(f"| {r} | {done[r]['cloud_finished']} | {lt} | {use} |")
PY
)
cd $RES && git pull -q --rebase origin results-2026-09-27
printf '\n## 指示 23 の 3：手元の較正 12 本を終わらせた（%s）\n- クラウドの 13 本を全部持ってきて、sha256 の確かめが済んだ（~/cloud/cloud_watch.log）。\n- 手元の 12 本の模型の過程（%s 個）に SIGTERM と SIGCONT を送って終わらせた。途中までの出力は消していない。\n- どの本をどちらで使うか（指示 19 の決まり：先に 1,740 試行を終えた方）：\n\n%s\n' "$T" "$(echo $PIDS | wc -w)" "$TABLE" >> control/2026-10-08_クラウドの開始_走行の係.md
python3 - "$T" <<'PY'
import re, sys
p="control/受け箱/デスクトップの走行の係.md"; s=open(p,encoding="utf-8").read(); t=sys.argv[1]
m=re.search(r"^## 指示 23（", s, re.M); k=s.index("\n", s.index("受領（", m.start()))+1
while s[k:].startswith("- "): k=s.index("\n",k)+1
s=s[:k]+f"- 3：{t} に、クラウドの 13 本の持ち帰りと確かめが済んだので、手元の 12 本を SIGTERM で終わらせた（出力は残した）。使う方の表は報告に書いた。\n"+s[k:]
open(p,"w",encoding="utf-8").write(s)
PY
git add -A control ataru-0608/game_mode && git commit -q -m "手元の較正 12 本を終わらせた（クラウドの 13 本が済んだため）（走行の係）" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 && break; sleep 20; git pull -q --rebase origin results-2026-09-27; done
echo "済み $T"
