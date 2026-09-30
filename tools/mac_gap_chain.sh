#!/bin/bash
# アストラさんの返事「消す範囲」（2026-09-30 深夜）：今の世界・--answer-gap ありの 7 腕を種 1〜20 で走らせる（マック）。
# 腕：λ＝0・L50・L90・0.2・0.3、λ＝0.2・0.3 の U 常時棄権。旗は今日の 11 腕と同じ一式（B＋E、--u-struct --relearn-init --tie-struct
#   --amb-local --dump-answers --dump-routing）に --answer-gap を足す。並列は 4（Codex の共有の診断が同じ機械で動くため）。
#   台帳は全部残す（~/v310gapprod/<腕>）。腕ごとに flag.json・台帳の本体の sha256 の一覧を結果のブランチ mac/<腕>/ に上げる。
# 空き − 2 GB ＜ 15 GB なら、腕の区切りで止めて control/ に書き、空きが戻るのを 5 分ごとに待つ。種 21〜40 は走らせない・読まない。
# 元は tools/mac_urta_chain.sh（ブランチ routing-urta-2026-09-30）。
set -u
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-answergap; cd $W
OUT=$HOME/v310gapprod; RES=$HOME/v33prod/results; LOG=$OUT/chain.log; mkdir -p $OUT
CTRL=control/2026-10-01_answer-gap_7腕の走行_マック.md
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
freegb() { df -Pk "$HOME" | awk 'NR==2 {printf "%d", $4/1048576}'; }
ctl() {
  ( cd $RES && git pull -q --rebase origin results-2026-09-27
    [[ -e "$CTRL" ]] || printf '%s\n' "# 今の世界・--answer-gap ありの 7 腕（種 1〜20）の走行（マック）" "" "アストラさんの返事「消す範囲」（2026-09-30 深夜）。台本 tools/mac_gap_chain.sh（ブランチ answer-gap-2026-09-30）。台帳は ~/v310gapprod に全部残す。並列 4。" "" > "$CTRL"
    echo "$1" >> "$CTRL"; git add "$CTRL" && git commit -q -m "control：answer-gap の 7 腕の走行（マック）" \
    && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 5; done ) >> "$LOG" 2>&1
}
L=$(python3.12 -c "import json;d=json.load(open('$HOME/v310prod/be_calib.json'))['λ'];print(repr(d['25']),repr(d['50']),repr(d['75']),repr(d['90']))")
read L25 L50 L75 L90 <<< "$L"
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --dump-answers --dump-routing --answer-gap --workers 4 --no-compare"
ARMS="v310gap_lam000:0 v310gap_L50:$L50 v310gap_L90:$L90 v310gap_lam020:0.2 v310gap_lam030:0.3 v310gap_lam020_Uabs:0.2:abstain v310gap_lam030_Uabs:0.3:abstain"
say "始める（コード $(git rev-parse --short HEAD)、未コミット $(git status --short -- tools abm | wc -l | tr -d ' ')）：$ARMS"
for A in $ARMS; do
  ARM=${A%%:*}; rest=${A#*:}; LAM=${rest%%:*}; U=""; [[ "$rest" == *:abstain ]] && U="--v39-u abstain"
  warned=0
  while (( $(freegb) - 2 < 15 )); do
    [[ $warned == 0 ]] && { say "★ 空き $(freegb) GB、腕 $ARM の前で止める"; ctl "- $(date '+%H:%M') ★ 空き $(freegb) GB で、腕 $ARM の前（腕の区切り）で止めた。空きが 17 GB 以上に戻れば続ける。"; warned=1; }
    sleep 300
  done
  say "腕 $ARM（λ＝$LAM ${U}）"
  caffeinate -dimsu python3.12 tools/v3_run.py config/sweep_b2_hide_s1_2026-09-22.json $OUT/$ARM $FL --v39-price $LAM $U >> $OUT/$ARM.log 2>&1
  rc=$?
  n=$(ls $OUT/$ARM/ledgers/cells/*/seed*.done 2>/dev/null | wc -l | tr -d ' ')
  python3.12 - "$OUT/$ARM" "$ARM" "$RES/mac/$ARM" <<'P' >> "$LOG" 2>&1
import glob, gzip, hashlib, json, os, shutil, sys
root, arm, dest = sys.argv[1:4]
os.makedirs(dest, exist_ok=True)
rows = []
for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.jsonl.gz"))):
    if not os.path.exists(p[:-len(".jsonl.gz")] + ".done"):
        continue
    h = hashlib.sha256(); n = 0; header = None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == 0:
                header = json.loads(line); continue
            h.update(line.encode("utf-8")); n += 1
    rows.append({"arm": arm, "cell": os.path.basename(os.path.dirname(p)), "seed": int(os.path.basename(p)[4:7]),
                 "body_sha256": h.hexdigest(), "n_body": n, "code_commit": header.get("code_commit")})
with open(os.path.join(dest, "sha256.jsonl"), "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
shutil.copy(os.path.join(root, "flag.json"), os.path.join(dest, "flag.json"))
open(os.path.join(dest, "README.md"), "w", encoding="utf-8").write(
    f"# {arm}（マック）\n\n今の世界・--answer-gap あり（ブランチ answer-gap-2026-09-30）、種 1〜20。ここは flag.json と台帳の本体の sha256 の一覧（{len(rows)} 本）だけ。"
    f"台帳・side・答えの記録・届け先の記録（*.routing.jsonl）はマックの ~/v310gapprod/{arm} に全部残している。\n")
print("sha", arm, len(rows))
P
  python3.12 tools/results_push.py $RES mac $ARM "結果：mac の $ARM（answer-gap あり）の flag.json・sha256 の一覧" >> "$LOG" 2>&1 && say "腕 $ARM を上げた" || say "★ 腕 $ARM を上げられなかった"
  ctl "- $(date '+%H:%M') 腕 $ARM（λ＝$LAM${U:+、U 常時棄権}）：20 本のうち $n 本が走り終わった（rc＝$rc）。"
done
say "URTADONE"
ctl "- $(date '+%H:%M') 7 腕が終わった。"
