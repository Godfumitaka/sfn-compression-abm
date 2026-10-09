#!/bin/bash
# 指示 58：集団化の関門を、Google Cloud の関門だけの機械で、前の関門 → 一体 ON（4 本と比べ 2 つ）まで通しで走らせる。走行中は SSH で入らない。
# 進みは coll_status.sh（bash と curl だけ、python を使わない）が 5 分ごとに gs://sfn-gate-status-577b8173/status.txt に上げる。
bash ~/cloud/coll/coll_phase1_gcp.sh > ~/coll_phase1_gcp.log 2>&1; echo "phase1 rc=$?" >> ~/coll_chain.log
grep -q "ALLDONE phase1" ~/coll_phase1_gcp.log && { bash ~/cloud/coll/coll_phase2_gcp.sh > ~/coll_phase2_gcp.log 2>&1; echo "phase2 rc=$?" >> ~/coll_chain.log; }
echo "chain 終わり $(date -u +%FT%T)" >> ~/coll_chain.log
