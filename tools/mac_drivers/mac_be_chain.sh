#!/bin/bash
# 委任書「B＋E（書き直しの費用で結ぶ統合版）の実装・較正・走行（2026-09-29 午後）」の 2・3：人の手なしで最後まで流す台本（マック）。
# 端末から切り離し、caffeinate -dimsu の下で走らせる（tools/mac_drivers/launch_detached.py）。
# 1 較正（tools/mac_drivers/be_calib.sh、~/v310prod/v310BE_cal）が終わるのを待ち、tools/v310be_calib.py で λ の 4 段階を出して
#   control/2026-09-29_BE_較正.md に上げる。正の点が無ければ「未較正」と書いて止まる。
# 2 タグ v3.10be-main が付いていて、作業場所に未コミットの変更が無いことを確かめる（無ければ止まる）。
# 3 腕の表 tools/prod_v310BE_mac_arms.tsv を作る（L0・L25・L50・L75・L90・L1・L50_Uabs。重複した λ の段は一つにまとめる）。
# 4 腕ごとに tools/prod_v39.sh（ONLY＝その腕、並列 8、台帳は全部残す）→ tools/v310be_summary.py → 結果のブランチへ上げる → control/ に一行。
# ログ：~/v310prod/mac_be.log（この台本）・~/v310prod/prod_v39.log（本番の台本）。
set -u
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-v310mac
OUT=$HOME/v310prod; RES=$HOME/v33prod/results; LOG=$OUT/mac_be.log; mkdir -p $OUT
CAL=$OUT/v310BE_cal
CTRL=control/2026-09-29_BE_腕ごと_マック.md
ARMSF=tools/prod_v310BE_mac_arms.tsv
say() { echo "$(date '+%F %T') [be] $*" >> "$LOG"; }
pushctl() {
  ( cd $RES && git add "control/$1" && git commit -q -m "control：$1" && for i in 1 2 3 4 5 6; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 10; done
    git fetch -q origin results-2026-09-27 && git diff --quiet origin/results-2026-09-27 -- "control/$1" ) >> "$LOG" 2>&1 && say "control/$1 を上げた（確かめ済み）" || say "★ control/$1 を上げられなかった"
}
say "較正が終わるのを待つ"
until grep -q "BECALIBDONE" $OUT/be_calib.log 2>/dev/null; do sleep 30; done
grep BECALIBDONE $OUT/be_calib.log | tail -1 >> "$LOG"
(cd $W && python3.12 tools/v310be_calib.py $CAL $OUT/be_calib.md $OUT/be_calib.json) >> "$LOG" 2>&1
LAMJ=$(python3.12 -c "import json;d=json.load(open('$OUT/be_calib.json'));print(json.dumps(d.get('λ') or {}))")
if [[ "$LAMJ" == "{}" ]]; then
  say "★ 正の点が無く、未較正。止める"
  F="$(date +%Y-%m-%d_%H%M)_BEの較正_未較正_マック.md"
  printf '# B＋E の較正：正の点が無い（未較正）（マックの Code の台本、%s）\n\n%s\n' "$(date '+%F %T')" "$(cat $OUT/be_calib.json)" > "$RES/control/$F"; pushctl "$F"; exit 3
fi
python3.12 - "$OUT/be_calib.json" "$RES/control/2026-09-29_BE_較正.md" <<'P' >> "$LOG" 2>&1
import json, sys
d = json.load(open(sys.argv[1]))
L = ["# B＋E の較正：λ（マックの Code の台本）　判断しない", "",
     "委任書「B＋E（書き直しの費用で結ぶ統合版）の実装・較正・走行」の 2（仕様 9 節）。",
     f"- コード：{', '.join(d['コード'])}（ブランチ v3.10mac-2026-09-29）。",
     "- 較正の走行：設定 config/sweep_b2_hide_s41_2026-09-27.json（種 41〜60。評価の s1＝種 1〜20 とは別）、セル f0.5000_th2.1000_first_order（最頻）、1,740 試行、"
     f"{d['走行']} 本。",
     "- 旗：--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first "
     "--fill-norestate --no-charge2 --own-evidence --v39 --v39-decay actr --v39-budget inf --v39-price 0 --v310-be --v39-dump-cands --nsim 0.7 "
     "--ident-rho 0.5 --ident-argmax --ident-commons",
     f"- 集めたもの：各試行の変換の前に列挙した、正の V（F 席の V_FH と H 席の V_HU）。20 本の全試行ぶんで {d['点の数']:,} 個（正でない点 {d['正でない点']}）。",
     "- パーセンタイルは線形補間（numpy.percentile の既定と同じ式。tools/v310be_calib.py）。重複した値は一つの段にまとめる。", "",
     "| 段階 | パーセンタイル | λ |", "|---|---:|---:|"]
for k, v in d["パーセンタイル"].items():
    L.append(f"| L{k} | {k} | {v!r} |")
L.append("| L1 | （承認済みの条件） | 1.0 |")
if d.get("統合した段"):
    L += ["", f"- 同じ値でまとめた段：{d['統合した段']}"]
