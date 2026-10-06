#!/bin/bash
# 点検 4：マックの段 4 と同じ命令・同じ環境（PYTHONHASHSEED=0、LC_CTYPE・LC_ALL・LANG を外す。stage4_full/checks/run.py と同じ）
cd $HOME/sfn/audit/_read/sme
PY=/home/tatsu/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12
L50=0.01873710622997919
BASE="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --dump-answers --dump-routing --answer-gap --strict-pc"
env -u LC_CTYPE -u LC_ALL -u LANG PYTHONHASHSEED=0 /usr/bin/time -v nice -n 10 $PY tools/v3_run.py config/sweep_shop_hide1_s1_2026-10-01.json $HOME/sme_audit/check4_sme $BASE --e-price $L50 --v39-price $L50 --shop-world 2 --workers 1 --seeds 1 --trial-count 1740 --no-compare --horizon 1740 --score-arg-order --sme2017 --shop-scatter > $HOME/sme_audit/check4.log 2>&1
echo "== check4 終わり $(date +%T)" >> $HOME/sme_audit/check4.log
