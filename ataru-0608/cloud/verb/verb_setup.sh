#!/bin/bash
# 動詞の包み（control/動詞_クラウドの包み_2026-10-09/README.md）の準備を、クラウドの機械の上で README の手順どおりに行う（受け箱の指示 29・30・31）。
# 違い：GitHub の鍵を機械に置かないため、土台 e9ed84a は README の git clone の代わりに、機械の上の既存の写し（デスクトップから束で送った）から clone する。
#       bundle の sha256・verify・fetch・checkout・HEAD と tree の確かめは README のとおり。どれかが違えば止まる（set -e と test）。
set -euo pipefail
export PATH=$HOME/.local/bin:$PATH
sudo mkdir -p /srv/verb /srv/jobs && sudo chown ubuntu:ubuntu /srv/verb /srv/jobs
VERB_PACKAGE=/srv/verb/report-results/control/動詞_クラウドの包み_2026-10-09
VERB_SOURCE=/srv/verb/source; VERB_OUTPUT_ROOT=/srv/verb/measurements_20261009
VERB_SPEED_SOURCE=/srv/verb/speed_source; VERB_SPEED_ROOT=/srv/verb/speed200_20261009
cp ~/cloud/verb/jobs.py ~/cloud/verb/verb_clearance.py /srv/jobs/
for x in "$VERB_SOURCE cloud codex/verb-cloud-package-2026-10-09 74d88e66f0ebcfcdaae007d80ad5df5514e465b7 47f03f03cc26e40793dcce90cdc8c62d673ed9b9 a2c086a98da0fa2624cf14b327e13d59725d9a91f5c93659ca85a18a87e34ca5" \
         "$VERB_SPEED_SOURCE speed200 codex/verb-stage2-speed-2026-10-09 412b9ce8ff6274d6b1da548ed4b1509f2bbf1772 07f9428b143b9fe82b89e918b9b6921d4ea03b6f 83aec21dad227ad5f0b9ec0c82f92544b8c9c2e74e58c53f352e45137a62eb24"; do
  set -- $x; S=$1; SUB=$2; BR=$3; C=$4; T=$5; SH=$6
  git clone -q --no-checkout $HOME/sfn/sfn-compression-abm "$S"
  git -C "$S" checkout -q --detach e9ed84ae3ee6c458f392cd58cadf9fc030639900
  test "$(sha256sum "$VERB_PACKAGE/$SUB/source.bundle" | cut -d " " -f 1)" = $SH
  git -C "$S" bundle verify "$VERB_PACKAGE/$SUB/source.bundle"
  git -C "$S" fetch --no-tags "$VERB_PACKAGE/$SUB/source.bundle" refs/heads/$BR
  git -C "$S" checkout -q -b $BR $C
  test "$(git -C "$S" rev-parse HEAD)" = $C
  test "$(git -C "$S" rev-parse "HEAD^{tree}")" = $T
  echo "$SUB：HEAD $C、tree $T（README と同じ）"
done
python3.12 -m venv /srv/verb/env; VERB_PY=/srv/verb/env/bin/python; $VERB_PY --version
"$VERB_PY" "$VERB_SOURCE/tools/verb_measurement/cloud_run.py" prepare --source "$VERB_SOURCE" --commit 74d88e66f0ebcfcdaae007d80ad5df5514e465b7 --root "$VERB_OUTPUT_ROOT"
"$VERB_PY" "$VERB_SPEED_SOURCE/tools/verb_measurement/cloud_run.py" prepare --source "$VERB_SPEED_SOURCE" --commit 412b9ce8ff6274d6b1da548ed4b1509f2bbf1772 --root "$VERB_SPEED_ROOT"
echo "準備済み"
