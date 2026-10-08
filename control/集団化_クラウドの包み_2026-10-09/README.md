# 八体の集団化：クラウドの関門の包み（指示7）

デスクトップの走行の係が実行する包み。Codex3はAWSを操作していない。候補は origin の `codex/coll8-allin-2026-10-08`、固定 `c4cfed12a3944071951775b2c9373ca27705fb25`。旧い集団化は `c55b8c1a62b04002413686b0405bc1960fa8d6b9`、準備版の独立単独は `e9ed84ae3ee6c458f392cd58cadf9fc030639900`。部品・台本の検査と、実走行の関門は別。**この包みを作った時点ではクラウドの実走行0、八体の関門・測定は未合格、本番は未開始。**

## 結果の前に固定した規則

比較する二本を同じ機械で走らせる。機械IDと起動IDのSHA256を各開始記録に入れ、比較時に一致を必須とする。マックの旧出力をクラウドの新出力と比べない。マックの組とクラウドの組のうち先に両側が揃った組をCodex3が判定する。マックのPID44480は止めず、再起動もしない。N5案の「一意の引き継ぎができるまでクラウドの組を開始しない」は、今回の指示7で置き換えられた。

新しい不一致・必須検査の失敗は `gates/gate-*.json` と `STOP.json` に残す。直したり後続を始めたりしない。保存済みの出力・比較を上書きしない。単に未発生・未完走の関門も合格にしない。削除、走行中の本番停止、種21〜40、受付・関門の解除の四項目は「保留：アストラの承認待ち」。開始後に版・旗を変えない。四体は今回の対象外。

期限は **2026-10-11 09:00 JST（00:00 UTC）**。期限後の新しい受付・模型開始を拒む。既に走行中の模型は自然終了まで保つ。マックの既存44480は旧期限を読み込み済みなので、ファイル編集で延長したとは扱わない。

## 実行場所と準備

指示7の実行場所は us-east-1、c7a/m7a/r7a の8xlarge、Ubuntu、Python3.12。係が既存の受付 `jobs.py`・24GB予算・模型8本上限・永続出力先を確認する。八体は直列でも生存する8本を数える。直列は計算上限1・待機7、並列は計算上限8。出力先の空き20GiB以上、熱・性能の警告なし。他の模型がいる時はこの包みは開始しない。受付の設定を変える命令は含めていない。

以下はクラウド上で打つ。`COLL_BASE` は係が確認した永続ディスク上の新しい専用場所、`RESULTS` は係自身の報告用clone、`JOBS` は係が確認した既存の受付。資格情報・鍵・合い言葉はこの包みに書かない。

```bash
export COLL_BASE=/mnt/coll_gate_20261009
export RESULTS=/mnt/results-coll-gate
export JOBS="$HOME/jobs/jobs.py"
export PY=python3.12
export PKG="$RESULTS/control/集団化_クラウドの包み_2026-10-09"
export CANDIDATE="$COLL_BASE/source-c4"
export BASELINE="$COLL_BASE/source-c55"
export PREPARATION="$COLL_BASE/source-e9"
export RUN="$COLL_BASE/run-same-host"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0

test -f "$JOBS"
test ! -e "$RUN"
mkdir -p "$COLL_BASE"
mkdir "$RUN"
"$PY" -c 'import sys,pytest; assert sys.version_info[:2]==(3,12); print(sys.version,pytest.__version__)'
"$PY" "$JOBS" status
df -h "$COLL_BASE"
cd "$PKG"
sha256sum -c SHA256SUMS
```

結果の枝の最新の通常pushを取り込み、上の包みが存在する状態で使う。報告用cloneにローカル変更があれば保全してfetch/rebaseし、衝突は解決せず止める。他係のcloneを使い回さない。Python3.12にpytestがなければ、小例を実行できる環境を係が用意してから続ける。

模型は新しい三cloneへ、必要なコード・許可された共通の世界定義だけを展開する。保護対象 `abm/` と `tools/v39.py` は候補とe9で全バイト同じであることを検査する。種別の結果・種21〜40のファイルは展開・読出ししない。

