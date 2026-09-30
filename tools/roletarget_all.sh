#!/bin/bash
# 11 腕 × 種 1〜20 の対応先の計算し直し（tools/roletarget_recompute.py）。★ 記録を読むだけ
W=/Users/tatsu-admin/sfn/sfn-compression-abm-routing-urta
P=/Users/tatsu-admin/v310urtaprod
for a in lam000 L25 L50 L75 L90 lam015 lam020 lam030 lam050 lam020_Uabs lam030_Uabs; do
  echo "== $a $(date +%H:%M:%S)"
  python3.12 $W/tools/roletarget_recompute.py $P/v310BEurta_$a $P/roletarget/$a || echo "FAILED $a"
done
echo "== done $(date +%H:%M:%S)"
