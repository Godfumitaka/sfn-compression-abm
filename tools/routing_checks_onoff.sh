#!/bin/bash
# --dump-routing の有無で、台帳・side・答えの記録が同じか（v3.10urta-main ＋ 四つの直しの旗、λ＝0.3、seed001）
set -u
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-routing-urta; cd $W
O=$HOME/routingcheck_urta; mkdir -p $O
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --dump-answers --seeds 1 --workers 1 --no-compare --v39-price 0.3"
python3.12 tools/v3_run.py config/sweep_b2_hide_s1_2026-09-22.json $O/off $FL > $O/off.log 2>&1 &
python3.12 tools/v3_run.py config/sweep_b2_hide_s1_2026-09-22.json $O/on $FL --dump-routing > $O/on.log 2>&1 &
wait
