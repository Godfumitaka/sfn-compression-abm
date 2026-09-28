#!/bin/bash
# 2026-09-28 夜の委任書「使える量が尽きても止まらないようにする（マック）」：v3.8 のマックの分を、人の手なしで最後まで流す台本。
# 端末から切り離して走らせる（tools/mac_drivers/launch_detached.py で新しいセッションにする）。Code が止まっても走り続ける。
# 引き継ぎ：前の台本 tools/mac_v38_0928.sh の本体（MAINPID）だけを止め、走っている腕の台本（RUNPID）は走り終えさせてから、次の順に流す。
#   v38new_n70_hide（8 本）→ v38new_n70_f10 → v38new_n50_hide → v38new_n40_hide → v38new_n70_hide の残り（80 本まで）→ v38new_n70_f00 → v38new_n70_f025
#   腕ごとに tools/prod_v38.sh（ONLY=<腕>、並列 6、台帳は全部残す）。終わった台帳・解析は飛ばすので、途中で止まった腕も続きから走る。
#   各腕のあと：tools/prod_v38.sh の中で解析（走査の版 8・死因・出どころ別・生まれと型またぎ）と上げ。そのあと数えて control/ に短く書く。
#   上げに失敗したら、ログに書いて次の腕へ進む。
#   追記の 3 腕（hide の残り・f00・f025）は、始める前に空きを見る：空き − その腕の見込みの大きさ ＜ 30 GB なら、そこで止めてログに書く。
# ログ：~/v38prod/mac_v38.log（この台本）・~/v38prod/prod_v38.log（本番の台本）。止まったか：ps -axo pid,command | grep mac_v38_chain
set -u
# ★ 切り離しの道具（Python）が足す文字の設定（LC_CTYPE＝C.UTF-8、PEP 538）を外す。macOS の bash 3.2 はこの設定のもとで "$HOST（" の全角の字を
#   変数名に含めて読み、tools/prod_v38.sh が unbound variable で止まる（2026-09-28 18:46 に起きた）。
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-v38mac2
OUT=$HOME/v38prod; RES=$HOME/v33prod/results; LOG=$OUT/mac_v38.log
MAINPID=${MAINPID:-}; RUNPID=${RUNPID:-}
say() { echo "$(date '+%F %T') [chain] $*" >> "$LOG"; }
freegb() { df -Pk "$OUT" | awk 'NR==2 {printf "%d", $4/1048576}'; }
pushctl() {
  ( cd $RES && git add "control/$1" && git commit -q -m "control：$1" && for i in 1 2 3 4 5 6; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 10; done
    git fetch -q origin results-2026-09-27 && git diff --quiet origin/results-2026-09-27 -- "control/$1" ) >> "$LOG" 2>&1 && say "control/$1 を上げた（確かめ済み）" || say "★ control/$1 を上げられなかった（次へ進む）"
}
note() {   # $1 腕  $2 見出しに足す文
  local arm=$1
  local S D CMP R F
  S=$( (cd $W && python3.12 tools/v37_arm_counts.py $OUT/$arm $arm 4) 2>>"$LOG" | tail -1 )
  D=$(python3.12 - "$OUT/$arm/merged/死因_$arm.json" <<'P' 2>>"$LOG"
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception as e: print("死因の表が無い", e); sys.exit()
print("削除 {:,}・死因 ".format(d["削除"]) + "・".join(f"{k} {v:,}" for k,v in d["死因"].items()) + f"・死んだ試行に自分が伏せ辺だった行 {d.get('死んだ試行に自分が伏せ辺だった行')}")
P
)
  R=$(python3.12 - "$OUT/$arm/manifest.jsonl" <<'P' 2>>"$LOG"
import json,sys,collections
c=collections.Counter(); n=0
for l in open(sys.argv[1]):
    r=json.loads(l); v=r.get("v38") or {}
    if v: n+=1; c.update({k:v.get(k,0) for k in ("refuted","confirmed_disclosure","confirmed_by_prediction","seat_obs_added","unconfirmed","undetermined")})
print(f"走行 {n} 本の和：D-11 の反証 {c['refuted']:,}・開示で確認 {c['confirmed_disclosure']:,}・予測で確認 {c['confirmed_by_prediction']:,}・席の観察 {c['seat_obs_added']:,}・未確認 {c['unconfirmed']:,}・判定不能 {c['undetermined']:,}（tools/v38.py の STATS）")
P
)
  CMP=""
  if [[ "$arm" == "v38new_n70_hide" ]]; then
    git -C $RES fetch -q origin results-2026-09-27
    CMP=$(python3.12 - "$OUT/$arm/post/sha256.jsonl" "$RES" <<'P' 2>>"$LOG"
import json,subprocess,sys
mac={(r["cell"],r["seed"]):r["body_sha256"] for r in map(json.loads,open(sys.argv[1]))}
p=subprocess.run(["git","-C",sys.argv[2],"show","origin/results-2026-09-27:ataru-0608/v38new_n70_hide/sha256.jsonl"],capture_output=True,text=True)
if p.returncode!=0: print("デスクトップの同じ腕の sha256.jsonl が結果のブランチにまだ無い"); sys.exit()
dt={(r["cell"],r["seed"]):r["body_sha256"] for r in map(json.loads,p.stdout.splitlines())}
both=set(mac)&set(dt); same=[k for k in both if mac[k]==dt[k]]; diff=sorted(k for k in both if mac[k]!=dt[k])
print(f"デスクトップの同じ腕との台帳の本体の sha256：両方にある {len(both)} 本のうち一致 {len(same)}・不一致 {len(diff)}" + (f"（不一致の例 {diff[:4]}）" if diff else ""))
P
)
  fi
  F="$(date +%Y-%m-%d_%H%M)_v3.8_${arm}_マック.md"
  {
    echo "# v3.8 の腕 $arm $2（マックの Code の台本 tools/mac_drivers/mac_v38_chain.sh、$(date '+%F %T')）　判断しない"; echo
    echo "- 結果：results-2026-09-27 の mac/$arm/。台帳は ~/v38prod/$arm に全部残した。"
    echo "- 死因（merged/死因_$arm.json）：$D"
    echo "- v3.8 の数え：$R"
    echo "- 数え（tools/v37_arm_counts.py）：$S"
    echo "  - L2〜L6 ＝ 中心的過程のラベルが付いた定義（名前@生まれた試行）の数。走行末に生きているかを問わない。"
    echo "  - 型またぎ ＝ 誕生のうち、土台の場面の型と今の場面の型が違うもの。同化も同じ比べ方。"
    [[ -n "$CMP" ]] && echo "- $CMP"
    echo "- 本番の台本の記録：$(grep -E "腕 $arm (の解析済み|が results|を results|に出どころ|に生まれ)|★" $OUT/prod_v38.log | tail -4 | tr '\n' ' ')"
  } > "$RES/control/$F"
  pushctl "$F"
}
run_arm() {   # $1 腕  $2 SEEDS_LIMIT
  say "腕 $1 を始める（SEEDS_LIMIT $2、並列 6、空き $(freegb) GB）"
  local n0; n0=$(wc -l < $OUT/prod_v38.log 2>/dev/null || echo 0)
  (cd $W && MACHINE=mac JOBS=6 MINFREE_GB=30 SEEDS_LIMIT=$2 OUT=$OUT HOST=mac RESULTS=$RES PY=python3.12 ARMSF=tools/prod_v38_mac_arms.tsv ONLY=$1 caffeinate -i -s bash tools/prod_v38.sh >> $OUT/prod_v38_stdout.log 2>&1)
  say "腕 $1 の台本が終わった rc=$?"
  tail -n +$((n0+1)) $OUT/prod_v38.log | grep -q "腕 $1 が results-2026-09-27 に上がっていることを確かめた" || say "★ 腕 $1 の上げが確かめられていない（prod_v38.log を見る）。次へ進む"
}
say "引き継ぎ：前の台本の本体（${MAINPID:-無し}）を止め、走っている腕の台本（${RUNPID:-無し}）を待つ"
[[ -n "$MAINPID" ]] && kill -TERM $MAINPID 2>/dev/null
if [[ -n "$RUNPID" ]]; then while kill -0 $RUNPID 2>/dev/null; do sleep 30; done; fi
say "前の台本の腕が終わった（または無かった）"
# ★ v38new_n70_hide（8 本）は 18:45 に上がり、前の台本が control/ に書いた。ここでは走らせない。
run_arm v38new_n70_f10 0; note v38new_n70_f10 ""
run_arm v38new_n50_hide 0; note v38new_n50_hide ""
run_arm v38new_n40_hide 0; note v38new_n40_hide ""
for spec in "v38new_n70_hide 7" "v38new_n70_f00 10" "v38new_n70_f025 9"; do
  set -- $spec; arm=$1; est=$2
  if (( $(freegb) - est < 30 )); then say "★ 空き $(freegb) GB − 見込み $est GB が 30 GB を切るので、ここで止める（$arm は始めない）"; break; fi
  if [[ "$arm" == "v38new_n70_hide" ]]; then
    # 8 本の速報の、作り直さない解析の出力（出どころ別・生まれと型またぎ・数え）を、消さずに merged/速報8本/ へ移す（80 本で作り直すため）
    mkdir -p $OUT/$arm/merged/速報8本
    for f in defs_spoke8src_$arm.csv 出どころ別_$arm.md defs_spoke8org_$arm.csv 型またぎ_$arm.md 型またぎ_$arm.json; do
      [[ -e $OUT/$arm/merged/$f ]] && mv $OUT/$arm/merged/$f $OUT/$arm/merged/速報8本/
    done
    run_arm $arm 0; note $arm "（80 本）"
  else
    run_arm $arm 0; note $arm ""
  fi
done
say "CHAINDONE"
