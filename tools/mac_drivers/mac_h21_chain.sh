#!/bin/bash
# 委任書「物の組で見分ける箇所の洗い出し・席の履歴の直し・直した B＋E の走らせ直し（2026-09-29 夜）」の 5（マック）：
#   デスクトップのタグ v3.10h-main が control/ に知らされたら、B＋E（--v310-be --hist-role）の 7 腕を確かめ用の種 s21（種 21〜40）で走らせる。
# ★ 2026-09-30 の追加・置換指示：履歴と採点の両方を直した新しいタグで走らせる。タグと足す旗は、マックの Code が control/ の知らせを読んで
#   確かめてから、環境変数で渡して始める（自動では待たない）：TAG＝<新しいタグ>  EXTRA＝"--hist-role <採点の直しの旗>"
#   ★ 結果は上げるが、要約は書かない（アストラが見分ける量を決めるまで読まないため）。上げるのは flag.json・台帳の本体の sha256 の一覧・README だけ。
#     台帳・side はマックの ~/v310hprod/<腕> に全部残す。control/ には腕ごとに「走り終わった」ことだけを書く（数は書かない）。
#   ★ 空きが 15 GB を切りそうなら（腕を始める前に、空き − 腕一つの大きさの見込み 2 GB ＜ 15 GB なら）、腕の区切りで止めて control/ に書く。
#     そのあとは空きが戻るのを 5 分ごとに見て、戻れば同じ腕から続ける（済んだ走行は飛ばす）。
# 端末から切り離し、caffeinate -dimsu の下で走らせる。ログ：~/v310hprod/mac_h21.log。
set -u
unset LC_CTYPE LC_ALL LANG
REPO=/Users/tatsu-admin/sfn/sfn-compression-abm
TAG=${TAG:?新しいタグを TAG に渡す}
EXTRA=${EXTRA:?両方の直しの旗を EXTRA に渡す}
export TAG EXTRA
W=/Users/tatsu-admin/sfn/sfn-compression-abm-${TAG}
OUT=$HOME/v310hprod; RES=$HOME/v33prod/results; LOG=$OUT/mac_h21.log; mkdir -p $OUT
CTRL=control/2026-09-30_BE直し_s21_走行_マック.md
say() { echo "$(date '+%F %T') [h21] $*" >> "$LOG"; }
freegb() { df -Pk "$HOME" | awk 'NR==2 {printf "%d", $4/1048576}'; }
pushctl() {
  ( cd $RES && git add "$1" && git commit -q -m "control：$(basename "$1")" && for i in 1 2 3 4 5 6; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 10; done
    git fetch -q origin results-2026-09-27 && git diff --quiet origin/results-2026-09-27 -- "$1" ) >> "$LOG" 2>&1 && say "$1 を上げた（確かめ済み）" || say "★ $1 を上げられなかった"
}
ctl_line() {   # control/ の一行を足して上げる
  ( cd $RES && git pull -q --rebase origin results-2026-09-27 ) >> "$LOG" 2>&1
  if [[ ! -e "$RES/$CTRL" ]]; then
    printf '%s\n' "# B＋E（履歴と採点を直した版）の確かめ用の種 s21 の走行（マック）　要約は書かない" "" \
      "委任書「物の組で見分ける箇所の洗い出し・席の履歴の直し・直した B＋E の走らせ直し（2026-09-29 夜）」の 5。台本 tools/mac_drivers/mac_h21_chain.sh（ブランチ v3.10mac-2026-09-29）。" \
      "設定 config/sweep_b2_hide_s21_2026-09-22.json（種 21〜40）、セル f0.5000_th2.1000_first_order（最頻）、1,740 試行、各腕 20 本。コードはデスクトップのタグ $TAG、足す旗 $EXTRA。λ は control/2026-09-29_BE_較正.md のまま。" \
      "★ 委任書により、結果の数・要約は書かない。結果のブランチの mac/<腕>/ には flag.json・台帳の本体の sha256 の一覧（sha256.jsonl）・README だけを上げる。台帳と side はマックの ~/v310hprod/<腕> に全部残す。" "" > "$RES/$CTRL"
  fi
  echo "$1" >> "$RES/$CTRL"
  pushctl "$CTRL"
}
say "タグ $TAG・足す旗 $EXTRA で始める（マックの Code が control/ の知らせを確かめて渡した）"
git -C $REPO fetch -q origin --tags >> "$LOG" 2>&1
[[ -d $W ]] || git -C $REPO worktree add -q --detach $W $TAG >> "$LOG" 2>&1
cd $W
TAGC=$(git rev-parse --short HEAD)
say "作業場所 $W（$TAGC、$(git describe --tags)）"
for f in $EXTRA; do
  if ! python3.12 tools/v3_run.py --help 2>/dev/null | grep -q -- "$f"; then
    say "★ $TAG の tools/v3_run.py に旗 $f が無い。走らせずに止める"
    ctl_line "- $(date '+%H:%M') ★ タグ $TAG（$TAGC）の tools/v3_run.py に旗 $f が見つからないので、走らせずに止めた。"
    exit 3
  fi
