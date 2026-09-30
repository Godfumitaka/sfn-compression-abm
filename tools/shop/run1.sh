#!/bin/bash
# お店の世界の確かめの走行を一本：run1.sh <出力の根> <config> <λ> <種> [足す旗 …]（並列 1）
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-shop; cd $W
OUT=$1; CFG=$2; LAM=$3; SEED=$4; shift 4
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --dump-answers --dump-routing --workers 1 --no-compare --seeds $SEED"
python3.12 tools/v3_run.py $CFG $OUT $FL --v39-price $LAM "$@" > $OUT.log 2>&1
echo "$(basename $OUT) rc=$?"
