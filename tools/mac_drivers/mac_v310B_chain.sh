#!/bin/bash
# 2026-09-29 の委任書「ACT-R 形の記録の重み・A の走らせ直し・B（1 ビットの値段）」の 4（マックの B）：人の手なしで最後まで流す台本。
# 端末から切り離し、caffeinate -dimsu の下で走らせる（tools/mac_drivers/launch_detached.py）。
# 1 v3.9 の解析のかけ直し（mac_v39_reanalyze.sh）が終わるのを待つ（同時に走らせない）。
# 2 先の確かめ（v3.10 のコード・--v39-price 0・旗は均等 が、マックの v3.9 の予算無限と一字一句同じか）を待ち、違えば control/ に書いて止まる。
# 3 control/2026-09-29_v3.10の較正.md を待ち、λ の 4 段階を tools/mac_drivers/v310_lambda.py で読む。読めなければ control/ に書き、
#   ~/v310prod/lambda.json（人が書く上書き）が置かれるまで待つ。
# 4 腕の表 tools/prod_v310B_mac_arms.tsv を作り、tools/prod_v39.sh（v3.10-main）で上から流す（並列 6、台帳は全部残す）。
#   腕ごとの一行は tools/v39_summary.py が作り、CTRL（control/2026-09-29_v3.10_腕ごと_マック.md）に足して上げる。
# 5 終わったら、v310B_L0（λ＝0）の台帳の本体の sha256 を、デスクトップの v310A の予算無限の腕（flag.json の v39_decay＝actr・
#   v39_budget＝inf・v39_price なし・v39_u＝global）と比べ、control/ に書く。
# ログ：~/v310prod/mac_v310B.log（この台本）・~/v310prod/prod_v39.log（本番の台本）。
set -u
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-v310mac
OUT=$HOME/v310prod; RES=$HOME/v33prod/results; LOG=$OUT/mac_v310B.log; mkdir -p $OUT
CHK=/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_v310_2026-09-29/check_mac/price0
CAL=control/2026-09-29_v3.10の較正.md
CTRL=control/2026-09-29_v3.10_腕ごと_マック.md
ARMSF=tools/prod_v310B_mac_arms.tsv
say() { echo "$(date '+%F %T') [v310B] $*" >> "$LOG"; }
pushctl() {
  ( cd $RES && git add "control/$1" && git commit -q -m "control：$1" && for i in 1 2 3 4 5 6; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 10; done
    git fetch -q origin results-2026-09-27 && git diff --quiet origin/results-2026-09-27 -- "control/$1" ) >> "$LOG" 2>&1 && say "control/$1 を上げた（確かめ済み）" || say "★ control/$1 を上げられなかった"
}
say "v3.9 の解析のかけ直しが終わるのを待つ"
until grep -q "V39REDONE" $HOME/v39prod/mac_v39.log 2>/dev/null; do sleep 60; done
say "先の確かめを待つ"
until [[ -s $CHK/manifest.jsonl ]]; do sleep 30; done
OK=$(python3.12 -c "import json;r=json.loads(open('$CHK/manifest.jsonl').readline());c=r.get('compare') or {};print(int(bool(c.get('snapshot_hash_equal')) and bool(c.get('body_sha_equal')) and not r.get('error')))")
python3.12 -c "import json;r=json.loads(open('$CHK/manifest.jsonl').readline());print(r.get('compare'), r.get('error'))" >> "$LOG"
if [[ "$OK" != "1" ]]; then
  say "★ 先の確かめが一致しなかった。走らせずに止める"
  F="$(date +%Y-%m-%d_%H%M)_v3.10の先の確かめが一致しない_マック.md"
  printf '# v3.10 の先の確かめが一致しない（マックの Code の台本、%s）\n\nv3.10-main（cd8dc52）の --v39-price 0（旗は均等）で、主・予算無限・seed001・最頻を走らせ、マックの v3.9 の v39new_n70_hide_Binf と比べたが、一致しなかった。B の腕は走らせずに止めた。\n\n比べの結果：%s\n' "$(date '+%F %T')" "$(tail -1 $LOG)" > "$RES/control/$F"; pushctl "$F"; exit 3
