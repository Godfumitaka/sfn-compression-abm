#!/bin/bash
# README「同じ機械の100二本と比較」：二本を順に、受付表（/srv/jobs/jobs.py）を通して走らせ、比べる。各本の後に報告の表を作る。300 はここでは始めない。
VERB_PY=/srv/verb/env/bin/python; VERB_TOOLS=/srv/verb/source/tools/verb_measurement; VERB_OUTPUT_ROOT=/srv/verb/measurements_20261009
VERB_JOBS=/srv/jobs/jobs.py; VERB_CLEARANCE_ROOT=/srv/verb/resource_clearance
for L in on100_without_probe on100_with_probe; do
  echo "$(date '+%F %T') 始める $L"; "$VERB_PY" "$VERB_TOOLS/cloud_run.py" run "$VERB_OUTPUT_ROOT/$L" --jobs "$VERB_JOBS" --clearance "$VERB_CLEARANCE_ROOT/$L.json"; echo "$(date '+%F %T') $L rc=$?"
done
"$VERB_PY" "$VERB_JOBS" run --wait --mem .2 --disk-path "$VERB_OUTPUT_ROOT" -- "$VERB_PY" "$VERB_TOOLS/cloud_compare.py" "$VERB_OUTPUT_ROOT/on100_without_probe" "$VERB_OUTPUT_ROOT/on100_with_probe" "$VERB_OUTPUT_ROOT/on100_comparison.json"; echo "$(date '+%F %T') 比べ rc=$?"
for L in on100_without_probe on100_with_probe; do
  "$VERB_PY" "$VERB_JOBS" run --wait --mem .5 --disk-path "$VERB_OUTPUT_ROOT" -- "$VERB_PY" "$VERB_TOOLS/export_tables.py" "$VERB_OUTPUT_ROOT/$L" "$VERB_OUTPUT_ROOT/report_$L"; echo "$(date '+%F %T') 表 $L rc=$?"
done
echo "$(date '+%F %T') ALLDONE on100"
