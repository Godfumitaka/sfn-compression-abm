#!/bin/bash
# v3.11c の受入検査のうち走らせて確かめるもの（仕様 8 節 ①・②・⑩・⑪ と ⑨ の数え）。300 試行・種 1 と 1001。
# 使い方（v3.11c の作業場所の根で）：bash tools/v311c_checks/acc_runs.sh <出力の根> <v3.10be-main を取り出した作業場所>
set -u
D=$1; BASEWT=$2
PY=${PY:-$(~/.local/bin/uv python find 3.12.13)}
C=config/sweep_b2_hide_s1_2026-09-22.json
BE="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v39-price 0.01873710622997919 --v310-be --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --no-compare --trial-count 300"
rm -rf $D; mkdir -p $D
HERE=$(pwd)
( $PY tools/v3_run.py $C $D/ind_dev $BE --seeds 1 --workers 1 > $D/ind_dev.log 2>&1 ) &
( cd $BASEWT && $PY tools/v3_run.py $C $D/ind_base $BE --seeds 1 --workers 1 > $D/ind_base.log 2>&1 ) &
( $PY tools/v3_run.py $C $D/c_notags $BE --workers 1 --v311c --v311c-f 0.5,0.5 --v311c-no-tags --v311c-runs 1 > $D/c_notags.log 2>&1 ) &
( $PY tools/v3_run.py $C $D/solo_notags $BE --workers 1 --v311c --v311c-f 0.5 --v311c-no-tags --v311c-runs 1001 > $D/solo_notags.log 2>&1 ) &
( $PY tools/v3_run.py $C $D/c_q0 $BE --workers 1 --v311c --v311c-f 0.5,0.5 --v311c-q 0 --v311c-runs 1 > $D/c_q0.log 2>&1 ) &
( $PY tools/v3_run.py $C $D/solo $BE --workers 2 --v311c --v311c-f 0.5 --v311c-q 0 --v311c-b-n 2 --v311c-runs 1,1001 > $D/solo.log 2>&1 ) &
( $PY tools/v3_run.py $C $D/c_rep1 $BE --workers 1 --v311c --v311c-f 0.5,0.5 --v311c-q 0.5 --v311c-recv B --v311c-runs 1 --v311c-probe-every 10 > $D/c_rep1.log 2>&1 ) &
( $PY tools/v3_run.py $C $D/c_rep2 $BE --workers 1 --v311c --v311c-f 0.5,0.5 --v311c-q 0.5 --v311c-recv B --v311c-runs 1 --v311c-probe-every 10 > $D/c_rep2.log 2>&1 ) &
( $PY tools/v3_run.py $C $D/c_noprobe $BE --workers 1 --v311c --v311c-f 0.5,0.5 --v311c-q 0.5 --v311c-recv B --v311c-runs 1 --v311c-probe-every 0 > $D/c_noprobe.log 2>&1 ) &
( $PY tools/v3_run.py $C $D/c_recvA $BE --workers 1 --v311c --v311c-f 0.5,0.5 --v311c-q 0.5 --v311c-recv A --v311c-runs 1 --v311c-probe-every 10 > $D/c_recvA.log 2>&1 ) &
wait
body() { zcat "$1" | tail -n +2 | sha256sum | cut -c1-16; }
L=ledgers/cells/f0.5000_th2.1000_vt0.3842_first_order
echo "① 個体版（v3.10be-main）と、この版の旗なし"
echo "  seed001  base $(body $D/ind_base/$L/seed001.jsonl.gz)  dev $(body $D/ind_dev/$L/seed001.jsonl.gz)"
echo "① 集団化の機能を全部切った二体（名札・通信なし）と、個体版"
echo "  seed001  個体 $(body $D/ind_dev/$L/seed001.jsonl.gz)  集団（切） $(body $D/c_notags/$L/seed001.jsonl.gz)"
echo "  seed1001（設定の種の範囲の外なので、集団化を切った単独と比べる）  単独（切） $(body $D/solo_notags/$L/seed1001.jsonl.gz)  集団（切） $(body $D/c_notags/$L/seed1001.jsonl.gz)"
echo "② 通信なしの二体（名札あり）と、同じ設定の単独（b は二体と同じ）"
for s in 001 1001; do echo "  seed$s  二体 $(body $D/c_q0/$L/seed$s.jsonl.gz)  単独 $(body $D/solo/$L/seed$s.jsonl.gz)"; done
echo "⑩ 同じ設定の二回（処理の順と乱数から再現できるか）：通信の記録と台帳"
echo "  comm（最後の要約の行＝走行時間などを除く）  $(grep -v '"kind": "summary"' $D/c_rep1/comm/run001.jsonl | sha256sum | cut -c1-16)  $(grep -v '"kind": "summary"' $D/c_rep2/comm/run001.jsonl | sha256sum | cut -c1-16)"
for s in 001 1001; do echo "  seed$s  $(body $D/c_rep1/$L/seed$s.jsonl.gz)  $(body $D/c_rep2/$L/seed$s.jsonl.gz)"; done
echo "⑪ 試験あり（10 試行ごと）と試験なしで、台帳（学習の状態）が同じか"
for s in 001 1001; do echo "  seed$s  試験あり $(body $D/c_rep1/$L/seed$s.jsonl.gz)  試験なし $(body $D/c_noprobe/$L/seed$s.jsonl.gz)"; done
echo "要約"
for x in c_rep1 c_recvA c_q0 c_notags; do $PY -c "
import json,sys; s=json.load(open('$D/$x/comm/run001.summary.json'))
a=[(g or {}).get('v311c') or {} for g in s.get('agents') or []]
print('  $x', {k:s.get(k) for k in ('trials','bundles','sent','delivered','recv','tag_lost')}, '失敗', len(s.get('errors') or []),
      '受け取りで成績が変わった', sum(x.get('recv_score_changed',0) for x in a), '功績が変わった', sum(x.get('recv_merit_changed',0) for x in a),
      '覚え直し', sum(x.get('recv_relearn',0) for x in a), '置き直しを戻した', sum(x.get('recv_reinit_restored',0) for x in a),
      'ΔC の食い違い', sum(x.get('dC_mismatch',0) for x in a))"; done
