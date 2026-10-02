#!/bin/bash
# 手がかりを知っていた場合の上限（2026-10-02 夜）：通常の日にドアが問われた試行の候補の書き出し。世界 2 の A・C（λ＝0.0187・0.099）、種 1〜20。
# ★ 記録を読むだけ。並列 1（Codex と同じ機械）。腕ごとに機械の状態を記録し、空きが 15 GB を切れば止まる。
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-spcana; cd $W
P=$HOME/v310cprod; OUT=$P/選び間違い3_通常の日; mkdir -p $OUT/作業
export SC_CUE=n SC_WORKERS=1 TMPDIR=$OUT/作業
for d in cw2_A_lam0187 cw2_C_lam0187 cw2_A_lam0990 cw2_C_lam0990; do
  free=$(df -g / | tail -1 | awk '{print $4}')
  echo "== $d $(date +%T) 空き ${free}GB $(uptime | sed 's/.*load/load/') $(sysctl -n vm.swapusage | awk '{print "swap", $6}')"
  if [ "$free" -lt 15 ]; then echo "STOP 空きが 15GB 未満"; break; fi
  python3.12 tools/selcands.py $OUT $P/$d $P/誤りの印と記憶の量3 || echo "FAILED $d"
done
echo "== SCDONE $(date +%T)"
