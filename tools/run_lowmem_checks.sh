#!/bin/zsh
# メモリを減らす書き直し（--lowmem）の一致の確かめ。1 本ずつ（時間と最大メモリを測るため）。
# ★ 引き金：v3 の主の一本（analysis_v3_2026-09-25/v3main_one）の .done ができていること。
# ★ 一本でも一致しなければ、その場で止める（以後を走らせない）。
cd /Users/tatsu-admin/sfn/sfn-compression-abm
D=analysis_v3_2026-09-25/lowmem_checks; mkdir -p $D; L=$D/checks.log
while [[ ! -e analysis_v3_2026-09-25/v3main_one/ledgers/cells/f0.5000_th2.1000_vt0.3842_first_order/seed001.done ]]; do sleep 30; done
echo "$(date '+%F %T') 開始" >> $L
run(){ # $1=名前 $2=config $3..=追加の引数
  local n=$1 c=$2; shift 2
  python3.12 tools/v3_run.py $c $D/$n --lowmem --workers 1 --seeds 1 "$@" >> $L 2>&1
  local rc=$?
  echo "$(date '+%F %T') $n rc=$rc" >> $L
  if [[ $rc != 0 ]]; then echo "★★ $n が rc=$rc（不一致またはエラー）。止める" >> $L; exit $rc; fi
}
for c in f0.5000_th2.1000_first_order f0.5000_th2.1000_first_order_fill-sample f0.5000_th2.3000_first_order f0.5000_th2.3000_first_order_fill-sample; do
  run hide_$c config/sweep_b2_hide_s1_2026-09-22.json --cells $c
done
run f00_th21 config/sweep_b2_f00_s1_2026-09-22.json --cells f0.0000_th2.1000_first_order
run f10_th21 config/sweep_b2_f10_s1_2026-09-22.json --cells f1.0000_th2.1000_first_order
run v3combo config/sweep_b2_hide_s1_2026-09-22.json --cells f0.5000_th2.1000_first_order --nohash --vt 0.3842 --greedy --compare-to analysis_v3_2026-09-25/v3main_one/ledgers
echo "$(date '+%F %T') ALLDONE" >> $L
