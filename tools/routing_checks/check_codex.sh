#!/bin/bash
# --dump-routing の確かめ：Codex の 5 腕（v310BEhsc_*、版 d2106e8）の種 1〜2 を、同じ旗 ＋ --dump-routing で ~/routingcheck/<腕> に走らせ、
# 台帳の本体の sha256 を Codex の sha256.jsonl（結果のブランチ mac/<腕>/sha256.jsonl）と比べる。Codex の作業場所には書かない。
set -u
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-routing; cd $W
O=$HOME/routingcheck; mkdir -p $O
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --dump-answers --dump-routing --seeds 1,2 --workers 2 --no-compare"
for A in "v310BEhsc_L90:0.09900039055209096" "v310BEhsc_lam015:0.15" "v310BEhsc_lam020:0.2" "v310BEhsc_lam030:0.3" "v310BEhsc_lam050:0.5"; do
  ARM=${A%%:*}; LAM=${A#*:}
  python3.12 tools/v3_run.py config/sweep_b2_hide_s1_2026-09-22.json $O/$ARM $FL --v39-price $LAM > $O/$ARM.log 2>&1 &
done
wait
echo CHECKDONE
