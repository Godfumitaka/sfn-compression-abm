#!/bin/bash
# 集団化で届いた定義（2026-10-03）：A・C × 通信あり／なし × 集団の種 1〜20 の 80 集団。★ 記録を読むだけ。並列 2（集団ごとに 1 本）。
# 空きが 15 GB を切れば新しい集団を始めない。Codex の重い処理が 3 本以上なら colldefs_gate.sh が一時停止する。
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-spcana; cd $W
S="/Users/tatsu-admin/Documents/ChatGPT/New project/codex_collective20_2026-10-02"
M=$HOME/v33prod/results/mac/collective20_20261002
OUT=$HOME/v310cprod/集団化で届いた定義; mkdir -p $OUT/A $OUT/C $OUT/作業
export TMPDIR=$OUT/作業
jobs_list() {
  for g in $(seq -f %03g 1 20); do for m in recvA no_comm; do
    echo "A|$S/outputs/pilot_w2_${m}_g$g|$M/runs/pilot_w2_${m}_g$g/unselected.json"
    echo "C|$S/outputs_C/pilot_w2_${m}_g$g|$M/C/runs/pilot_w2_${m}_g$g/unselected.json"
  done; done
}
one() {
  IFS='|' read arm root u <<< "$1"
  free=$(df -g / | tail -1 | awk '{print $4}')
  if [ "$free" -lt 15 ]; then echo "STOP 空きが 15GB 未満 $root"; return; fi
  echo "== $(date +%T) $arm $(basename "$root") 空き ${free}GB $(sysctl -n vm.swapusage | awk '{print "swap", $6}')"
  python3.12 tools/colldefs.py $OUT/$arm "$root" "$u" || echo "FAILED $arm $root"
}
export -f one; export OUT
jobs_list | xargs -P 2 -I{} bash -c 'one "$@"' _ {}
echo "== CDDONE $(date +%T)"
