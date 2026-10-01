#!/bin/bash
# 2026-10-01 午前の返事の段 6：--answer-gap・--strict-pc（段 1 の後）・--cf-value を足した走行（マック）。種 1〜20。並列 8（ほかの作業が動いていなければ）。
#  1 お店の世界（予約の委任書の 5 節）：世界 2 → 世界 1。λ（絶対値）0・0.0187371・0.0990004・0.2・0.3 の通常と、λ＞0 の --shop-keep-cue。--probe-world つき。
#  2 今の世界：λ＝0・L50・L90・0.2・0.3、0.2・0.3 の U 常時棄権（7 腕）。
# 台帳は全部残す（~/v310spcprod/<腕>）。腕ごとに flag.json・台帳の本体の sha256 の一覧を結果のブランチ mac/<腕>/ に上げる。
# 空き − 2 GB ＜ 15 GB なら、腕の区切りで止めて control/ に書き、空きが戻るのを 5 分ごとに待つ。種 21〜40 は走らせない・読まない。
set -u
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-strictpc; cd $W
OUT=$HOME/v310spcprod; RES=$HOME/v33prod/results; LOG=$OUT/chain.log; mkdir -p $OUT
CTRL=control/2026-10-01_strict-pcの続き_マック.md
WK=${WORKERS:-8}
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
freegb() { df -Pk "$HOME" | awk 'NR==2 {printf "%d", $4/1048576}'; }
ctl() {
  ( cd $RES && git pull -q --rebase origin results-2026-09-27
    echo "$1" >> "$CTRL"; git add "$CTRL" && git commit -q -m "control：strict-pc の続き・段 6 の走行（マック）" \
    && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 5; done ) >> "$LOG" 2>&1
}
L=$(python3.12 -c "import json;d=json.load(open('$HOME/v310prod/be_calib.json'))['λ'];print(repr(d['50']),repr(d['90']))")
read L50 L90 <<< "$L"
C0=config/sweep_b2_hide_s1_2026-09-22.json; CS=config/sweep_shop_hide_s1_2026-10-01.json
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --dump-answers --dump-routing --answer-gap --strict-pc --cf-value --workers $WK --no-compare"
# 腕：名前|config|λ|足す旗
ARMS=()
for WD in 2 1; do
  ARMS+=("shop_w${WD}_lam000|$CS|0|--shop-world $WD --probe-world")
  for x in "lam0187:$L50" "lam0990:$L90" "lam020:0.2" "lam030:0.3"; do ARMS+=("shop_w${WD}_${x%%:*}|$CS|${x#*:}|--shop-world $WD --probe-world"); done
  for x in "lam0187:$L50" "lam0990:$L90" "lam020:0.2" "lam030:0.3"; do ARMS+=("shop_w${WD}_keep_${x%%:*}|$CS|${x#*:}|--shop-world $WD --probe-world --shop-keep-cue"); done
done
for x in "lam000:0:" "L50:$L50:" "L90:$L90:" "lam020:0.2:" "lam030:0.3:" "lam020_Uabs:0.2:--v39-u abstain" "lam030_Uabs:0.3:--v39-u abstain"; do
  n=${x%%:*}; r=${x#*:}; lam=${r%%:*}; ex=${r#*:}; ARMS+=("spc_${n}|$C0|$lam|$ex")
done
say "始める（コード $(git rev-parse --short HEAD)、未コミット $(git status --short -- tools abm | wc -l | tr -d ' ')、並列 $WK）：${#ARMS[@]} 腕"
ctl "- $(date '+%H:%M') 段 6 の走行を始めた（コード $(git rev-parse --short HEAD)、並列 $WK、${#ARMS[@]} 腕 × 種 1〜20、置き場所 ~/v310spcprod。お店の世界 2 → 1 → 今の世界）。"
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
    f"# {arm}（マック）\n\n--answer-gap・--strict-pc・--cf-value（ブランチ strict-pc-2026-10-01）、種 1〜20。ここは flag.json と台帳の本体の sha256 の一覧（{len(rows)} 本）だけ。"
    f"台帳・side（診断 cfvalue・試験 probe・お店 shop を含む）はマックの ~/v310spcprod/{arm} に全部残している。\n")
print("sha", arm, len(rows))
P
  python3.12 tools/results_push.py $RES mac $ARM "結果：mac の $ARM（--answer-gap・--strict-pc・--cf-value）の flag.json・sha256 の一覧" >> "$LOG" 2>&1 && say "腕 $ARM を上げた" || say "★ 腕 $ARM を上げられなかった"
  ctl "- $(date '+%H:%M') 腕 $ARM（λ＝$LAM${EX:+ $EX}）：20 本のうち $n 本が走り終わった（rc＝$rc）。"
done
say "SPCDONE"
ctl "- $(date '+%H:%M') 段 6 の走行がすべて終わった。"
