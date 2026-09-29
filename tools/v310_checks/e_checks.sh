#!/bin/bash
# E（--v310-merge）の走行を使う検査（委任書「D と E」第 2 部の 3）。主・予算無限・seed001・最頻。出力は本体のリポジトリの analysis_v310_2026-09-29/check_mac/。
# 1 旗を切った版（--v39-price 0・均等）が、v3.10-main（cd8dc52）の同じ走行（price0）と一字一句同じ。
# 2（--v310-merge-price の検査は、B＋E を外したので無い）
# 3 v3.8 の T02（本人が知りえない情報で学ばない）を、E を付けて通す。
# ★ q1〜q6 は検査のために全部 a で走らせる（本番の値ではない。control/2026-09-29_E_仕様の問い_マック.md の返事を待つ）。
set -u
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-v310mac; cd $W
O=/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_v310_2026-09-29/check_mac
BASE="config/sweep_b2_hide_s1_2026-09-22.json"
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --seeds 1 --cells f0.5000_th2.1000_first_order --workers 1"
EO="--v310-opts q1=a,q2=a,q3=a,q4=a,q5=a,q6=a"
python3.12 tools/v3_run.py $BASE $O/off $FL --v39-price 0 --compare-to $O/price0/ledgers > $O/off.log 2>&1 &
( python3.12 tools/v3_run.py $BASE $O/E_a1 $FL --v39-decay actr --v310-merge --v310-alpha 1 $EO --no-compare > $O/E_a1.log 2>&1
 ) &
T02_OUT=$O/t02_E.json PYTHONPATH=$W/tools/v38_checks python3.12 tools/v38_checks/t02.py $BASE $O/t02_E $FL --v39-decay actr --v310-merge --v310-alpha 1 $EO --no-compare > $O/t02_E.log 2>&1 &
wait
echo ECHECKSDONE
