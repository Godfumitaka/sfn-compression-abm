#!/bin/bash
# 2026-10-01 午後の追加の委任書「D-最小のしきい値を細かく」：τ＝0.15・0.25・0.4・0.6・1.0・1.6（走らせる前に固定）× 世界 2 → 1、計 12 腕。
# 以下は chain.sh（8 腕）の写し。設定・旗・種 1〜20・並列 14・台帳の残し方は同じ。
#  コード：ブランチ use-forget-2026-10-01（マックの strict-pc-2026-10-01 の bc5cd13 の上に --use-forget）。本番の作業場所 ~/sfn/sfn-compression-abm。
#  共通の旗：マックの段 6 の一式（tools/mac_c_chain.sh の FL）＋ お店の世界 ＋ --e-price/--v39-price＝L50 ＋ --use-forget τ。並列 14、優先度を下げる。
#  較正：世界 2・1、τ＝−∞、--use-forget-dump-s、種 41〜60。四つの分位点（両世界を合わせる）を tau.json に固定してから腕を始める。
#  腕：D25・D50・D75・D90 × 世界 2 → 1、種 1〜20。空き − 2 GB ＜ 15 GB なら新しい腕を始めず、control/ に書いて止める。
#  台帳：毎腕のあと、全部の種の試行ごとの小さな表（tables/<腕>/）を作ってから、決まりどおり最初の二つの種（1・2、較正は 41・42）だけ残す。
#  side の大きな jsonl は gzip で縮める（中身は残る）。
set -u
W=$HOME/sfn/sfn-compression-abm; cd $W
OUT=$HOME/ufprod; RES=$HOME/v33prod/results; LOG=$OUT/chain2.log
CTRL="control/2026-10-01_使用で強める腕D_走行の係.md"
PY=/home/tatsu/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12
CODE=fe8d567
L50=0.01873710622997919
CS=config/sweep_shop_hide1_s1_2026-10-01.json
# 較正の種 41〜60：同じ設定の写しで seeds.start を 1 → 41、名前を shop_hide1_s41 にしただけ（config/sweep_b2_hide_s41_2026-09-27.json と同じやり方。リポジトリの外に置く）
CS41=$OUT/sweep_shop_hide1_s41_2026-10-01.json
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --dump-answers --dump-routing --answer-gap --strict-pc --cf-value --probe-world --e-price $L50 --v39-price $L50 --workers 14 --no-compare"
S120=$(seq -s, 1 20); S4160=$(seq -s, 41 60)
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
freegb() { df -BG /mnt/c | awk 'NR==2 {gsub("G","",$4); print $4}'; }
ctl() {
  ( cd $RES && git pull -q --rebase origin results-2026-09-27
    echo "$1" >> "$CTRL"; git add "$CTRL" && git commit -q -m "control：腕 D の走行（走行の係）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
    && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 5; done ) >> "$LOG" 2>&1
}
diskok() {
  local f; f=$(freegb)
  if (( f - 2 < 15 )); then say "★ 空き ${f} GB、$1 の前で止める"; ctl "- $(date '+%H:%M') ★ C: の空き ${f} GB。$1 の前（腕の区切り）で止めた（新しい走行は始めない）。"; exit 3; fi
}
post() {   # 腕のあと：小さな表 → sha256 → 台帳を最初の二つの種だけ残す → side を縮める → 結果のブランチに上げる
  local ARM=$1 KEEP=$2
  $PY $OUT/extract.py "$OUT/$ARM" "$OUT/tables/$ARM" "$KEEP" >> "$LOG" 2>&1 || { say "★ 表の取り出しに失敗：$ARM（台帳は消さない）"; return 1; }
  find $OUT/$ARM/side -name "*.jsonl" -size +1M -exec gzip -f {} \;
  ( cd $RES && git pull -q --rebase origin results-2026-09-27
    mkdir -p ataru-0608/use_forget_D/$ARM && cp $OUT/$ARM/flag.json $OUT/tables/$ARM/sha256.jsonl ataru-0608/use_forget_D/$ARM/ \
    && cp $OUT/tables/$ARM/trials.tsv.gz ataru-0608/use_forget_D/$ARM/ \
    && git add ataru-0608/use_forget_D/$ARM && git commit -q -m "腕 D：$ARM の flag・sha256・試行ごとの表（走行の係）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
    && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 5; done ) >> "$LOG" 2>&1
}
run() {   # 名前 世界 種 足す旗…
  local ARM=$1 WD=$2 SEEDS=$3; shift 3
  say "腕 $ARM（世界 $WD、$*）"
  local C=$CS; [[ $ARM == calib_* ]] && C=$CS41
  nice -n 10 $PY tools/v3_run.py $C $OUT/$ARM $FL --seeds $SEEDS --shop-world $WD "$@" >> $OUT/$ARM.log 2>&1
  local rc=$? n; n=$(ls $OUT/$ARM/ledgers/cells/*/seed*.done 2>/dev/null | wc -l)
  local err; err=$(grep -c '"error"' $OUT/$ARM/manifest.jsonl 2>/dev/null)
  say "腕 $ARM 終わり rc=$rc 完走 $n 誤り ${err:-?}"
  echo "$rc $n ${err:-?}"
}

git fetch -q origin use-forget-2026-10-01 && git checkout -q --detach $CODE || { say "★ checkout に失敗"; exit 2; }
say "始める（コード $(git rev-parse --short HEAD)、未コミット $(git status --short -- tools abm | wc -l)）"
ctl "- $(date '+%H:%M') 追加の 12 腕を始めた（コード $(git rev-parse --short HEAD)、τ＝0.15・0.25・0.4・0.6・1.0・1.6、世界 2 → 1、種 1〜20、並列 14）。"
for WD in 2 1; do
  for TAU in 0.15 0.25 0.4 0.6 1.0 1.6; do
    ARM=uf_w${WD}_t$TAU
    diskok "腕 $ARM"
    read rc n err <<< "$(run $ARM $WD $S120 --use-forget $TAU)"
    post $ARM 1,2
    ctl "- $(date '+%H:%M') 腕 $ARM（τ＝$TAU）：完走 $n／20、誤り $err、rc=$rc。空き $(freegb) GB。"
  done
done
ctl "- $(date '+%H:%M') 追加の 12 腕が走り終わった。"
say "全部終わり"
