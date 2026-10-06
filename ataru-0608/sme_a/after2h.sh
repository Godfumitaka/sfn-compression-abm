#!/bin/bash
# 控えを捨てる版への切り替えの後の最初の 2 時間：1 分ごとに、CPU の使用（/proc/stat の差）、同時の本数、メモリ、スワップ、C: の空き、vhdx の大きさを記録する（読むだけ）。
F=$HOME/smeprod_a/after_evict_2h.tsv; N=${1:-120}
V="/mnt/c/Users/tatsu/AppData/Local/wsl/{08afc2c4-dbb6-4ed8-a3d9-f738345258a5}/ext4.vhdx"
[ -f $F ] || echo -e "time\tcpu_busy_pct\tn_running\tmem_available_gib\tswap_used_mib\tc_free_gb\tvhdx_gb\tload1" > $F
read -r _ a b c d e f g h _ < /proc/stat; T0=$((a+b+c+d+e+f+g+h)); I0=$((d+e))
for i in $(seq $N); do
  sleep 60
  read -r _ a b c d e f g h _ < /proc/stat; T1=$((a+b+c+d+e+f+g+h)); I1=$((d+e))
  cpu=$(awk "BEGIN{printf \"%.1f\", 100*(1-($I1-$I0)/($T1-$T0))}"); T0=$T1; I0=$I1
  n=$(ps -eo args | awk '$2=="tools/v3_run.py"' | grep -c "/home/tatsu/smeprod_a/sme/")
  m=$(awk '/MemAvailable/{a=$2} /SwapTotal/{st=$2} /SwapFree/{sf=$2} END{printf "%.1f\t%.0f", a/1048576, (st-sf)/1024}' /proc/meminfo)
  c=$(df -BG /mnt/c | awk 'NR==2{gsub("G","",$4); print $4}')
  v=$(stat -c %s "$V" | awk '{printf "%.2f", $1/1e9}')
  echo -e "$(date '+%F %T')\t$cpu\t$n\t$m\t$c\t$v\t$(cut -d' ' -f1 /proc/loadavg)" >> $F
done
