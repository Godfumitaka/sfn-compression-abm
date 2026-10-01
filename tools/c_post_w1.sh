#!/bin/bash
# 世界 1 の腕（A 5・C 4・F 2）の後の解析（2026-10-01 夕方の返事の 1）。並列 4（LLM の走行と並行のため）。★ 記録を読むだけ
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-spcana; cd $W
P=$HOME/v310cprod; OUT=$P/表_世界1; mkdir -p $OUT $P/roletarget
ARMS="cw1_A_lam000 cw1_A_lam0187 cw1_A_lam0990 cw1_A_lam020 cw1_A_lam030 cw1_C_lam0187 cw1_C_lam0990 cw1_C_lam020 cw1_C_lam030 cw1_F_lam0187 cw1_F_lam0990"
export RT_WORKERS=4 EP_WORKERS=4 DC_WORKERS=4
for d in $ARMS; do
  [ -f $P/roletarget/$d/checks.json ] && continue
  echo "== roletarget $d $(date +%T)"
  python3.12 tools/roletarget_recompute.py $P/$d $P/roletarget/$d || echo "FAILED $d"
done
mkdir -p $OUT/root; for d in $ARMS; do ln -sfn $P/$d $OUT/root/$d; done
echo "== 表 $(date +%T)"
python3.12 tools/spc_tables.py $OUT $OUT/root $HOME/v310gapprod $P/roletarget
echo "== 誤答の経路 $(date +%T)"
python3.12 tools/shop_errpath.py $OUT/誤答の経路.json $(for d in $ARMS; do echo $P/$d; done)
echo "== 定義の本数 $(date +%T)"
python3.12 tools/defcount.py $OUT/定義の本数.json $(for d in $ARMS; do echo $P/$d; done)
echo "== POSTDONE $(date +%T)"
