#!/bin/bash
# 既定の答えとの食い違い（2026-10-03）：世界 1・2 の A・C（λ＝0.0187・0.099）、種 1〜20。★ 記録を読むだけ。並列 UD_WORKERS＝2。
# 重い処理の合計が 4 を超える間は tools/udefault_gate.sh が一時停止する。空きが 15 GB を切れば次の腕を始めない。
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-spcana; cd $W
P=$HOME/v310cprod; OUT=$P/既定の答えとの食い違い; mkdir -p $OUT/作業
export UD_WORKERS=2 TMPDIR=$OUT/作業
for d in cw2_A_lam0187 cw2_C_lam0187 cw2_A_lam0990 cw2_C_lam0990 cw1_A_lam0187 cw1_C_lam0187 cw1_A_lam0990 cw1_C_lam0990; do
  free=$(df -g / | tail -1 | awk '{print $4}')
  echo "== $d $(date +%T) 空き ${free}GB $(uptime | sed 's/.*load/load/') $(sysctl -n vm.swapusage | awk '{print "swap", $6}')"
  if [ "$free" -lt 15 ]; then echo "STOP 空きが 15GB 未満"; break; fi
  python3.12 tools/udefault.py $OUT $P/$d || echo "FAILED $d"
done
echo "== UDDONE $(date +%T)"
