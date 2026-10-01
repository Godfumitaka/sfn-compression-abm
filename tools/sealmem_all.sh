#!/bin/bash
# 誤りの印と記憶の量（2026-10-02 朝）。★ 記録を読むだけ。世界 1・2 の A・C（λ＝0.0187・0.099・0.2）と F（λ＝0.0187）。
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-spcana; cd $W
P=$HOME/v310cprod; OUT=$P/誤りの印と記憶の量3; mkdir -p $OUT
export SM_WORKERS=${SM_WORKERS:-4}
for w in 2 1; do
  for a in A_lam0187 A_lam0990 A_lam020 C_lam0187 C_lam0990 C_lam020 F_lam0187; do
    d=cw${w}_$a
    echo "== $d $(date +%T)"
    python3.12 tools/sealmem.py $OUT $P/$d --rt $P/roletarget/$d || echo "FAILED $d"
  done
done
echo "== SMDONE $(date +%T)"