```bash
checkout_code () {
  git clone --filter=blob:none --no-checkout https://github.com/Godfumitaka/sfn-compression-abm.git "$1" || return
  git -C "$1" sparse-checkout set --no-cone '/abm/' '/tools/' '/tests/' '/*.py' '/AGENTS.md' '/SPEC.md' '/pyproject.toml' || return
  git -C "$1" fetch origin "$2" || return
  git -C "$1" checkout --detach "$2"
}
checkout_code "$CANDIDATE" c4cfed12a3944071951775b2c9373ca27705fb25
checkout_code "$BASELINE" codex/coll8-baseline-2026-10-09
test "$(git -C "$BASELINE" rev-parse HEAD)" = c55b8c1a62b04002413686b0405bc1960fa8d6b9
checkout_code "$PREPARATION" e9ed84ae3ee6c458f392cd58cadf9fc030639900
"$PY" "$PKG/check_package.py" --candidate "$CANDIDATE" --baseline "$BASELINE" --preparation "$PREPARATION" --fixtures "$RUN/package-checks"
```

`configs/shop.json` は既存の共通設定の同一コピー（SHA256 `ef385e65c6fd42a3de3b239127e7da15d70e5d9b897a5c29d1f810cc92cbcbaf`）。一体比較の二設定はaxes.fだけを0.1/0.9にする。両側は同じ設定を使う。すべてCLIで世界の種/集団種を1本に限定し、OFF/小関門は1、本番は1〜5。個体の世界の乱数種は既存規則「集団種＋1000×個体番号」。本番の10集団を同時投入せず、1集団8体ずつ進める。

## 各本の資源の見込み

|名前|計算の芯上限／生存する模型|試行|メモリの見込み・受付|
|---|---:|---:|---|
|小例 `components.py`|1／世界の走行0|小例|1GB。既存の41検査は約1秒、追加の公開材料・誕生HU・停止検査も小例。クラウド実時間は未測定|
|off2_baseline200 / off2_candidate200|1／2|各200|各1GB。旧い二体のRSS合計418,381,824 bytesに余裕を加えた既存の予約|
|off8_baseline200 / off8_candidate200|1／8|各200|各2GB。旧い八体200のRSS合計約1.011GBを根拠にした既存の予約|
|off8_parallel200|8／8|200|2GB案。直列と同じ模型の総量でも並列の山は未測定。2GBを超える警告なら後続を止める|
|on1_pilot20|1／1|20|初回だけ係が小さい観測の予約を決め、bootstrap根拠を記す。上流ON20のRSS62,898,176 bytesは参考。移植後200・全長の安全上限には使わない|
|on1_f0.1/0.9 のcollective/independent|1／1|各200|予約は空欄。pilotの実測を読んで余裕と条件差を明記し、1.2×観測RSS以上・24GB以内にする。20→200の成長は未保証|
|on2_receive200 / on2_replay200|1／2|各200|予約は空欄。一体200の実測を根拠に、二体の合計と余裕を記す|
|on8_measure300|8／8|300|予約は空欄。受信二体の実測から八体の条件差・合計の余裕を記す。前の条件付き25GB外挿を実測予約にしない|
|production_f0.1/0.9_seed1〜5|8／8|各1740|予約・λとも空欄。八体300の実測だけで1740の安全上限とはせず、後半の成長と出力を係が確認。24GB内が確認できなければ保留|

RSSは親子合計を1秒間隔で採る。真の山を取り逃す可能性がある。GNU timeの実時間・user/sys CPU秒・最大RSSも `time.log` に保存する。枠の「芯×実時間」はCPU実測ではない。新しいC*の控えは旧SMEの破棄の対象へ勝手に追加しない。出力の安全上限は未測定なので、空き20GiBを開始時と走行中に検査する。

## 受付の共通命令

`clearance.py` は係が受付表と警告を確認した記録を作る。`--existing-gb` はその時の実際の予約合計。以下の `EXISTING_GB=0` は他予約0を実確認した専用機の例で、未確認なら使わない。新しい確認は10分以内だけ有効で、受付後にもCPU・空き・期限・版・重複を確認する。既存出力を消して取り直さない。

```bash
export EXISTING_GB=0
run_one () {
  name="$1"; source_dir="$2"; mem_gb="$3"; measured_resource="$4"; memory_note="$5"
  record="$RUN/clearance-$name.json"
  if [ -n "$measured_resource" ]; then
    "$PY" "$PKG/clearance.py" "$name" --root "$RUN" --source "$source_dir" --jobs "$JOBS" --mem "$mem_gb" --existing-gb "$EXISTING_GB" --resource-file "$measured_resource" --memory-note "$memory_note" --no-resource-warning --record "$record" || return
  else
    "$PY" "$PKG/clearance.py" "$name" --root "$RUN" --source "$source_dir" --jobs "$JOBS" --mem "$mem_gb" --existing-gb "$EXISTING_GB" --memory-note "$memory_note" --no-resource-warning --record "$record" || return
  fi
  "$PY" "$PKG/run.py" run "$name" --source "$source_dir" --root "$RUN" --jobs "$JOBS" --mem "$mem_gb" --clearance "$record"
}
```

