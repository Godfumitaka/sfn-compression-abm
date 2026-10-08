#!/bin/bash
# README「二の次：速度off/on200の包み」：二本を順に、受付表を通して走らせる。比べは、動詞の係が直した比較器（README に sha256 が書かれる）が来てから行う（受け箱の指示 31 の 1）。
VERB_PY=/srv/verb/env/bin/python; VERB_SPEED_TOOLS=/srv/verb/speed_source/tools/verb_measurement; VERB_SPEED_ROOT=/srv/verb/speed200_20261009
VERB_JOBS=/srv/jobs/jobs.py; VERB_CLEARANCE_ROOT=/srv/verb/resource_clearance
for L in speed200_off speed200_on; do
  echo "$(date '+%F %T') 始める $L"; "$VERB_PY" "$VERB_SPEED_TOOLS/cloud_run.py" run "$VERB_SPEED_ROOT/$L" --jobs "$VERB_JOBS" --clearance "$VERB_CLEARANCE_ROOT/$L.json"; echo "$(date '+%F %T') $L rc=$?"
done
echo "$(date '+%F %T') ALLDONE speed200（比べは直した比較器を待つ）"
