#!/bin/bash
# 2026-10-02 朝の委任書「C の格子（例外の頻度 × ドアを問う割合 × λ）」の段 2（デスクトップ、走行の係）。f の格子の台本の写し。
#  コード：strict-pc-2026-10-01 の今の先頭（88e0e38）。本番の作業場所 ~/sfn/sfn-compression-abm。
#  旗：マックのお店の世界の腕と同じ一式 ＋ --e-price L50。腕：A（λ＝L50・L90）、C（--cf-learn、λ＝L50・L90）× f＝0.5 → 1.0 → 0.25。種 1〜20、並列 14。
#  f の設定：0.5 は元の設定、0.25・1.0 は写しで axes.f だけ変えたもの（~/fgrid、リポジトリの外）。セルの名前も f に合わせる。
#  空きの決まり（この依頼から）：WSL の中の使用量（df -B1 /）が LIMIT を超えそうなら、又は C: の空きが 5GB を切りそうなら、新しい腕を始めずに止める。
#  台帳：毎腕のあと、全部の種の試行ごとの表と sha256 を作ってから、種 1・2 だけ残す。side（記録）は全部残す（大きな jsonl は gzip）。
set -u
W=$HOME/sfn/sfn-compression-abm; cd $W
OUT=$HOME/cgrid; RES=$HOME/v33prod/results; LOG=$OUT/chain.log
CTRL="control/2026-10-02_Cの格子_走行の係.md"
PY=/home/tatsu/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12
CODE=da80915
L50=0.01873710622997919; L90=0.09900039055209096
LIMIT=78231291392
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --dump-answers --dump-routing --answer-gap --strict-pc --cf-value --probe-world --e-price $L50 --shop-world 2 --workers 14 --no-compare --seeds $(seq -s, 1 20)"
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
used() { df -B1 / | awk 'NR==2 {print $3}'; }
cfree() { df -BG /mnt/c | awk 'NR==2 {gsub("G","",$4); print $4}'; }
ctl() {
  ( cd $RES && git pull -q --rebase origin results-2026-09-27
    echo "$1" >> "$CTRL"; git add "$CTRL" && git commit -q -m "control：C の格子（走行の係）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
    && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 5; done ) >> "$LOG" 2>&1
}
diskok() {
  local u c; u=$(used); c=$(cfree)
  if (( u > LIMIT || c < 6 )); then say "★ 使用量 $u B・C: の空き ${c} GB、$1 の前で止める"; ctl "- $(date '+%H:%M') ★ WSL の中の使用量 $u B（上限 $LIMIT B）・C: の空き ${c} GB。$1 の前（腕の区切り）で止めた。"; exit 3; fi
}
post() {
  local ARM=$1
  $PY $HOME/ufprod/extract.py "$OUT/$ARM" "$OUT/tables/$ARM" 1,2 >> "$LOG" 2>&1 || { say "★ 表の取り出しに失敗：$ARM（台帳は消さない）"; return 1; }
  find $OUT/$ARM/side -name "*.jsonl" -size +1M ! -name "*.shop.jsonl" -exec gzip -f {} \;
  ( cd $RES && git pull -q --rebase origin results-2026-09-27
    mkdir -p ataru-0608/c_grid/$ARM && cp $OUT/$ARM/flag.json $OUT/tables/$ARM/sha256.jsonl $OUT/tables/$ARM/trials.tsv.gz ataru-0608/c_grid/$ARM/ \
    && git add ataru-0608/c_grid/$ARM && git commit -q -m "C の格子：$ARM の flag・sha256・試行ごとの表（走行の係）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
    && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 5; done ) >> "$LOG" 2>&1
}
git fetch -q origin shopdoor-2026-10-02 && git checkout -q --detach $CODE || { say "★ checkout に失敗"; exit 2; }
say "始める（コード $(git rev-parse --short HEAD)、未コミット $(git status --short -- tools abm | wc -l)、上限 $LIMIT）"
ctl "- $(date '+%H:%M') 28 腕を始めた（コード $(git rev-parse --short HEAD)、並列 14、置き場所 ~/cgrid）。"
CS=config/sweep_shop_hide1_s1_2026-10-01.json
ARMS=()
for LL in "L50 $L50" "L90 $L90"; do
  read LN LV <<< "$LL"
  for E in 0.1 0.2 0.3 0.5; do
    for D in none 0.3 0.5; do
      DX=""; [[ $D != none ]] && DX="--shop-door-p $D"
      ARMS+=("cg_C_${LN}_e${E}_d${D}|$LV|--cf-learn --shop-exc $E $DX")
    done
  done
done
for E in 0.1 0.2 0.3 0.5; do ARMS+=("cg_A_L50_e${E}_d0.5|$L50|--shop-exc $E --shop-door-p 0.5"); done
for A in "${ARMS[@]}"; do
  IFS='|' read -r ARM LAM EX <<< "$A"
  diskok "腕 $ARM"
  say "腕 $ARM（λ＝$LAM $EX）使用量 $(used)"
  nice -n 10 $PY tools/v3_run.py $CS $OUT/$ARM $FL --cells f0.5000_th2.1000_first_order --v39-price $LAM $EX >> $OUT/$ARM.log 2>&1
  rc=$?; n=$(ls $OUT/$ARM/ledgers/cells/*/seed*.done 2>/dev/null | wc -l); err=$(grep -c '"error"' $OUT/$ARM/manifest.jsonl 2>/dev/null)
  say "腕 $ARM 終わり rc=$rc 完走 $n 誤り ${err:-?}"
  post $ARM
  ctl "- $(date '+%H:%M') 腕 $ARM（λ＝$LAM $EX）：完走 $n／20、誤り ${err:-?}、rc=$rc。WSL の中の使用量 $(used) B、C: の空き $(cfree) GB。"
done
ctl "- $(date '+%H:%M') 28 腕が走り終わった。"
say "全部終わり"
