#!/bin/bash
# 2026-09-28 夕の判断「v3.7 を止める／v3.8 の差分を読む／v3.8 の走行（マックの分）」の 2。tools/mac_v37_0928.sh の写しを v3.8 にした。
# 1 先の確かめ（--own-evidence を切った v3.8 で、マックの v3.7 の主 hide・seed001・θ′2.1・最頻が一字一句同じ）を待ち、違えば止めて control/ に書く。
# 2 腕を一つずつ（tools/prod_v38.sh、ONLY=<腕>、並列 6、台帳は全部残す、MINFREE_GB=30。主の hide は SEEDS_LIMIT=2 で 8 本）。作業場所 sfn-compression-abm-v38mac（0bef5fc ＝ v3.8-main に腕の表と数えの道具を足しただけ）。
# 3 腕が上がるたびに、死因（merged/死因_<腕>.json）と tools/v37_arm_counts.py の数えを control/ に短く書く（主の hide は、デスクトップの同じ腕の台帳の sha256 とも突き合わせる）。
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-v38mac
OUT=$HOME/v38prod; RES=$HOME/v33prod/results; LOG=$HOME/v38prod/mac_v38.log; mkdir -p $OUT
CHK=/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_v38_2026-09-28/check_mac/v37_on
say() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
pushctl() {   # $1 ファイル名（control/ の下）
  ( cd $RES && git add "control/$1" && git commit -q -m "control：$1" && for i in 1 2 3 4 5 6; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 10; done
    git fetch -q origin results-2026-09-27 && git diff --quiet origin/results-2026-09-27 -- "control/$1" ) && say "control/$1 を上げた（確かめ済み）" || say "★ control/$1 を上げられなかった"
  echo "control/$1" >> $HOME/v33prod/audit_seen.txt
}
say "v3.8 のマックの分：先の確かめを待つ"
until [[ -s $CHK/manifest.jsonl ]]; do sleep 30; done
OK=$(python3.12 -c "import json;r=json.loads(open('$CHK/manifest.jsonl').readline());c=r.get('compare') or {};print(int(bool(c.get('snapshot_hash_equal')) and bool(c.get('body_sha_equal')) and not r.get('error')))")
python3.12 -c "import json;r=json.loads(open('$CHK/manifest.jsonl').readline());print(r.get('compare'), r.get('error'))" >> "$LOG"
if [[ "$OK" != "1" ]]; then
  say "★ 先の確かめが一致しなかった。走らせずに止める"
  F="$(date +%Y-%m-%d_%H%M)_v3.8の先の確かめが一致しない_マック.md"
  printf '# v3.8 の先の確かめが一致しない（マックの Code、%s）\n\n--own-evidence を切った v3.8（v3.8-main）で、マックの v3.7 の主 hide・seed001・θ′2.1・最頻（~/v37prod/v37new_n70_hide）を走らせ直したが、一致しなかった。判断に従い、v3.8 の腕は走らせずに止めた。\n\n比べの結果：%s\n' "$(date '+%F %T')" "$(tail -1 $LOG)" > "$RES/control/$F"; pushctl "$F"; exit 3
fi
say "先の確かめが一致した（全試行の指紋・本体の sha256）"
while IFS=$'\t' read -r -u 3 mach arm cfg nsim kind trials keepc; do
  [[ -z "$mach" || "$mach" == \#* ]] && continue
  SL=0; [[ "$arm" == "v38new_n70_hide" ]] && SL=2
  say "腕 $arm を始める（並列 6、MINFREE_GB 30、SEEDS_LIMIT $SL）"
  (cd $W && MACHINE=mac JOBS=6 MINFREE_GB=30 SEEDS_LIMIT=$SL OUT=$OUT HOST=mac RESULTS=$RES PY=python3.12 ARMSF=tools/prod_v38_mac_arms.tsv ONLY=$arm caffeinate -i -s bash tools/prod_v38.sh >> $OUT/prod_v38_stdout.log 2>&1)
  say "腕 $arm の台本が終わった rc=$?"
  S=$( (cd $W && python3.12 tools/v37_arm_counts.py $OUT/$arm $arm 4) 2>>"$LOG" | tail -1 )
  say "数え：$S"
  D=$(python3.12 -c "import json,sys
try:
 d=json.load(open('$OUT/$arm/merged/死因_$arm.json'))
except Exception as e: print('死因の表が無い', e); sys.exit()
print('削除 {:,}・死因 '.format(d['削除']) + '・'.join(f'{k} {v:,}' for k,v in d['死因'].items()) + f'・死んだ試行に自分が伏せ辺だった行 {d.get(\"死んだ試行に自分が伏せ辺だった行\")}')" 2>>"$LOG")
  say "死因：$D"
  CMP=""
  if [[ "$arm" == "v38new_n70_hide" ]]; then
    git -C $RES fetch -q origin results-2026-09-27
    CMP=$(python3.12 - "$OUT/$arm/post/sha256.jsonl" "$RES" <<'P'
import json,subprocess,sys
mac={(r["cell"],r["seed"]):r["body_sha256"] for r in map(json.loads,open(sys.argv[1]))}
p=subprocess.run(["git","-C",sys.argv[2],"show","origin/results-2026-09-27:ataru-0608/v38new_n70_hide/sha256.jsonl"],capture_output=True,text=True)
if p.returncode!=0: print("デスクトップの同じ腕の sha256.jsonl が結果のブランチにまだ無い"); sys.exit()
dt={(r["cell"],r["seed"]):r["body_sha256"] for r in map(json.loads,p.stdout.splitlines())}
both=set(mac)&set(dt); same=[k for k in both if mac[k]==dt[k]]; diff=sorted(k for k in both if mac[k]!=dt[k])
print(f"デスクトップの同じ腕との台帳の本体の sha256：両方にある {len(both)} 本のうち一致 {len(same)}・不一致 {len(diff)}" + (f"（不一致の例 {diff[:4]}）" if diff else ""))
P
)
    say "$CMP"
  fi
  F="$(date +%Y-%m-%d_%H%M)_v3.8_${arm}_マック.md"
  printf '# v3.8 の腕 %s（マックの Code、%s）　判断しない\n\n- 結果：results-2026-09-27 の mac/%s/（表・まとめ〔死因の表を含む〕・図・README・出どころ別）。台帳は ~/v38prod/%s に全部残した。\n- 死因（tools/death_cause.py、merged/死因_<腕>.json）：%s\n- 数え（tools/v37_arm_counts.py、v3.8mac-2026-09-28 0bef5fc）：%s\n  - L2〜L6 ＝ 中心的過程のラベルが付いた定義（名前@生まれた試行）の数（走行末に生きているかを問わない）。\n  - 型またぎ ＝ 誕生（was_extension＝False）のうち、土台の場面（base_written_at の試行）の型と今の場面の型が違うもの。\n  - 同化 ＝ was_extension＝True の登録。その「土台と場面の型が違う」も同じ比べ方。\n%s\n- 台本の記録：%s\n' \
    "$arm" "$(date '+%F %T')" "$arm" "$arm" "$D" "$S" "$([[ -n "$CMP" ]] && echo "- $CMP")" "$(grep -E "腕 $arm (の解析済み|が results|を results)|★" $OUT/prod_v38.log | tail -3 | tr '\n' ' ')" > "$RES/control/$F"
  pushctl "$F"
done 3< "$W/tools/prod_v38_mac_arms.tsv"
say "V38MACDONE"