fi
say "先の確かめが一致した（全試行の指紋・本体の sha256）"
say "較正の知らせ（$CAL）を待つ"
until git -C $RES fetch -q origin results-2026-09-27 2>/dev/null && git -C $RES cat-file -e "origin/results-2026-09-27:$CAL" 2>/dev/null; do sleep 120; done
git -C $RES show "origin/results-2026-09-27:$CAL" > $OUT/較正.md
LAM=$(cd $W && python3.12 tools/mac_drivers/v310_lambda.py $OUT/較正.md); rc=$?
if [[ $rc != 0 ]]; then
  say "★ λ を読めなかった：$LAM"
  F="$(date +%Y-%m-%d_%H%M)_v3.10のλを読めない_マック.md"
  printf '# v3.10 の較正から λ を読めない（マックの Code の台本、%s）\n\n%s から、25・50・75・90 パーセンタイルの λ を、表の行（最初の欄が 25・50・75・90、次の欄が数）として一つずつ読めなかった。B は始めずに待っている。\n\n読んだもの：%s\n\n~/v310prod/lambda.json（{"25": …, "50": …, "75": …, "90": …}）が置かれたら、それを使って始める。\n' "$(date '+%F %T')" "$CAL" "$LAM" > "$RES/control/$F"; pushctl "$F"
  until [[ -s $OUT/lambda.json ]]; do sleep 60; done
  LAM=$(cd $W && python3.12 tools/mac_drivers/v310_lambda.py $OUT/較正.md) || { say "★ 上書きも読めない。止める"; exit 3; }
fi
say "λ：$LAM"
(cd $W && python3.12 - "$LAM" "$ARMSF" <<'P'
import json, sys
lam, out = json.loads(sys.argv[1]), sys.argv[2]
cfg, cell = "config/sweep_b2_hide_s1_2026-09-22.json", "f0.5000_th2.1000_first_order"
base = "--v39-decay actr --v39-budget inf"
arms = [("v310B_L0", f"{base} --v39-price 0"), ("v310B_L25", f"{base} --v39-price {lam['25']}"),
        ("v310B_L50", f"{base} --v39-price {lam['50']}"), ("v310B_L75", f"{base} --v39-price {lam['75']}"),
        ("v310B_L90", f"{base} --v39-price {lam['90']}"), ("v310B_Uabs_L50", f"{base} --v39-u abstain --v39-price {lam['50']}")]
with open(out, "w", encoding="utf-8") as f:
    f.write("# v3.10 のマックの分（B：1 ビットの値段 λ）。委任書「ACT-R 形の記録の重み・A の走らせ直し・B」の 4。上から順に。\n")
    f.write("# λ は control/2026-09-29_v3.10の較正.md の 25・50・75・90 パーセンタイル（tools/mac_drivers/mac_v310B_chain.sh が書いた）。台帳は全部残す。\n")
    f.write("# 列：機械\t腕\t設定\t基準\t腕の種類\t試行数\t残す\tセル\t腕の旗\n")
    for a, fl in arms:
        f.write(f"mac\t{a}\t{cfg}\t0.7\tnew\t1740\tall\t{cell}\t{fl}\n")
P
) >> "$LOG" 2>&1
cat $W/$ARMSF >> "$LOG"
(cd $W && git add $ARMSF tools/mac_drivers && git commit -q -m "v3.10 のマックの B の腕の表と台本（λ は較正の値）" && git push -q origin v3.10mac-2026-09-29) >> "$LOG" 2>&1 && say "腕の表をブランチ v3.10mac-2026-09-29 に上げた" || say "★ 腕の表をブランチに上げられなかった（走行は続ける）"
if [[ ! -e "$RES/$CTRL" ]]; then
  printf '%s\n' "# v3.10（B：1 ビットの値段 λ）の腕ごとの一行（マック）　判断しない" "" \
    "委任書「ACT-R 形の記録の重み・A の走らせ直し・B（1 ビットの値段）」の 4。台本 tools/prod_v39.sh（v3.10-main、ブランチ v3.10mac-2026-09-29）が、腕が終わるたびに tools/v39_summary.py の一行を足して上げる。" \
    "評価：s1（種 1〜20）、セル f0.5000_th2.1000_first_order（最頻）、1,740 試行、各腕 20 本。すべて --v39-decay actr・予算無限。λ は control/2026-09-29_v3.10の較正.md の値：$LAM" "" > "$RES/$CTRL"
  pushctl "$(basename "$CTRL")"
