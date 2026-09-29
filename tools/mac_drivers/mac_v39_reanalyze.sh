#!/bin/bash
# 2026-09-29 昼：v3.9 のマックの 8 腕の、台帳ごとの解析とまとめのかけ直し（走行はしない。台帳は .done があるので飛ばされる）。
# わけ：analysis_sbe_2026-09-19/recon_removed.py:10-11 が決め打ちの場所 /Users/tatsu-admin/sfn/sfn-compression-abm の analysis_v3a2cf_2026-09-17 を読み、
#   そこの rext_port_stage1.py が v3.9-main の手当て（⟨消去⟩の行）の前の版だったため、160 本すべての走査の版 8 が「既知物理行がsnapshotから消失」で落ちた。
#   そのファイルを v3.9-main の版に差し替えた（前の版は rext_port_stage1.py.v3.9前_2026-09-29 に残した。差分は ⟨消去⟩ のときだけ働く）。
# 腕ごとの一行（CTRL）は 03:52〜05:59 の走行で上がっているので、ここでは足さない。終わったら二台の台帳の一致を比べ直して control/ に書く。
set -u
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-v39mac
OUT=$HOME/v39prod; RES=$HOME/v33prod/results; LOG=$OUT/mac_v39.log; mkdir -p $OUT
CHK=/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_v39_2026-09-29/check_mac/v38_on
CTRL=control/2026-09-29_予算_腕ごと_マック.md
say() { echo "$(date '+%F %T') [v39re] $*" >> "$LOG"; }
pushctl() {
  ( cd $RES && git add "control/$1" && git commit -q -m "control：$1" && for i in 1 2 3 4 5 6; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 10; done
    git fetch -q origin results-2026-09-27 && git diff --quiet origin/results-2026-09-27 -- "control/$1" ) >> "$LOG" 2>&1 && say "control/$1 を上げた（確かめ済み）" || say "★ control/$1 を上げられなかった"
}
say "解析とまとめのかけ直しを始める（8 腕）"
(cd $W && MACHINE=mac JOBS=6 MINFREE_GB=30 OUT=$OUT HOST=mac RESULTS=$RES PY=python3.12 ARMSF=tools/prod_v39_mac_arms.tsv caffeinate -dimsu bash tools/prod_v39.sh >> $OUT/prod_v39_stdout.log 2>&1)
say "prod_v39.sh が終わった rc=$?"
git -C $RES fetch -q origin results-2026-09-27
CMP=$(python3.12 - "$OUT" "$RES" <<'P' 2>>"$LOG"
import json, subprocess, sys, os
out, res = sys.argv[1], sys.argv[2]
def git(*a): return subprocess.run(["git", "-C", res, *a], capture_output=True, text=True)
dirs = [l.strip() for l in git("-c", "core.quotepath=false", "ls-tree", "--name-only", "origin/results-2026-09-27", "ataru-0608/").stdout.splitlines() if "/v39" in l]
desk = {}
for d in dirs:
    p = git("show", f"origin/results-2026-09-27:{d}/flag.json")
    if p.returncode: continue
    fl = json.loads(p.stdout)
    desk[(str(fl.get("v39_budget")), fl.get("v39_u"), fl.get("v39_init"), str(fl.get("v39_a")))] = d
lines = []
for arm in ("v39new_n70_hide_Binf", "v39new_n70_hide_B100", "v39new_n70_hide_B075", "v39new_n70_hide_B050", "v39new_n70_hide_B025"):
    try: fl = json.load(open(f"{out}/{arm}/flag.json"))
    except Exception: lines.append(f"- {arm}：マックの走行が無い"); continue
    key = (str(fl.get("v39_budget")), fl.get("v39_u"), fl.get("v39_init"), str(fl.get("v39_a")))
    d = desk.get(key)
    if not d: lines.append(f"- {arm}（予算 {key[0]}）：デスクトップに同じ旗の腕がまだ無い"); continue
    p = git("show", f"origin/results-2026-09-27:{d}/sha256.jsonl")
    dt = {(r["cell"], r["seed"]): r["body_sha256"] for r in map(json.loads, p.stdout.splitlines())} if p.returncode == 0 else {}
    mac = {(r["cell"], r["seed"]): r["body_sha256"] for r in map(json.loads, open(f"{out}/{arm}/post/sha256.jsonl"))}
    both = set(mac) & set(dt); same = sorted(k for k in both if mac[k] == dt[k]); diff = sorted(k for k in both if mac[k] != dt[k])
    lines.append(f"- {arm}（予算 {key[0]}）↔ {d}：両方にある {len(both)} 本のうち一致 {len(same)}・不一致 {len(diff)}" + (f"（不一致の種 {[k[1] for k in diff]}）" if diff else ""))
print("\n".join(lines))
P
)
F="$(date +%Y-%m-%d_%H%M)_v3.9_二台の台帳の一致_やり直し_マック.md"
printf '# v3.9 の主の 5 腕：二台の台帳の一致（マックの Code の台本、%s）　判断しない\n\n台帳の本体（見出しを除く）の sha256 を、腕の sha256.jsonl で比べた。デスクトップの腕は、flag.json の v39_budget・v39_u・v39_init・v39_a が同じものを選んだ。\n\n%s\n' "$(date '+%F %T')" "$CMP" > "$RES/control/$F"
pushctl "$F"
say "V39REDONE"
