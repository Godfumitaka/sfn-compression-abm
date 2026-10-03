#!/bin/bash
# 2026-10-03 の委任書「分類の表の書き出しと、U の既定の答えを外す走行」の段 3（デスクトップ、走行の係）。偶然の決まりの台本の写し。
#  答え（2026-10-02 夜）：--e-price は全腕共通の L50 に固定、λ は --v39-price だけ。0.0187・0.099 は走らせない。新しい点は台帳を全部残す。C: の空きが 10GB を切りそうなら止める。
#  コード：strict-pc-2026-10-01 の今の先頭（88e0e38）。本番の作業場所 ~/sfn/sfn-compression-abm。
#  旗：マックのお店の世界の腕と同じ一式 ＋ --e-price L50。腕：A（λ＝L50・L90）、C（--cf-learn、λ＝L50・L90）× f＝0.5 → 1.0 → 0.25。種 1〜20、並列 14。
#  f の設定：0.5 は元の設定、0.25・1.0 は写しで axes.f だけ変えたもの（~/fgrid、リポジトリの外）。セルの名前も f に合わせる。
#  空きの決まり（この依頼から）：WSL の中の使用量（df -B1 /）が LIMIT を超えそうなら、又は C: の空きが 5GB を切りそうなら、新しい腕を始めずに止める。
#  台帳：毎腕のあと、全部の種の試行ごとの表と sha256 を作ってから、種 1・2 だけ残す。side（記録）は全部残す（大きな jsonl は gzip）。
set -u
W=$HOME/sfn/sfn-compression-abm; cd $W
OUT=$HOME/uabs; RES=$HOME/v33prod/results; LOG=$OUT/chain.log
CTRL="control/2026-10-03_U既定を外す_走行の係.md"
PY=/home/tatsu/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12
CODE=3380344
L50=0.01873710622997919; L90=0.09900039055209096
LIMIT=78231291392
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --dump-answers --dump-routing --answer-gap --strict-pc --cf-value --probe-world --e-price $L50 --select-log --workers 14 --no-compare --seeds $(seq -s, 1 20)"
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
used() { df -B1 / | awk 'NR==2 {print $3}'; }
cfree() { df -BG /mnt/c | awk 'NR==2 {gsub("G","",$4); print $4}'; }
ctl() {
  ( cd $RES && git pull -q --rebase origin results-2026-09-27
    echo "$1" >> "$CTRL"; git add "$CTRL" && git commit -q -m "control：U 既定を外す（走行の係）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
    && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 5; done ) >> "$LOG" 2>&1
}
diskok() {
  local u c; u=$(used); c=$(cfree)
  if (( u > LIMIT || c < 11 )); then say "★ 使用量 $u B・C: の空き ${c} GB、$1 の前で止める"; ctl "- $(date '+%H:%M') ★ WSL の中の使用量 $u B（上限 $LIMIT B）・C: の空き ${c} GB。$1 の前（腕の区切り）で止めた。"; exit 3; fi
}
post() {
  local ARM=$1
  $PY $HOME/ufprod/extract.py "$OUT/$ARM" "$OUT/tables/$ARM" $(seq -s, 1 20) >> "$LOG" 2>&1 || { say "★ 表の取り出しに失敗：$ARM（台帳は消さない）"; return 1; }
  find $OUT/$ARM/side -name "*.jsonl" -size +1M ! -name "*.shop.jsonl" -exec gzip -f {} \;
  ( cd $RES && git pull -q --rebase origin results-2026-09-27
    mkdir -p ataru-0608/uabs/$ARM && cp $OUT/$ARM/flag.json $OUT/tables/$ARM/sha256.jsonl $OUT/tables/$ARM/trials.tsv.gz ataru-0608/uabs/$ARM/ \
    && git add ataru-0608/uabs/$ARM && git commit -q -m "U 既定を外す：$ARM の flag・sha256・試行ごとの表（走行の係）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
    && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 5; done ) >> "$LOG" 2>&1
}
until grep -q "== DONE" $HOME/normal_sel.log 2>/dev/null; do sleep 60; done
git fetch -q origin n3-2026-10-02 && git checkout -q --detach $CODE || { say "★ checkout に失敗"; exit 2; }
say "始める（コード $(git rev-parse --short HEAD)、未コミット $(git status --short -- tools abm | wc -l)、上限 $LIMIT、使用量 $(used)、C: $(cfree) GB）"
ctl "- $(date '+%H:%M') 段 3 を始めた（コード $(git rev-parse --short HEAD)、並列 14、置き場所 ~/uabs、台帳は全部残す、tmux）。WSL の中の使用量 $(used) B、C: の空き $(cfree) GB。"
O=$HOME/uabs_sel; mkdir -p $O/作業
ARMS=("u_w1_A_L50|1|$L50|--v39-u abstain" "u_w1_C_L50|1|$L50|--v39-u abstain --cf-learn"
      "u_n3_w2_A_L50|2|$L50|--v39-u abstain --select-n3" "u_n3_w2_C_L50|2|$L50|--v39-u abstain --select-n3 --cf-learn"
      "u_n3_w1_A_L50|1|$L50|--v39-u abstain --select-n3" "u_n3_w1_C_L50|1|$L50|--v39-u abstain --select-n3 --cf-learn")
