#!/bin/bash
# 2026-10-01 午前・改訂の予約の委任書の段 6：お店の世界（設定 config/sweep_shop_hide1_s1_2026-10-01.json：二階を伏せない）の 26 腕 × 種 1〜20（マック）。並列 8。
#  共通の旗：今の 11 腕と同じ一式 ＋ --answer-gap --strict-pc --cf-value --probe-world、お店の世界の旗、--e-price 0.0187371（L50 の較正値）。
#  腕（世界 2 → 世界 1）：A＝今の規則（λ＝0・L50・L90・0.2・0.3）、C＝--cf-learn（λ＞0 の 4 つ）、F＝--shop-keep-cue（λ＞0 の 4 つ）。
#  忘れる値段 λ は --v39-price（絶対値）。台帳は全部残す（~/v310cprod/<腕>）。腕ごとに flag.json・台帳の本体の sha256 の一覧を結果のブランチ mac/<腕>/ に上げる。
# 空き − 2 GB ＜ 15 GB なら、腕の区切りで止めて control/ に書き、空きが戻るのを 5 分ごとに待つ。種 21〜40 は走らせない・読まない。
set -u
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-strictpc; cd $W
OUT=$HOME/v310cprod; RES=$HOME/v33prod/results; LOG=$OUT/chain.log; mkdir -p $OUT
CTRL=control/2026-10-01_穴の直しとC_マック.md
WK=${WORKERS:-8}
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
freegb() { df -Pk "$HOME" | awk 'NR==2 {printf "%d", $4/1048576}'; }
ctl() {
  ( cd $RES && git pull -q --rebase origin results-2026-09-27
    echo "$1" >> "$CTRL"; git add "$CTRL" && git commit -q -m "control：穴の直しと C・段 6 の走行（マック）" \
    && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 5; done ) >> "$LOG" 2>&1
}
L=$(python3.12 -c "import json;d=json.load(open('$HOME/v310prod/be_calib.json'))['λ'];print(repr(d['50']),repr(d['90']))")
read L50 L90 <<< "$L"
CS=config/sweep_shop_hide1_s1_2026-10-01.json
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --dump-answers --dump-routing --answer-gap --strict-pc --cf-value --probe-world --e-price $L50 --workers $WK --no-compare"
# 腕：名前|config|λ|足す旗
ARMS=()
for WD in 2 1; do
  for x in "lam000:0" "lam0187:$L50" "lam0990:$L90" "lam020:0.2" "lam030:0.3"; do ARMS+=("cw${WD}_A_${x%%:*}|$CS|${x#*:}|--shop-world $WD"); done
  for x in "lam0187:$L50" "lam0990:$L90" "lam020:0.2" "lam030:0.3"; do ARMS+=("cw${WD}_C_${x%%:*}|$CS|${x#*:}|--shop-world $WD --cf-learn"); done
  for x in "lam0187:$L50" "lam0990:$L90" "lam020:0.2" "lam030:0.3"; do ARMS+=("cw${WD}_F_${x%%:*}|$CS|${x#*:}|--shop-world $WD --shop-keep-cue"); done
done
say "始める（コード $(git rev-parse --short HEAD)、未コミット $(git status --short -- tools abm | wc -l | tr -d ' ')、並列 $WK）：${#ARMS[@]} 腕"
ctl "- $(date '+%H:%M') 段 6 の走行を始めた（コード $(git rev-parse --short HEAD)、並列 $WK、${#ARMS[@]} 腕 × 種 1〜20、置き場所 ~/v310cprod。世界 2 → 世界 1、各世界で A・C・F）。"
for A in "${ARMS[@]}"; do
  IFS='|' read -r ARM CFG LAM EX <<< "$A"
  warned=0
  while (( $(freegb) - 2 < 15 )); do
    [[ $warned == 0 ]] && { say "★ 空き $(freegb) GB、腕 $ARM の前で止める"; ctl "- $(date '+%H:%M') ★ 空き $(freegb) GB で、腕 $ARM の前（腕の区切り）で止めた。空きが 17 GB 以上に戻れば続ける。"; warned=1; }
    sleep 300
  done
  say "腕 $ARM（λ＝$LAM $EX）"
  caffeinate -dimsu python3.12 tools/v3_run.py $CFG $OUT/$ARM $FL --v39-price $LAM $EX >> $OUT/$ARM.log 2>&1
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
    f"# {arm}（マック）\n\nお店の世界（二階を伏せない）、--answer-gap・--strict-pc・--cf-value・--probe-world・--e-price（ブランチ strict-pc-2026-10-01）、種 1〜20。ここは flag.json と台帳の本体の sha256 の一覧（{len(rows)} 本）だけ。"
    f"台帳・side（診断 cfvalue・cflearn・試験 probe・お店 shop を含む）はマックの ~/v310cprod/{arm} に全部残している。\n")
print("sha", arm, len(rows))
P
  python3.12 tools/results_push.py $RES mac $ARM "結果：mac の $ARM（お店の世界・穴の直しと C）の flag.json・sha256 の一覧" >> "$LOG" 2>&1 && say "腕 $ARM を上げた" || say "★ 腕 $ARM を上げられなかった"
  ctl "- $(date '+%H:%M') 腕 $ARM（λ＝$LAM${EX:+ $EX}）：20 本のうち $n 本が走り終わった（rc＝$rc）。"
done
say "CDONE"
ctl "- $(date '+%H:%M') 段 6 の走行がすべて終わった。"
