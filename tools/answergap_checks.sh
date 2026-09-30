#!/bin/bash
# --answer-gap の確かめの走行（委任書「欠けた位置にだけ答える」の 2）：旗なし λ＝0.3・L50 の種 1、旗あり λ＝0.3 の種 1。並列 3
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-answergap; cd $W
OUT=$HOME/v310gapcheck; mkdir -p $OUT
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --dump-answers --dump-routing --workers 1 --no-compare --seeds 1"
run() { caffeinate -i python3.12 tools/v3_run.py config/sweep_b2_hide_s1_2026-09-22.json $OUT/$1 $FL --v39-price $2 ${3:-} > $OUT/$1.log 2>&1; echo "$1 rc=$?"; }
run off_lam030 0.3 &
run off_L50 0.01873710622997919 &
run on_lam030 0.3 --answer-gap &
wait
