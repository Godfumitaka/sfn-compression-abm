#!/bin/bash
# 世界 v4（--world-cue）の走らせて確かめるもの（委任書 2）。使い方：bash tools/worldcue_checks/acc_runs.sh <出力の根> <v3.10be-main を取り出した作業場所>
set -u
D=$1; BASEWT=$2
PY=${PY:-$(~/.local/bin/uv python find 3.12.13)}
C=config/sweep_b2_hide_s1_2026-09-22.json
L50=0.01873710622997919
BE="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --no-compare --seeds 1 --workers 1"
rm -rf $D; mkdir -p $D
( $PY tools/v3_run.py $C $D/off_dev $BE --v39-price $L50 > $D/off_dev.log 2>&1 ) &
( cd $BASEWT && $PY tools/v3_run.py $C $D/off_base $BE --v39-price $L50 > $D/off_base.log 2>&1 ) &
( $PY tools/v3_run.py $C $D/cue_L50 $BE --v39-price $L50 --world-cue > $D/cue_L50.log 2>&1 ) &
( $PY tools/v3_run.py $C $D/cue_L0 $BE --v39-price 0 --world-cue > $D/cue_L0.log 2>&1 ) &
( T02_OUT=$D/t02.json $PY tools/v38_checks/t02.py $C $D/t02run $BE --v39-price 0 --world-cue > $D/t02.log 2>&1 ) &
wait
body() { zcat "$1" | tail -n +2 | sha256sum | cut -c1-16; }
L=ledgers/cells/f0.5000_th2.1000_vt0.3842_first_order
echo "旗を切ったとき（主・seed001・λ＝L50・1,740 試行）：v3.10be-main $(body $D/off_base/$L/seed001.jsonl.gz)  この版 $(body $D/off_dev/$L/seed001.jsonl.gz)"
echo "T02（開示の無い試行で伏せ辺だけを差し替えても学習が同じ。--world-cue・λ＝0）：$(cat $D/t02.json 2>/dev/null)"
for x in cue_L0 cue_L50; do $PY - $D/$x <<'P'
import gzip, json, sys, collections
root = sys.argv[1]
rec = [json.loads(l) for l in open(root + "/manifest.jsonl")][-1]
be = rec.get("v310be") or {}; wc = rec.get("worldcue") or {}
C = collections.Counter()
with gzip.open(root + "/ledgers/cells/f0.5000_th2.1000_vt0.3842_first_order/seed001.jsonl.gz", "rt") as f:
    next(f)
    for l in f:
        r = json.loads(l)
        C["行"] += 1
        C["world_cue あり"] += r.get("world_cue") in ("upright", "lateral")
        C["held_out_switch あり"] += r.get("held_out_switch") is not None
print(root.split("/")[-1], "失敗", rec.get("error"), "ΔC の食い違い", be.get("dC_mismatch"), "世界", wc, "台帳", dict(C))
P
done
