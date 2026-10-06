#!/bin/bash
# WSL を起動し直した後に、(a) 版の本番を始め直す（2026-10-06「WSL のメモリの割り当てを増やす準備」）。
# 1. MemTotal を確かめる（約 36GB でなければ止まる）。
# 2. 版の一覧と、残りの一覧を確かめる。
# 3. 途中で止まった本（出力のフォルダはあるが .done が無い）があれば、出力と plan1 の写しを ~/smeprod_a/stopped_<日時>/ へ移す
#    （消さない）。launch_b は「出力のフォルダが無い本」を残りとするので、移した本は最初からやり直す一覧に戻る。
# 4. launch_b を tmux smeprod_b で始め直す。memroom.py の式・同時の本数の上限（8）・空き 4GiB を残す決まりは変えない。
# 5. 最初の 1 時間、1 分ごとに、同時の本数・空きメモリ・スワップ・C: の空きを ~/smeprod_a/after_wsl_1h.tsv に記録する（tmux after1h）。
# 使い方：bash ~/smeprod_a/resume_after_wsl.sh        （--check で 1〜3 の確かめだけ。何も移さず、何も始めない）
set -u
P=$HOME/smeprod_a; CHECK=0; [[ ${1:-} == --check ]] && CHECK=1
TS=$(date '+%Y-%m-%d_%H%M'); OUT=$P/resume_$TS.log
say() { echo "$(date '+%F %T') $*" | tee -a $OUT; }

# 1. メモリ
MT=$(awk '/MemTotal/ {print $2}' /proc/meminfo); MTG=$(awk "BEGIN{printf \"%.1f\", $MT/1024/1024}")
say "MemTotal ${MT} kB（${MTG}GiB）、SwapTotal $(awk '/SwapTotal/ {print $2}' /proc/meminfo) kB、nproc $(nproc)"
if (( CHECK == 0 )) && (( MT < 30 * 1024 * 1024 )); then say "★ MemTotal が 30GiB 未満。.wslconfig が効いていない。始め直さずに止まる"; exit 2; fi

# 2. 版の一覧と残りの一覧
say "版の一覧：$(($(wc -l < $P/版の一覧.tsv) - 1)) 本を始めた記録（最後：$(tail -1 $P/版の一覧.tsv | tr '\t' ' ')）"
python3 - <<'PY' | tee -a $OUT
import json, os, glob
c = json.load(open("/home/tatsu/smeprod_a/plan/sme.commands.json"))
done = [x for x in c if glob.glob(x["command"][3] + "/ledgers/cells/*/seed*.done")]
part = [x for x in c if os.path.exists(x["command"][3]) and x not in done]
left = [x for x in c if not os.path.exists(x["command"][3])]
print(f"完了 {len(done)} 本、出力はあるが完了の印が無い本 {len(part)} 本、まだ始めていない本 {len(left)} 本（計 {len(c)}）")
for x in part: print(f"  完了の印が無い：{x['arm']} 種 {x['seed']}")
open("/home/tatsu/smeprod_a/.resume_partial.tsv", "w").write("".join(f"{x['arm']}\t{x['seed']}\n" for x in part))
PY
R=$(ps -eo args | awk '$2=="tools/v3_run.py"' | grep -c "/home/tatsu/smeprod_a/sme/")
say "いま走っている本 ${R}"
if (( CHECK == 1 )); then say "--check なので、ここで終わり"; exit 0; fi
if (( R > 0 )); then say "★ 走っている本がある（WSL を起動し直した直後ではない）。何も移さずに止まる"; exit 3; fi
if tmux has-session -t smeprod_b 2>/dev/null; then say "★ tmux smeprod_b がもうある。二重に始めないよう止まる"; exit 4; fi

# 3. 途中で止まった本を移す（消さない）
if [ -s $P/.resume_partial.tsv ]; then
  ST=$P/stopped_$TS; mkdir -p $ST
  while IFS=$'\t' read -r ARM SEED; do
    S=$(printf %03d $SEED)
    mkdir -p $ST/sme/$ARM; mv $P/sme/$ARM/seed$S $ST/sme/$ARM/
    [ -d $P/plan1/${ARM}_seed$S ] && { mkdir -p $ST/plan1; mv $P/plan1/${ARM}_seed$S $ST/plan1/; }
    echo -e "$ARM\t$SEED\t$(date '+%F %T')" >> $ST/最初からやり直す一覧.tsv
    say "移した：$ARM 種 $SEED → $ST（最初からやり直す一覧に戻した）"
  done < $P/.resume_partial.tsv
fi

# 4. launch_b を始め直す（残りの一覧は launch_b が出力のフォルダの有無から作り直す）
[ -f $P/残り_b.tsv ] && cp $P/残り_b.tsv $P/残り_b_再起動前_$TS.tsv
tmux new-session -d -s smeprod_b "bash $P/launch_b.sh"
say "launch_b を始め直した（tmux smeprod_b）"

# 5. 最初の 1 時間の記録
tmux new-session -d -s after1h "bash $P/after1h.sh 60"
say "最初の 1 時間の記録を始めた（~/smeprod_a/after_wsl_1h.tsv）"