各命令が0で終わったことを確認して次へ進む。`STOP.json` があれば以降は開始しない。走行中の模型には信号を送らず、自然終了後に失敗・資源警告を記録する。熱・性能の警告を認めたら新しい本を始めない。

## 関門の全部の命令

**1. 小例：状態の隔離、公開材料と誕生、墓石と未知名停止。** 入れ子とpendingの同一性、SME/C*の控えと乱数、診断による実課題回数・実開示名集合の非増加、複数報告、世界／報告の背景の分離、仮Fと実Fの不一致停止、HUの二段の仮問い、C*の確率枠、墓石の再参照停止、未知名の停止を検査する。固定版の11検査ファイルと外部の停止2例をそのまま使う。検査ファイルと命令全量は `components.py`、生の成否はstdoutに保存する。

```bash
"$PY" "$PKG/components.py" run --source "$CANDIDATE" --root "$RUN" --jobs "$JOBS"
```

**2. OFFの全バイト比較（二体受信、八体q0）。** クラウドでは旧版側も新しく同じ機械で用意する。マックで保存済みの旧二体・旧八体や新二体は走り直さない。

```bash
run_one off2_baseline200 "$BASELINE" 1 "" "既存の二体OFFの実測と1GB予約"
run_one off2_candidate200 "$CANDIDATE" 1 "" "同じOFF・世界・種・旗、三メタデータ検査"
"$PY" "$PKG/compare.py" "$RUN" off2
run_one off8_baseline200 "$BASELINE" 2 "" "既存の八体OFFの実測と2GB予約"
run_one off8_candidate200 "$CANDIDATE" 2 "" "同じOFF・世界・種・旗、三メタデータ検査"
"$PY" "$PKG/compare.py" "$RUN" off8
```

OFF2はf0.1/0.9、q0.2/m0.3/recvA。OFF8はf0.1×4/0.9×4、q0/m0。いずれも世界2・集団種1・200・b_n8・直列・audit・試験100・intern/evict/墓石。新しいC*/logP/注意/第二段はOFF。全argvは `specs/off*.json` に固定した。

**3. 直列と体ごとの並列の全バイト一致。** 同じc4、OFF8のspecから `--v311c-serial` だけを外す。並列の比較も時計・順の違いを理由に模型値を除かない。

```bash
run_one off8_parallel200 "$CANDIDATE" 2 "" "OFF8の直列との比較。並列のRSS合計は実測で記録"
"$PY" "$PKG/compare.py" "$RUN" off8-parallel
```

**4. 一体ONとe9の独立単独。** f0.1と0.9をそれぞれ200。集団一体はq0/no-tags、名札費用を足さない。C*/C*E・logP・H Dirichlet1・birth seq・注意global/k2/eta0.1/allin・stage2 on/top1/virtual/all・birthHU on・logp-eps0.01/match-eps0。cf-valueとlogP_Eは両側とも付けない。後の高速化はOFF。

```bash
# 最初の20だけ、係が確認した予算内で根拠つきの初回予約を設定する。
export PILOT_MEM=1
run_one on1_pilot20 "$CANDIDATE" "$PILOT_MEM" "" "初回20だけ。上流ON20のRSS約63MBを参考、移植後は未測定・後続予約へ直接流用しない"
cat "$RUN/evidence/on1_pilot20/resource.json"

# 以下の空欄は実測を確認して係が記入する。空欄のまま受付しない。
export ON1_MEM=""
run_one on1_f0.1_collective200 "$CANDIDATE" "${ON1_MEM:?pilotの実測と条件差から記入}" "$RUN/evidence/on1_pilot20/resource.json" "一体200。pilotからの成長と余裕を確認"
run_one on1_f0.1_independent200 "$PREPARATION" "$ON1_MEM" "$RUN/evidence/on1_f0.1_collective200/resource.json" "同じf0.1・200の一体実測と余裕"
"$PY" "$PKG/compare.py" "$RUN" on1-f0.1
run_one on1_f0.9_collective200 "$CANDIDATE" "$ON1_MEM" "$RUN/evidence/on1_f0.1_collective200/resource.json" "f0.9の条件差と余裕を確認"
run_one on1_f0.9_independent200 "$PREPARATION" "$ON1_MEM" "$RUN/evidence/on1_f0.9_collective200/resource.json" "同じf0.9・200の一体実測と余裕"
"$PY" "$PKG/compare.py" "$RUN" on1-f0.9
```