L += ["", "| 種 | 正の点の数 |", "|---|---:|"] + [f"| {k} | {v:,} |" for k, v in d["種ごとの点の数"].items()]
open(sys.argv[2], "w", encoding="utf-8").write("\n".join(L) + "\n")
P
pushctl "2026-09-29_BE_較正.md"
cd $W
if [[ -n "$(git status --short -- tools abm tests)" ]] || ! git describe --exact-match --tags HEAD 2>/dev/null | grep -q "v3.10be-main"; then
  say "★ 作業場所に未コミットの変更があるか、HEAD にタグ v3.10be-main が無い。腕は走らせずに止める（$(git status --short | tr '\n' ' ')・$(git describe --tags --always)）"
  exit 3
fi
python3.12 - "$OUT/be_calib.json" "$ARMSF" <<'P' >> "$LOG" 2>&1
import json, sys
d = json.load(open(sys.argv[1]))
lam = d["λ"]
cfg, cell = "config/sweep_b2_hide_s1_2026-09-22.json", "f0.5000_th2.1000_first_order"
base = "--v39-decay actr --v39-budget inf --v310-be"
arms = [("v310BE_L0", f"{base} --v39-price 0")]
for k in ("25", "50", "75", "90"):
    if k in lam:
        arms.append((f"v310BE_L{k}", f"{base} --v39-price {lam[k]!r}"))
arms.append(("v310BE_L1", f"{base} --v39-price 1"))
k50 = "50" if "50" in lam else next(k for k, v in d["統合した段"].items() if 50 in v)
arms.append(("v310BE_L50_Uabs", f"{base} --v39-u abstain --v39-price {lam[k50]!r}"))
with open(sys.argv[2], "w", encoding="utf-8") as f:
    f.write("# v3.10 B＋E のマックの腕（委任書「B＋E（書き直しの費用で結ぶ統合版）」の 3）。上から順に。λ は control/2026-09-29_BE_較正.md（tools/mac_drivers/mac_be_chain.sh が書いた）。台帳は全部残す。\n")
    f.write("# 列：機械\t腕\t設定\t基準\t腕の種類\t試行数\t残す\tセル\t腕の旗\n")
    for a, fl in arms:
        f.write(f"mac\t{a}\t{cfg}\t0.7\tnew\t1740\tall\t{cell}\t{fl}\n")
print(open(sys.argv[2]).read())
P
git add $ARMSF && git commit -q -m "B＋E の腕の表（λ は較正の値）" && git push -q origin v3.10mac-2026-09-29 >> "$LOG" 2>&1
if [[ ! -e "$RES/$CTRL" ]]; then
  printf '%s\n' "# v3.10 B＋E（書き直しの費用で結ぶ統合版）の腕ごとの一行（マック）　判断しない" "" \
    "委任書「B＋E（書き直しの費用で結ぶ統合版）の実装・較正・走行」の 3。台本 tools/mac_drivers/mac_be_chain.sh（タグ v3.10be-main、ブランチ v3.10mac-2026-09-29）が、腕が終わるたびに tools/v310be_summary.py の一行を足して上げる。" \
    "評価：s1（種 1〜20）、セル f0.5000_th2.1000_first_order（最頻）、1,740 試行、各腕 20 本。すべて --v39-decay actr・予算無限・--v310-be（α＝1）。λ は control/2026-09-29_BE_較正.md。" \
    "λC と R：C＝各試行の終わりの総費用（ビット）、R＝採った候補の書換ビットの累計＋B の採点の書換ビットの累計。走行ごとの推移は結果のブランチの mac/<腕>/be推移_<腕>.csv.gz。" "" > "$RES/$CTRL"
  pushctl "$(basename "$CTRL")"
fi
for ARM in $(grep -v '^#' $ARMSF | cut -f2); do
  say "腕 $ARM を始める"
  (MACHINE=mac JOBS=8 MINFREE_GB=15 OUT=$OUT HOST=mac RESULTS=$RES PY=python3.12 ARMSF=$ARMSF ONLY=$ARM caffeinate -dimsu bash tools/prod_v39.sh >> $OUT/prod_v39_stdout.log 2>&1)
  say "腕 $ARM の prod_v39.sh が終わった rc=$?"
  LINE=$(python3.12 tools/v310be_summary.py $OUT/$ARM $ARM $RES mac 2>> "$LOG" | tail -1)
  if [[ "$LINE" == "- "* ]]; then
    python3.12 tools/results_push.py $RES mac $ARM "結果：mac の $ARM に B＋E の要約と推移を足す（tools/v310be_summary.py）" >> "$LOG" 2>&1 && say "腕 $ARM の B＋E の要約を上げた" || say "★ 腕 $ARM の B＋E の要約を上げられなかった"
    ( cd $RES && git pull -q --rebase origin results-2026-09-27 && echo "$LINE" >> "$CTRL" && git add -- "$CTRL" \
      && git commit -q -m "control：B＋E の腕 $ARM の一行（マック）" \
      && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || { git rebase --abort; break; }; sleep 5; done \
      && git fetch -q origin results-2026-09-27 && git diff --quiet origin/results-2026-09-27 -- "$CTRL" ) >> "$LOG" 2>&1 \
      && say "腕 $ARM の一行を上げた" || say "★ 腕 $ARM の一行を上げられなかった（$LINE）"
  else
    say "★ 腕 $ARM の B＋E の要約が失敗（$LOG）"
  fi
done
say "BECHAINDONE"
