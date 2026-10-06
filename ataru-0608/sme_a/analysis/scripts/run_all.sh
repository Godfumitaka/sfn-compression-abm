#!/bin/bash
# 走り終えた (a) 版の本（完了の印 .done がある本、種 1〜20）のうち、まだ解析していないものだけを解析する。読むだけ。
#   1) memcompare.py：古い本番との記憶の比べ（一本 10 秒ほど）
#   2) run_replay.py：tools/selcands_sme.py による保存記憶の再生と候補の調べ（一本 数時間。本番＋再生 ≦ 12、再生は MAXPAR 本まで）
#   3) tables.py：誤りの型の表・選び間違いの診断・区分表・時間の表
# 出力：~/sme_analysis/out/。ログ：~/sme_analysis/run_all.log
set -u
cd "$HOME/sme_analysis"
PY=python3.12
{
  echo "== $(date '+%F %T') 始め"
  nice -n 15 ionice -c3 $PY memcompare.py || echo "★ memcompare.py が失敗"
  $PY run_replay.py --maxpar "${MAXPAR:-4}" || echo "★ run_replay.py が失敗"
  nice -n 15 ionice -c3 $PY tables.py || echo "★ tables.py が失敗"
  echo "== $(date '+%F %T') 終わり"
} >> run_all.log 2>&1
