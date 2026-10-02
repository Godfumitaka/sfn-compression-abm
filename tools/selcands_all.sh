#!/bin/bash
# 選び間違いの数え上げ（2026-10-02 夕方）。世界 2 の A・C（λ＝0.0187・0.099）、種 1〜20。★ 記録を読むだけ。並列 SC_WORKERS（既定 2）
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-spcana; cd $W
P=$HOME/v310cprod; OUT=$P/選び間違い; mkdir -p $OUT/作業
export SC_WORKERS=${SC_WORKERS:-2} TMPDIR=$OUT/作業
for d in cw2_A_lam0187 cw2_C_lam0187 cw2_A_lam0990 cw2_C_lam0990; do
  echo "== $d $(date +%T)"
  python3.12 tools/selcands.py $OUT $P/$d $P/誤りの印と記憶の量3 || echo "FAILED $d"
done
echo "== SCDONE $(date +%T)"