for LAM in 0.03 0.045 0.065 0.09900039055209096 0.15; do
  LN=$LAM; [[ $LAM == 0.0990* ]] && LN=0.099
  ARMS+=("u_w2_A_lam$LN|2|$LAM|--v39-u abstain" "u_w2_C_lam$LN|2|$LAM|--v39-u abstain --cf-learn")
done
for A in "${ARMS[@]}"; do
  IFS='|' read -r ARM WD LAM EX <<< "$A"
  [[ $ARM == u_w2_A_lam0.03 ]] && { touch $OUT/段3の1から3が終わった; ctl "- $(date '+%H:%M') 段 3 の 1・2 の 6 腕と分類が終わった（このあと 4 の 10 腕に進む）。"; }
  diskok "腕 $ARM"
  say "腕 $ARM（世界 $WD、λ＝$LAM $EX）使用量 $(used)"
  nice -n 10 $PY tools/v3_run.py config/sweep_shop_hide1_s1_2026-10-01.json $OUT/$ARM $FL --shop-world $WD --cells f0.5000_th2.1000_first_order --v39-price $LAM $EX >> $OUT/$ARM.log 2>&1
  rc=$?; n=$(ls $OUT/$ARM/ledgers/cells/*/seed*.done 2>/dev/null | wc -l); err=$(grep -c '"error"' $OUT/$ARM/manifest.jsonl 2>/dev/null)
  say "腕 $ARM 終わり rc=$rc 完走 $n 誤り ${err:-?}"
  post $ARM
  ctl "- $(date '+%H:%M') 腕 $ARM（世界 $WD、λ＝$LAM $EX）：完走 $n／20、誤り ${err:-?}、rc=$rc。WSL の中の使用量 $(used) B、C: の空き $(cfree) GB。"
  V=$HOME/uabs_view/$ARM; mkdir -p $V; ln -sfn $OUT/$ARM/ledgers $V/ledgers; cp $OUT/$ARM/flag.json $OUT/$ARM/manifest.jsonl $V/
  for c in $OUT/$ARM/side/*/; do cn=$(basename $c); mkdir -p $V/side/$cn; for f in $c/*; do b=$(basename $f); case $b in *.select.jsonl.gz) ;; *.gz) zcat $f > $V/side/$cn/${b%.gz};; *) ln -sfn $f $V/side/$cn/$b;; esac; done; done
  ( cd $HOME/sfn/audit/_dev/n3sel && export TMPDIR=$O/作業 SM_WORKERS=8 SC_WORKERS=8 \
    && nice -n 10 $PY tools/sealmem.py $O/sealmem $V \
    && SC_CUE=e nice -n 10 $PY tools/selcands.py $O/selcands $V $O/sealmem \
    && SC_CUE=n SC_ONLY_MISS=1 nice -n 10 $PY tools/selcands.py $O/selcands_n $V $O/sealmem ) >> $O/run.log 2>&1 && rm -rf $V || say "★ 分類に失敗：$ARM（読み取り用の写しは残す）"
  say "分類 $ARM 終わり"
done
ctl "- $(date '+%H:%M') 段 3 の 16 腕と分類が終わった。"
say "全部終わり"
