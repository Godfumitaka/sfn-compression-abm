#!/bin/bash
# シールを戻す確かめ（2026-10-02 昼の 1）。世界 2 の A・C（λ＝0.0187・0.099）の 4 腕、種 1〜20。★ 記録を読むだけ。並列 SR_WORKERS（既定 2。2026-10-02 昼に熱で止まったあと 4 から下げた）。全試行の確かめは種 1〜5（SR_FULL）
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-spcana; cd $W
P=$HOME/v310cprod; OUT=$P/シールを戻す確かめ; mkdir -p $OUT/作業
export SR_WORKERS=${SR_WORKERS:-2} SR_FULL=${SR_FULL:-1,2,3,4,5} TMPDIR=$OUT/作業
for d in cw2_A_lam0187 cw2_C_lam0187 cw2_A_lam0990 cw2_C_lam0990; do
  echo "== $d $(date +%T)"
  python3.12 tools/sealrestore.py $OUT $P/$d $P/誤りの印と記憶の量3 || echo "FAILED $d"
done
echo "== SRDONE $(date +%T)"
