#!/bin/bash
# 2026-09-29 深夜の委任書「記憶予算・三段階の忘却（v3.9）の走行（マックの分）」：人の手なしで最後まで流す台本（端末から切り離し、caffeinate -dimsu の下）。
# 1 先の確かめ（旗を切った v3.9 が、マックの v3.8 の v38new_n70_hide・seed001・θ′2.1・最頻と一字一句同じか）を待ち、違えば control/ に書いて止まる。
# 2 tools/prod_v39.sh（v3.9-main、作業場所 sfn-compression-abm-v39mac）で、tools/prod_v39_mac_arms.tsv の 8 腕を上から流す（並列 6、台帳は全部残す）。
#   腕ごとの一行は tools/v39_summary.py が作り、CTRL（control/2026-09-29_予算_腕ごと_マック.md）に足して上げる（prod_v39.sh の中）。
# 3 終わったら、主の 5 腕の台帳の本体の sha256 を、デスクトップの同じ予算の腕（ataru-0608/v39*/flag.json の v39_budget と v39_u で選ぶ）と比べ、control/ に書く。
# ログ：~/v39prod/mac_v39.log（この台本）・~/v39prod/prod_v39.log（本番の台本）。
set -u
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-v39mac
OUT=$HOME/v39prod; RES=$HOME/v33prod/results; LOG=$OUT/mac_v39.log; mkdir -p $OUT
CHK=/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_v39_2026-09-29/check_mac/v38_on
CTRL=control/2026-09-29_予算_腕ごと_マック.md
say() { echo "$(date '+%F %T') [v39] $*" >> "$LOG"; }
pushctl() {
  ( cd $RES && git add "control/$1" && git commit -q -m "control：$1" && for i in 1 2 3 4 5 6; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 10; done
    git fetch -q origin results-2026-09-27 && git diff --quiet origin/results-2026-09-27 -- "control/$1" ) >> "$LOG" 2>&1 && say "control/$1 を上げた（確かめ済み）" || say "★ control/$1 を上げられなかった"
}
say "先の確かめを待つ"
until [[ -s $CHK/manifest.jsonl ]]; do sleep 30; done
OK=$(python3.12 -c "import json;r=json.loads(open('$CHK/manifest.jsonl').readline());c=r.get('compare') or {};print(int(bool(c.get('snapshot_hash_equal')) and bool(c.get('body_sha_equal')) and not r.get('error')))")
python3.12 -c "import json;r=json.loads(open('$CHK/manifest.jsonl').readline());print(r.get('compare'), r.get('error'))" >> "$LOG"
if [[ "$OK" != "1" ]]; then
  say "★ 先の確かめが一致しなかった。走らせずに止める"
  F="$(date +%Y-%m-%d_%H%M)_v3.9の先の確かめが一致しない_マック.md"
  printf '# v3.9 の先の確かめが一致しない（マックの Code、%s）\n\n旗を切った v3.9（v3.9-main）で、マックの v3.8 の v38new_n70_hide・seed001・θ′2.1・最頻（~/v38prod）を走らせ直したが、一致しなかった。委任書に従い、v3.9 の腕は走らせずに止めた。\n\n比べの結果：%s\n' "$(date '+%F %T')" "$(tail -1 $LOG)" > "$RES/control/$F"; pushctl "$F"; exit 3
fi
say "先の確かめが一致した（全試行の指紋・本体の sha256）"
if [[ ! -e "$RES/$CTRL" ]]; then
  printf '%s\n' "# v3.9（記憶予算・三段階の忘却）の腕ごとの一行（マック）　判断しない" "" \
    "委任書「記憶予算・三段階の忘却（v3.9）の走行（マックの分）」の 2。台本 tools/prod_v39.sh（v3.9-main、ブランチ v3.9mac-2026-09-29）が、腕が終わるたびに tools/v39_summary.py の一行を足して上げる。" \
    "評価：s1（種 1〜20）、セル f0.5000_th2.1000_first_order（最頻）、1,740 試行、各腕 20 本。予算は B_ref＝55344.5（デスクトップの較正）から。" "" > "$RES/$CTRL"
  pushctl "$(basename "$CTRL")"
fi
say "8 腕を流す"
(cd $W && MACHINE=mac JOBS=6 MINFREE_GB=30 OUT=$OUT HOST=mac RESULTS=$RES PY=python3.12 ARMSF=tools/prod_v39_mac_arms.tsv CTRL=$CTRL caffeinate -dimsu bash tools/prod_v39.sh >> $OUT/prod_v39_stdout.log 2>&1)
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
F="$(date +%Y-%m-%d_%H%M)_v3.9_二台の台帳の一致_マック.md"
printf '# v3.9 の主の 5 腕：二台の台帳の一致（マックの Code の台本、%s）　判断しない\n\n台帳の本体（見出しを除く）の sha256 を、腕の sha256.jsonl で比べた。デスクトップの腕は、flag.json の v39_budget・v39_u・v39_init・v39_a が同じものを選んだ。\n\n%s\n' "$(date '+%F %T')" "$CMP" > "$RES/control/$F"
pushctl "$F"
say "V39CHAINDONE"
