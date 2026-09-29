#!/bin/bash
# B＋E（--v310-be）の走行を使う検査。主・seed001・最頻・1,740 試行。出力は本体のリポジトリの analysis_v310_2026-09-29/check_be/。
# 1 旗を切った版（--v39-price 0・均等）が、v3.10-main（cd8dc52）の同じ走行（check_mac/price0）と一字一句同じ（仕様 ⑫ の基準版の再現）。
# 2 λ＝0 の 1,740 試行で、新しい定義が実際に選ばれるか（誕生の数と走行末の定義の数）。
# 3 v3.8 の T02（本人が知りえない情報で学ばない）を、--v310-be（λ＝0）を付けて通す。
set -u
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-v310mac; cd $W
O=/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_v310_2026-09-29/check_be; mkdir -p $O
P0=/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_v310_2026-09-29/check_mac/price0
BASE="config/sweep_b2_hide_s1_2026-09-22.json"
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --seeds 1 --cells f0.5000_th2.1000_first_order --workers 1"
python3.12 tools/v3_run.py $BASE $O/off $FL --v39-price 0 --compare-to $P0/ledgers > $O/off.log 2>&1 &
python3.12 tools/v3_run.py $BASE $O/L0_1740 $FL --v39-decay actr --v39-price 0 --v310-be --no-compare > $O/L0_1740.log 2>&1 &
T02_OUT=$O/t02_be.json PYTHONPATH=$W/tools/v38_checks python3.12 tools/v38_checks/t02.py $BASE $O/t02_be $FL --v39-decay actr --v39-price 0 --v310-be --no-compare > $O/t02_be.log 2>&1 &
wait
echo BECHECKSDONE