**5. 受信ONと再生、実状態・実誕生の確認。** 二体f0.1/0.9・q0.2/m0.3・recvA・200、世界後と受信後を別に保存。再生は前の個体別sideを読む。追加状態もnative再生で照合し、全部の比較を別名へ保存する。実報告誕生と世界誕生、HUの記録がなければ合格にせず停止。小例で作った合格で代用しない。

```bash
export ON2_MEM=""
run_one on2_receive200 "$CANDIDATE" "${ON2_MEM:?一体200の実測から二体の予約を記入}" "$RUN/evidence/on1_f0.9_collective200/resource.json" "二体200の合計と余裕、複数受信の条件差を確認"
run_one on2_replay200 "$CANDIDATE" "$ON2_MEM" "$RUN/evidence/on2_receive200/resource.json" "同じ二体の受信の実測と余裕"
"$PY" "$PKG/compare.py" "$RUN" receive-replay
```

**6. 八体300の短い測定。** 上記すべての合格後。auditなし、試験100と必須の保存復元は維持。体ごとの並列、世界2・種1・f0.1×4/0.9×4・q0.2/m0.1/recvA。四体の測定を開始条件へ加えない。

```bash
export ON8_MEM=""
run_one on8_measure300 "$CANDIDATE" "${ON8_MEM:?二体200の実測から八体の予約を記入}" "$RUN/evidence/on2_receive200/resource.json" "八体の合計・300試行・並列の山と余裕。24GB内を確認"
"$PY" "$PKG/measurement.py" "$RUN"
```

## 比べる道具と全ファイル

`compare.py` は固定した上記六組だけを比較する。各側の完走・resource警告0・固定版を先に確認する。doneおよび通信集計の **code_commit＝固定spec、ledger_bytes＝実圧縮サイズ、見出しの差＝code_commitだけ**（同版の組では差0）を必須とする。誤った版・サイズ・agent_idsの三例が拒まれることも各組で検査する。旧い不合格 `gate-off_recv2_200.json` と `STOP-off-recv2.json` は元の場所で保全する。

|対象|比較|
|---|---|
|`ledgers/cells/*/seed*.jsonl.gz`|見出しの必須検査後、台帳本体の解凍した全生バイト。全200件・trial順・f_realizedを別検査|
|`ledgers/cells/*/*.done`|版・サイズの実体照合後、時計とその検査済みメタデータ以外の全欄|
|`side/**/*`|全ファイルの種類・全生バイト。cfvalue.sec_trialだけ除く。保存SME状態・予測・同点の乱数を含む|
|`attention/**/*`|全ファイル・全値・全順序|
|`stage2/**/*`|全値・順序。通常jsonlのseconds/wrapper_secondsと終了summary.secondsだけ除く。initialの公開材料・問い・HU値は除かない|
|`evictions/**/*`|捨てた完全な鍵と墓石の全記録。墓石enabled・hit0・最後の試行を必須検査|
|`comm/run001.jsonl`|終了時計を持つsummary行以外の全事象の生バイト|
|`comm/run001.summary.json`|全模型欄。各agentを実体照合した後、時計・版・サイズを除く。再生のreplayedは各側の真偽を検査後だけ正規化|
|`comm/run001.jsonl.state.jsonl`, `run001.lineage.jsonl`|状態指紋と系譜の全生バイト|
|外部保存 `agent*.final-sme.jsonl.gz`, `model-rng.jsonl`, `rng.jsonl`, `cstar-final.json`|SMEの最終控え全量、全試行の乱数、C*の専用ENGINEの完全なsnapshot。両側の存在も検査。C*がOFFで未導入なら両側とも無い|
|一体ONの追加状態|e9は外部でc4と同一の読み取り符号を使い、c4のnative collective-runtimeのpre/post全量と比較。q0/no-tagsの重複collective_phaseは、空のdeliveries・世界/受信各200・全stateがnative postと同じことを検査してから、独立にない写しだけを除く|
|`flag.json`, `manifest.jsonl`, `runtime.json`|模型の値の全バイト表には含めず、全argv・設定SHA・版・完走・開始証拠として別に保存。模型の記録の値を取り除く口実にしない|

## 本番10集団（列#20）の命令

実行はClaudeがL50_refを記入し、八体のすべての関門と受付・出力・CPUの条件を確認し、最新の列#20に版・旗・出力先を指定して未着手にしてから。係はfetch/rebaseして最新の列を取り、走行中・クラウド・開始時刻を書き、通常pushの成功を確認する。競合なら取り込み直し、同じ行を重複取得しない。以下のspecのq0.2/m0.1/recvA・group00001111はまだ列の確定前の案。列で別の値が指定されたら、先に包みの固定版・spec・SHA・必要な再関門を更新し、黙ってruntimeを変えない。

