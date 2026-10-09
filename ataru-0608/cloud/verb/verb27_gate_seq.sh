#!/bin/bash
# 受け箱の指示 64 の 1：動詞の速い版の関門の組を、同じ機械で一本ずつ（off → 子 4）。この機械（c2d-standard-16）は物理 8 芯で cpu_budget 6 なので、off（2 枠）と子 4（6 枠）は同時に入らない。
# 各本は包みの受付 command（admission_command.draft.json の形）：jobs.py run --wait … -- python run_registered.py <case> --clearance <確認>。その後、包みの gate_compare.py で off と 4 を比べる。子 20 は保留（アストラの承認待ち）。
set -u
PY=/srv/verb/env/bin/python; P=/srv/verb/report-results/control/動詞_クラウドの包み_2026-10-09/instruction27; R=/srv/verb/production_instruction27; CL=/srv/verb/clearance27; CMP=/srv/verb/compare27
mkdir -p $CMP; log(){ echo "$(date -u +%FT%T) $*"; }
for L in gate100_birth0 gate100_birth4; do
  M=$(python3 -c "import json;print(json.load(open('$R/$L/spec.json'))['memory_reservation_gb'])")
  log "始める $L（予約 ${M}GB）"
  $PY ~/jobs/jobs.py run --wait --owner "動詞・指示28・$L" --mem $M --disk-path $R/$L/output -- $PY $P/run_registered.py $R/$L --clearance $CL/$L.json > $R/$L.jobs.log 2>&1; rc=$?
  log "$L rc=$rc"; [ $rc -eq 0 ] || { log "★ $L が 0 で終わらなかった。比べに進まない"; exit 3; }
done
$PY ~/jobs/jobs.py run --wait --owner 動詞28-off4 --mem 0.3 --disk-path $CMP -- $PY $P/gate_compare.py $R/gate100_birth0 $R/gate100_birth4 $CMP/gate_off_vs_4.json; rc=$?
log "比べ off と 4 rc=$rc"; log "ALLDONE"
