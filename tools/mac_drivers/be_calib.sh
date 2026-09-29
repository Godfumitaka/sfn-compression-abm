#!/bin/bash
# B＋E の較正（委任書 2・仕様 9 節）：s41（種 41〜60）、λ＝0、20 本、最頻のセル。各試行の変換の前に列挙した正の V を
# side/<セル>/seedNNN.v39cands.f64 に書き出す（--v39-dump-cands。--v310-be では「変換の前」）。出力 ~/v310prod/v310BE_cal。
set -u
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-v310mac; cd $W
O=$HOME/v310prod/v310BE_cal; mkdir -p $HOME/v310prod
echo "$(date '+%F %T') 較正を始める コード $(git rev-parse --short HEAD) 未コミット $(git status --short | wc -l | tr -d ' ')" >> $HOME/v310prod/be_calib.log
caffeinate -dimsu python3.12 tools/v3_run.py config/sweep_b2_hide_s41_2026-09-27.json $O \
  --nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history \
  --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence \
  --v39 --v39-decay actr --v39-budget inf --v39-price 0 --v310-be --v39-dump-cands \
  --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --workers 6 --no-compare >> $HOME/v310prod/be_calib.log 2>&1
echo "$(date '+%F %T') BECALIBDONE rc=$?" >> $HOME/v310prod/be_calib.log