```bash
export L50_ref=""  # Claudeがお店の較正結果を記入する
export PRODUCTION_MEM=""  # 八体の実測と全長の成長を確認した予約
for f in 0.1 0.9; do
  for seed in 1 2 3 4 5; do
    name="production_f${f}_seed${seed}"
    record="$RUN/clearance-$name.json"
    "$PY" "$PKG/clearance.py" "$name" --root "$RUN" --source "$CANDIDATE" --jobs "$JOBS" --mem "${PRODUCTION_MEM:?実測予約を記入}" --existing-gb "$EXISTING_GB" --resource-file "$RUN/evidence/on8_measure300/resource.json" --memory-note "八体1740の成長と出力を確認、較正L50_ref、全関門・列#20取得後" --no-resource-warning --record "$record" || break 2
    "$PY" "$PKG/run.py" run "$name" --source "$CANDIDATE" --root "$RUN" --jobs "$JOBS" --mem "$PRODUCTION_MEM" --clearance "$record" --l50-ref "${L50_ref:?ClaudeがL50_refを記入}" --queue-proof "$RUN/queue-${name}.json" || break 2
  done
done
```

`queue-<name>.json` は最新の通常push済み取得の証拠で、係が以下の欄を実記録から作る。架空のpassed/取得証拠を台本に作らせない。空欄なら拒否する。`spec_sha256` は `run.py plan <name>` の値、`model_argv` はその固定specの全量。

```json
{"row":"20","commit":"c4cfed12a3944071951775b2c9373ca27705fb25",
 "status":"走行中（クラウド・実際の開始時刻）","normal_push_confirmed":true,
 "results_commit":"通常push済みの40桁commit","lambda_source":"L50_ref","L50_ref":null,
 "approved_specs":{"production_f0.1_seed1":"固定specのSHA256"},
 "model_argv":[],"output":"実際のRUN/outputs/production_f0.1_seed1"}
```

## S3の原出力とGitHubへ戻す証拠

S3・GitHubへの操作もデスクトップの係が行う。永続のバケット/接頭辞を実確認してから、原出力・各開始/観測・比較をS3へ置く。削除同期を使わず、上書きしない新しい接頭辞にする。GitHubの `ataru-0608/cloud_runs/coll_gate_<名前>/` にはtime.log、SHA表、比較の判定、起動・版・host・資源の証拠を保存する。原出力はGitHubに入れない。比較で不合格なら不合格とSTOPも返す。

```bash
export S3_PREFIX=""  # 係が実確認した新しいs3://.../coll_gate_<名前>
export GATE_NAME=coll8_c4_20261009
"$PY" "$PKG/export.py" "$RUN" "$RESULTS/ataru-0608/cloud_runs/coll_gate_${GATE_NAME}"
aws s3 sync "$RUN/" "${S3_PREFIX:?確認済みの永続接頭辞を記入}/"
```

係自身の報告用cloneで差分を確認して必要な証拠だけcommitし、push直前にもfetch/rebaseして通常pushする。衝突は解決せず止め、強制pushを使わない。S3の所在地と完了した組の名前を報告へ記し、Codex3が戻った記録を読む。模型値の良し悪しを判定しない。

## 包みの準備検査と限界

`check_package.py` は23specの旗・種・設定SHA・三つの固定版・保護24ファイル・CLIの既存旗を確認し、合成した記録で比較の一致／一バイト不一致／異機械／誤版／誤サイズ／誤見出しを検査する。これは台本の検査であり、実模型の関門の合格ではない。native模型の独自修正は0。新しい本番・クラウド資源の開始は0。未実測予約・L50_ref・列取得は空欄のまま。

作成時の準備検査は48件合格、追加の墓石・未知名の停止の小例は2件合格。保護24ファイルは候補とe9で一致した。記録は `preparation/` に保存した。合成の比較やローカルの小例をクラウドの実関門の合格へ読み替えない。ONの予約・L50_ref・列#20の取得は未確定のまま。

旧版c55がoriginから取れないとの実行係の報告を確認し、2026-10-09T02:42:33.166986+09:00までに保全した同じcommitを `codex/coll8-baseline-2026-10-09` へ通常pushした。commit `c55b8c1a62b04002413686b0405bc1960fa8d6b9`、tree `abfe2c67a4be1908fdcf1f80fd0be9a68e978fed`。旧い作業場所・枝・出力・specの版は変えていない。取得する枝だけを明示し、SHAの照合を必須にした。
