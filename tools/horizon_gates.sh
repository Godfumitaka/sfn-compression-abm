#!/bin/bash
# 時間の幅の旗の関門 1・2（2026-10-03）。世界 2・A・λ＝0.0187（--v39-price・--e-price とも be_calib の L50）・種 1。旗一式は tools/mac_c_chain.sh と同じ。
# 三本：旗なし（T＝1,740）、--horizon 1740（T＝1,740）、--horizon 1740 で T＝3,480（--trial-count 3480）。並列 2 まで（重い処理の合計は 4 まで）。
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-horizon; cd $W
OUT=$HOME/horizon_gate; mkdir -p $OUT
L50=$(python3.12 -c "import json;print(repr(json.load(open('$HOME/v310prod/be_calib.json'))['λ']['50']))")
CS=config/sweep_shop_hide1_s1_2026-10-01.json
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --dump-answers --dump-routing --answer-gap --strict-pc --cf-value --probe-world --e-price $L50 --workers 1 --no-compare --seeds 1 --v39-price $L50 --shop-world 2"
echo "== $(date +%T) コード $(git rev-parse --short HEAD) 未コミット $(git status --short -- tools abm | wc -l | tr -d ' ') λ $L50"
caffeinate -i python3.12 tools/v3_run.py $CS $OUT/off $FL > $OUT/off.log 2>&1 &
caffeinate -i python3.12 tools/v3_run.py $CS $OUT/h1740 $FL --horizon 1740 > $OUT/h1740.log 2>&1 &
wait
echo "== $(date +%T) 関門 1 の二本が終わった"
python3.12 tools/horizon_compare.py gate1 $OUT/off $OUT/h1740 > $OUT/gate1.json
caffeinate -i python3.12 tools/v3_run.py $CS $OUT/h1740_T3480 $FL --horizon 1740 --trial-count 3480 > $OUT/h1740_T3480.log 2>&1
echo "== $(date +%T) T＝3,480 が終わった"
python3.12 tools/horizon_compare.py gate2 $OUT/h1740 $OUT/h1740_T3480 1740 > $OUT/gate2.json
echo "== HGDONE $(date +%T)"
