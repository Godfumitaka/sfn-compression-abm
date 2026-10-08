#!/bin/bash
# 組の二本が終わった後の比べと表（README の命令に、Ubuntu 版の受付表 jobs.py が要る --owner を足しただけ）。
# 前の verb_pair.sh は --owner が無くて jobs.py が引数の誤りで止まり、さらに rc の書き方の誤り（$(date) が $? を上書き）で rc=0 と書いていた。
# 引数：on100 又は speed200
set -u
VERB_PY=/srv/verb/env/bin/python; VERB_JOBS=/srv/jobs/jobs.py
if [ "$1" == on100 ]; then T=/srv/verb/source/tools/verb_measurement; R=/srv/verb/measurements_20261009; A=on100_without_probe; B=on100_with_probe
else T=/srv/verb/speed_source/tools/verb_measurement; R=/srv/verb/speed200_20261009; A=speed200_off; B=speed200_on; fi
until [ -f "$R/$A/result.json" ] && [ -f "$R/$B/result.json" ]; do sleep 30; done
if [ "$1" == on100 ]; then
  "$VERB_PY" "$VERB_JOBS" run --wait --owner "動詞・指示9・on100_comparison" --mem .2 --disk-path "$R" -- "$VERB_PY" "$T/cloud_compare.py" "$R/$A" "$R/$B" "$R/on100_comparison.json"; rc=$?; echo "$(date '+%F %T') 比べ rc=$rc"
else echo "$(date '+%F %T') speed200 の比べは、動詞の係が直した比較器（README に sha256）が来てから行う"; fi
for L in $A $B; do
  "$VERB_PY" "$VERB_JOBS" run --wait --owner "動詞・指示9・report_$L" --mem .5 --disk-path "$R" -- "$VERB_PY" "$T/export_tables.py" "$R/$L" "$R/report_$L"; rc=$?; echo "$(date '+%F %T') 表 $L rc=$rc"
done
echo "$(date '+%F %T') ALLDONE after $1"
