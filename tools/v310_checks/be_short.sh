#!/bin/bash
# B＋E の短い走行（委任書 1 の追加の検査）：seed001・最頻・300 試行、λ＝0 と λ＝1。引数：出力の根 [試行数＝300] [λ の並び＝"0 1"]
set -u
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-v310mac; cd $W
O=$1; N=${2:-300}; LAMS=${3:-"0 1"}; mkdir -p $O
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-decay actr --v39-budget inf --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --seeds 1 --cells f0.5000_th2.1000_first_order --workers 1 --no-compare --v310-be"
TC=""; [[ "$N" != "1740" ]] && TC="--trial-count $N"
for l in $LAMS; do
  python3.12 tools/v3_run.py config/sweep_b2_hide_s1_2026-09-22.json $O/L${l}_$N $FL $TC --v39-price $l > $O/L${l}_$N.log 2>&1 &
done
wait