fi
say "6 腕を流す"
(cd $W && MACHINE=mac JOBS=6 MINFREE_GB=20 OUT=$OUT HOST=mac RESULTS=$RES PY=python3.12 ARMSF=$ARMSF CTRL=$CTRL caffeinate -dimsu bash tools/prod_v39.sh >> $OUT/prod_v39_stdout.log 2>&1)
say "prod_v39.sh が終わった rc=$?"
git -C $RES fetch -q origin results-2026-09-27
CMP=$(python3.12 - "$OUT" "$RES" <<'P' 2>>"$LOG"
import json, subprocess, sys
out, res = sys.argv[1], sys.argv[2]
def git(*a): return subprocess.run(["git", "-C", res, *a], capture_output=True, text=True)
dirs = [l.strip() for l in git("-c", "core.quotepath=false", "ls-tree", "--name-only", "origin/results-2026-09-27", "ataru-0608/").stdout.splitlines() if "/v310" in l]
cand = []
for d in dirs:
    p = git("show", f"origin/results-2026-09-27:{d}/flag.json")
    if p.returncode: continue
    fl = json.loads(p.stdout)
    if fl.get("v39_decay") == "actr" and str(fl.get("v39_budget")) in ("inf", "None") and fl.get("v39_price") is None \
            and fl.get("v39_u") == "global" and fl.get("v39_init") == "two" and str(fl.get("v39_a")) == "0.5":
        cand.append(d)
if len(cand) != 1:
    print(f"- v310B_L0：デスクトップの予算無限の腕が一つに決まらない（{cand}）"); sys.exit(0)
d = cand[0]
p = git("show", f"origin/results-2026-09-27:{d}/sha256.jsonl")
dt = {(r["cell"], r["seed"]): r["body_sha256"] for r in map(json.loads, p.stdout.splitlines())} if p.returncode == 0 else {}
mac = {(r["cell"], r["seed"]): r["body_sha256"] for r in map(json.loads, open(f"{out}/v310B_L0/post/sha256.jsonl"))}
both = set(mac) & set(dt); diff = sorted(k for k in both if mac[k] != dt[k])
print(f"- v310B_L0（actr・予算無限・λ＝0）↔ {d}：両方にある {len(both)} 本のうち一致 {len(both) - len(diff)}・不一致 {len(diff)}"
      + (f"（不一致の種 {[k[1] for k in diff]}）" if diff else ""))
P
)
F="$(date +%Y-%m-%d_%H%M)_v3.10_λ0と予算無限の一致_マック.md"
printf '# v3.10 の v310B_L0 と、デスクトップの v310A の予算無限：台帳の一致（マックの Code の台本、%s）　判断しない\n\n委任書 1-2「λ＝0 のときは、予算無限の v3.9 と一字一句同じ」により、同じ actr の重みでは二つは同じ台帳になるはずのもの。台帳の本体（見出しを除く）の sha256 を、腕の sha256.jsonl で比べた。\n\n%s\n' "$(date '+%F %T')" "$CMP" > "$RES/control/$F"
pushctl "$F"
say "V310BDONE"
