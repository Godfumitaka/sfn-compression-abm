#!/bin/bash
# WSL を起動し直した後の最初の 1 時間：1 分ごとに、同時の本数・メモリ・スワップ・C: の空きを記録する（読むだけ）。引数で回数を変えられる（既定 60）。
P=$HOME/smeprod_a; F=$P/after_wsl_1h.tsv; N=${1:-60}
[ -f $F ] || echo -e "time\tn_running\tmem_total_gib\tmem_available_gib\tswap_used_mib\tc_free_gb\tload1" > $F
for i in $(seq $N); do
  n=$(ps -eo args | awk '$2=="tools/v3_run.py"' | grep -c "/home/tatsu/smeprod_a/sme/")
  m=$(awk '/MemTotal/{t=$2} /MemAvailable/{a=$2} /SwapTotal/{st=$2} /SwapFree/{sf=$2} END{printf "%.1f\t%.1f\t%.0f", t/1048576, a/1048576, (st-sf)/1024}' /proc/meminfo)
  c=$(df -BG /mnt/c | awk 'NR==2{gsub("G","",$4); print $4}')
  echo -e "$(date '+%F %T')\t$n\t$m\t$c\t$(cut -d' ' -f1 /proc/loadavg)" >> $F
  if (( i < N )); then sleep 60; fi
done
