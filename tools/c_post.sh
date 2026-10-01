#!/bin/bash
# 段 6（お店の世界 26 腕）の走り終わったあとの集計：対応先の計算し直し → 表 → 誤答の経路。★ 記録を読むだけ
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-spcana; cd $W
P=$HOME/v310cprod; OUT=$P/表; mkdir -p $OUT $P/roletarget
for d in $(ls -d $P/cw*/ | xargs -n1 basename); do
  echo "== roletarget $d $(date +%T)"
  python3.12 tools/roletarget_recompute.py $P/$d $P/roletarget/$d || echo "FAILED $d"
done
echo "== 表 $(date +%T)"
python3.12 tools/spc_tables.py $OUT $P $HOME/v310gapprod $P/roletarget
echo "== 誤答の経路 $(date +%T)"
python3.12 tools/shop_errpath.py $OUT/誤答の経路.json $(ls -d $P/cw*/ | sed 's#/$##')
echo "== POSTDONE $(date +%T)"