done
LAMJ=$HOME/v310prod/be_calib.json
FL="--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-decay actr --v39-budget inf --v310-be $EXTRA --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --workers 8 --no-compare"
L25=$(python3.12 -c "import json;print(repr(json.load(open('$LAMJ'))['λ']['25']))")
L50=$(python3.12 -c "import json;print(repr(json.load(open('$LAMJ'))['λ']['50']))")
L75=$(python3.12 -c "import json;print(repr(json.load(open('$LAMJ'))['λ']['75']))")
L90=$(python3.12 -c "import json;print(repr(json.load(open('$LAMJ'))['λ']['90']))")
ARMS="v310BEh_L0_s21:0 v310BEh_L25_s21:$L25 v310BEh_L50_s21:$L50 v310BEh_L75_s21:$L75 v310BEh_L90_s21:$L90 v310BEh_L1_s21:1 v310BEh_L50_Uabs_s21:$L50:abstain"
say "腕：$ARMS"
for A in $ARMS; do
  ARM=${A%%:*}; rest=${A#*:}; LAM=${rest%%:*}; U=""; [[ "$rest" == *:abstain ]] && U="--v39-u abstain"
  n_done=$(ls $OUT/$ARM/ledgers/cells/*/seed*.done 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$n_done" == "20" ]]; then say "腕 $ARM は済んでいる。飛ばす"; continue; fi
  warned=0
  while (( $(freegb) - 2 < 15 )); do
    if [[ $warned == 0 ]]; then
      say "★ 空き $(freegb) GB。腕 $ARM を始めると 15 GB を切りそうなので、腕の区切りで止める"
      ctl_line "- $(date '+%H:%M') ★ 空きが $(freegb) GB で、腕 $ARM（腕一つ約 2 GB）を始めると 15 GB を切りそうなので、腕の区切りで止めた。済んだ腕の台帳は消していない。空きが 17 GB 以上に戻れば、この腕から自動で続ける（5 分ごとに見る）。"
      warned=1
    fi
    sleep 300
  done
  [[ $warned == 1 ]] && ctl_line "- $(date '+%H:%M') 空きが $(freegb) GB に戻ったので、腕 $ARM から続けた。"
  say "腕 $ARM を始める（λ＝$LAM ${U}）"
  caffeinate -dimsu python3.12 tools/v3_run.py config/sweep_b2_hide_s21_2026-09-22.json $OUT/$ARM $FL --v39-price $LAM $U >> $OUT/${ARM}.log 2>&1
  rc=$?
  n_done=$(ls $OUT/$ARM/ledgers/cells/*/seed*.done 2>/dev/null | wc -l | tr -d ' ')
  say "腕 $ARM の走行が終わった rc=$rc 済み $n_done 本"
  python3.12 - "$OUT/$ARM" "$ARM" "$RES/mac/$ARM" "$TAGC" <<'P' >> "$LOG" 2>&1
import glob, gzip, hashlib, json, os, shutil, sys
root, arm, dest, tagc = sys.argv[1:5]
os.makedirs(dest, exist_ok=True)
rows = []
for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.jsonl.gz"))):
    if not os.path.exists(p[:-len(".jsonl.gz")] + ".done"):
        continue
    h = hashlib.sha256(); n = 0; header = None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == 0:
                header = json.loads(line); continue
            h.update(line.encode("utf-8")); n += 1
    rows.append({"arm": arm, "cell": os.path.basename(os.path.dirname(p)), "seed": int(os.path.basename(p)[4:7]),
                 "body_sha256": h.hexdigest(), "n_body": n, "ledger_bytes": os.path.getsize(p),
                 "code_commit": header.get("code_commit"), "run_seed": header.get("run_seed")})
with open(os.path.join(dest, "sha256.jsonl"), "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
shutil.copy(os.path.join(root, "flag.json"), os.path.join(dest, "flag.json"))
open(os.path.join(dest, "README.md"), "w", encoding="utf-8").write(
    f"# {arm}（マック）\n\n委任書「物の組で見分ける箇所の洗い出し・席の履歴の直し・直した B＋E の走らせ直し（2026-09-29 夜）」の 5。"
    f"（2026-09-30 の追加・置換指示）コード {os.environ.get('TAG')}（{tagc}）、足す旗 {os.environ.get('EXTRA')}。確かめ用の種 s21（種 21〜40）。\n\n★ 委任書により要約は書かない。ここにあるのは flag.json と台帳の本体の sha256 の一覧（{len(rows)} 本）だけ。"
    f"台帳と side はマックの ~/v310hprod/{arm} に全部残している。\n")
print("sha", arm, len(rows))
P
  (cd $W && python3.12 tools/results_push.py $RES mac $ARM "結果：mac の $ARM（s21）の flag.json・sha256 の一覧（要約なし）") >> "$LOG" 2>&1 \
    && say "腕 $ARM の flag.json・sha256 を上げた" || say "★ 腕 $ARM を上げられなかった"
  ctl_line "- $(date '+%H:%M') 腕 $ARM（λ＝$LAM${U:+、U 棄権}）：20 本のうち $n_done 本が走り終わった（rc＝$rc）。台帳は ~/v310hprod/$ARM。"
done
say "H21DONE"
ctl_line "- $(date '+%H:%M') 7 腕が終わった。"
