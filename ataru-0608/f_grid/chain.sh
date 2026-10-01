#!/bin/bash
# 2026-10-01 夜の委任書「開示の確率 f を振る小さな格子（お店の世界 2、A と C）」（デスクトップ、走行の係）。
#  コード：strict-pc-2026-10-01 の今の先頭（88e0e38）。本番の作業場所 ~/sfn/sfn-compression-abm。
#  旗：マックのお店の世界の腕と同じ一式 ＋ --e-price L50。腕：A（λ＝L50・L90）、C（--cf-learn、λ＝L50・L90）× f＝0.5 → 1.0 → 0.25。種 1〜20、並列 14。
#  f の設定：0.5 は元の設定、0.25・1.0 は写しで axes.f だけ変えたもの（~/fgrid、リポジトリの外）。セルの名前も f に合わせる。
#  空きの決まり（この依頼から）：WSL の中の使用量（df -B1 /）が LIMIT を超えそうなら、又は C: の空きが 5GB を切りそうなら、新しい腕を始めずに止める。
#  台帳：毎腕のあと、全部の種の試行ごとの表と sha256 を作ってから、種 1・2 だけ残す。side（記録）は全部残す（大きな jsonl は gzip）。
set -u
W=$HOME/sfn/sfn-compression-abm; cd $W
OUT=$HOME/fgrid; RES=$HOME/v33prod/results; LOG=$OUT/chain.log
CTRL="control/2026-10-01_fを振る格子_走行の係.md"
PY=/home/tatsu/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12
CODE=88e0e38
L50=0.01873710622997919; L90=0.09900039055209096
LIMIT=$(cat $OUT/limit_bytes)
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --dump-answers --dump-routing --answer-gap --strict-pc --cf-value --probe-world --e-price $L50 --shop-world 2 --workers 14 --no-compare --seeds $(seq -s, 1 20)"
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
used() { df -B1 / | awk 'NR==2 {print $3}'; }
cfree() { df -BG /mnt/c | awk 'NR==2 {gsub("G","",$4); print $4}'; }
ctl() {
  ( cd $RES && git pull -q --rebase origin results-2026-09-27
    echo "$1" >> "$CTRL"; git add "$CTRL" && git commit -q -m "control：f を振る格子（走行の係）

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
    mkdir -p ataru-0608/f_grid/$ARM && cp $OUT/$ARM/flag.json $OUT/tables/$ARM/sha256.jsonl $OUT/tables/$ARM/trials.tsv.gz ataru-0608/f_grid/$ARM/ \
    && git add ataru-0608/f_grid/$ARM && git commit -q -m "f を振る格子：$ARM の flag・sha256・試行ごとの表（走行の係）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
    && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 5; done ) >> "$LOG" 2>&1
}
git fetch -q origin strict-pc-2026-10-01 && git checkout -q --detach $CODE || { say "★ checkout に失敗"; exit 2; }
say "始める（コード $(git rev-parse --short HEAD)、未コミット $(git status --short -- tools abm | wc -l)、上限 $LIMIT）"
ctl "- $(date '+%H:%M') 12 腕を始めた（コード $(git rev-parse --short HEAD)、並列 14、置き場所 ~/fgrid）。"
for F in "f050 0.5000 config/sweep_shop_hide1_s1_2026-10-01.json" "f100 1.0000 $OUT/sweep_shop_hide1_f100_s1_2026-10-01.json" "f025 0.2500 $OUT/sweep_shop_hide1_f025_s1_2026-10-01.json"; do
  read FT FV CFG <<< "$F"
  for A in "A_L50 $L50" "A_L90 $L90" "C_L50 $L50 --cf-learn" "C_L90 $L90 --cf-learn"; do
    read RULE LAM EX <<< "$A"
    ARM=fg_${FT}_$RULE
    diskok "腕 $ARM"
    say "腕 $ARM（f＝$FV、λ＝$LAM ${EX:-}）使用量 $(used)"
    nice -n 10 $PY tools/v3_run.py $CFG $OUT/$ARM $FL --cells f${FV}_th2.1000_first_order --v39-price $LAM ${EX:-} >> $OUT/$ARM.log 2>&1
    rc=$?; n=$(ls $OUT/$ARM/ledgers/cells/*/seed*.done 2>/dev/null | wc -l); err=$(grep -c '"error"' $OUT/$ARM/manifest.jsonl 2>/dev/null)
    say "腕 $ARM 終わり rc=$rc 完走 $n 誤り ${err:-?}"
    post $ARM
    ctl "- $(date '+%H:%M') 腕 $ARM（f＝$FV、λ＝$LAM ${EX:-}）：完走 $n／20、誤り ${err:-?}、rc=$rc。WSL の中の使用量 $(used) B、C: の空き $(cfree) GB。"
  done
done
ctl "- $(date '+%H:%M') 12 腕が走り終わった。"
say "全部終わり"
