#!/bin/bash
# 受け箱の指示 32 の 1：組の二本目を、一本目の終わりを待たずに、同じ機械で今すぐ始める。二本とも終わったら（result.json）、比べと表へ進む。
# 引数：on100 又は speed200。一本目は前の順番の台本で始まっていて、その台本の bash だけを止めた（一本目の走行は続いている）。
set -u
VERB_PY=/srv/verb/env/bin/python; VERB_JOBS=/srv/jobs/jobs.py; C=/srv/verb/resource_clearance
if [ "$1" == on100 ]; then
  T=/srv/verb/source/tools/verb_measurement; R=/srv/verb/measurements_20261009; A=on100_without_probe; B=on100_with_probe
else
  T=/srv/verb/speed_source/tools/verb_measurement; R=/srv/verb/speed200_20261009; A=speed200_off; B=speed200_on
fi
echo "$(date '+%F %T') 始める $B（$A は走っている）"
"$VERB_PY" "$T/cloud_run.py" run "$R/$B" --jobs "$VERB_JOBS" --clearance "$C/$B.json"; echo "$(date '+%F %T') $B rc=$?"
until [ -f "$R/$A/result.json" ]; do sleep 30; done; echo "$(date '+%F %T') $A の result.json ができた"
if [ "$1" == on100 ]; then
  "$VERB_PY" "$VERB_JOBS" run --wait --mem .2 --disk-path "$R" -- "$VERB_PY" "$T/cloud_compare.py" "$R/$A" "$R/$B" "$R/on100_comparison.json"; echo "$(date '+%F %T') 比べ rc=$?"
else
  echo "speed200 の比べは、動詞の係が直した比較器（README に sha256）が来てから行う"
fi
for L in $A $B; do
  "$VERB_PY" "$VERB_JOBS" run --wait --mem .5 --disk-path "$R" -- "$VERB_PY" "$T/export_tables.py" "$R/$L" "$R/report_$L"; echo "$(date '+%F %T') 表 $L rc=$?"
done
echo "$(date '+%F %T') ALLDONE $1"
