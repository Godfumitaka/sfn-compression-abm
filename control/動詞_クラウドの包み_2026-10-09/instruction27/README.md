# 指示27・28：動詞の二旗版、x86の40命令と100試行関門3本

指示28を2026-10-10T00:27:32.464033+09:00に受領、通常push370209f4b761a69b3c4abe4fd38801b6fb6958d3後に最優先で追加。現行plan.jsonは本番40命令（20本それぞれ子4/20）と関門3本（子0/4/20）。子20は最大21実模型なので開始は**保留：アストラの承認待ち**。現行同時8模型の条件を外さない。三本同時は最大27模型・CPU30枠・初回54GiBとなり、今の上限では開始できない。空いた芯だけで許可を推測しない。命令の用意と実際の開始を分け、このチャットからクラウド模型を開始しない。

指示27を2026-10-10T00:00:36.536859+09:00に受領、通常push6acb0eac6b5aed196f939bdaf28f3c7459f0ae5e後に準備。クラウドは作るだけで、このチャットから開始しない。Macの種1比較用一本はCPU6枠・実模型5枠・既存受付の全条件待ち。現行19/22四本は途中変更/停止しない。

土台 `e9ed84ae3ee6c458f392cd58cadf9fc030639900`、固定HEAD `6e4bcba94874a4f49c5a1bae11d385534504e2e5`、tree `b4dd25d03844e81bf09de3421f444081a50d5b35`。birth_workers.bundleは57369B、SHA256 `a077875be1b94a7eafbfb01b210e14e3b72f3ab49f73afa2698fe64b048018cd`、ref `HEAD`。新枝はpushせず承認済み報告枝のbundleで渡す。別専用cloneでHEAD/tree/clean/模型の全Git木が一致。模型起動0。値と復元証拠はversions.json/bundle_restore_checks.json。

模型を変えず、指示20の`--verb-snap-append-only on`と指示22の`--stage2-birth-workers 4`だけを指示23の旗なし19の原全旗へ追加。`--score-logp-e`無し、`--match-eps 0`、速度二旗無し。E0.01873710622997919とBは別価格。RunHeaderの出所タグは既存4dc、実際のHEADはspec/resultへ記録。観察器5ファイルは指示26の固定内容と同一バイトで、records複製を作らず原解凍内容のSHA256/bytes/linesと状態/RNG/全cache、100時間、501M1を記録する。

## 種1・L50の全argv

以下は引数を一つも省かないJSON配列。SOURCEは上の固定HEADの専用checkout、PACKAGEはこのinstruction27、OUTPUT_ROOTはこの係専用の新しい出力根。Macの実パス版はmac/spec.jsonのレビューコピー。Pythonは3.12。

```json
[
  "$PYTHON",
  "$PACKAGE/tools/production/measurement_driver.py",
  "$SOURCE",
  "$SOURCE/config/sweep_verb_hide1_s1_2026-10-04.json",
  "$OUTPUT_ROOT/19_seed001_flags_on/output",
  "--nohash",
  "--vt",
  "0.3842",
  "--extend-rule",
  "none",
  "--charge1",
  "d32",
  "--fast",
  "--no-public-history",
  "--dump-slot-history",
  "--fix2-full",
  "--fix-order2",
  "--proj-first",
  "--fill-norestate",
  "--no-charge2",
  "--own-evidence",
  "--v39",
  "--v39-budget",
  "inf",
  "--v39-decay",
  "actr",
  "--v310-be",
  "--hist-role",
  "--score-role",
  "--u-struct",
  "--relearn-init",
  "--tie-struct",
  "--amb-local",
  "--nsim",
  "0.7",
  "--ident-rho",
  "0.5",
  "--ident-argmax",
  "--ident-commons",
  "--cells",
  "f0.5000_th2.1000_first_order",
  "--dump-answers",
  "--dump-routing",
  "--answer-gap",
  "--strict-pc",
  "--e-price",
  "0.01873710622997919",
  "--v39-price",
  "0.00035129738499384776",
  "--workers",
  "1",
  "--seeds",
  "1",
  "--trial-count",
  "5000",
  "--no-compare",
  "--horizon",
  "5000",
  "--score-arg-order",
  "--sme2017",
  "--sme-call-seed",
  "--sme-tie-uniform",
  "--sme-intern-cache",
  "--sme-evict-trial-cache",
  "--verb-world",
  "--probe-world",
  "--verb-timing",
  "--v39-u",
  "global",
  "--match-cstar",
  "--match-cstar-e",
  "--h-dirichlet",
  "1",
  "--match-eps",
  "0",
  "--logp-eps",
  "0.01",
  "--birth-score",
  "seq",
  "--score-logp",
  "--attn-sme",
  "global",
  "--attn-position",
  "k2",
  "--attn-eta",
  "0.1",
  "--attn-allin",
  "--stage2",
  "on",
  "--stage2-loss",
  "top1",
  "--stage2-init",
  "virtual",
  "--stage2-scope",
  "all",
  "--stage2-birth-hu",
  "on",
  "--stage2-reuse",
  "off",
  "--verb-snap-append-only",
  "on",
  "--stage2-birth-workers",
  "4"
]
```

## クラウドの本番40命令（未開始）

plan.jsonのcommandsが現在の全argv。種・--v39-price・--stage2-birth-workersだけが変わり、他の全旗/順/値は同じ。子4版と子20版の二通りを各本に用意。全ready_to_start=false、cloud_start_authorized=false。plan_original_instruction27.jsonと子数を名前に含まない旧18草稿は履歴で、現在の指定には使わない。

|腕|種|B（--v39-price）|E（--e-price）|子4/20合計|
|---|---|---|---|---:|
|#19|1〜10|0.00035129738499384776|0.01873710622997919|20|
|#19L25|1〜5|0.00010926774617357411|0.01873710622997919|10|
|#19L90|1〜5|0.00699330963316462|0.01873710622997919|10|

本番の数は速いクラウド種1〜10で取る指定。Macの遅い19種1/2は旗なしの手本として保持し、Mac27の種1旗つき一本は同じ機械での全長比較用。子4は最大5模型・CPU6枠・初回10GiB、子20は最大21模型・CPU22枠・初回42GiB。実模型workerと出生fork子を一個体ずつ数え、監督/親/time/tracker/T/Zを稼働数へ足さない。ソースは問いの元順で加算し、Pool(min(子数,実問い数))のため予約は最大個体数とする。

記憶の候補は直列100実群最大RSS442302464B×1.5と最低2GiB/模型の大きい方×親子数。子4の先頭100実群最大1236533248Bは原標本から確認済み。子20/全5000/x86の実測は無く、保証上限にはしない。Claudeの子20は子4より約3倍という値は見積りであり、この包みの実測ではない。記憶・模型8本・physicalCPU−2・受付/swap10分/熱/容量条件を維持（memory_basis.json）。GNU timeとmeasurementのLinux maxrss原値はKiB、MacはB。原欄は変更せず単位を別に記す。

#19種1/2は同じx86の関門判定を正常pushした後の正式指定、種3〜10はさらにClaudeのM1確認と正式列を待つ。L25/L90は指示27の費用承認と正式列を待つ。他の報告の文だけで新しい委任にしない。子20の開始は模型上限の直接承認を待ち、子4も同じ機械のoff/4関門を満たしてから。どちらの旗つき結果も全長一致までは仮、動詞較正までλも仮。

## 同じx86の100試行関門（準備のみ）

plan.jsonのgate_commandsにgate100_birth0/4/20を用意。同じ6e4・V1 on・種1・L50・試験つきで出生の子数だけが違う。gate/measurement_driver.pyは固定6ca7af8f64dbc9599ac256f84d15930d37d102aeff56bf2e1f29b861c49217f4と同じバイト。設定/horizon/len5000を保ち先頭100だけで正常終了、完了100/full_5000_completed=false、48問48回答・fingerprint1・注意/問い回数の保存復元を要求。これは全5000完了ではない。

関門0は2GiB/CPU2枠/模型1、4は10GiB/CPU6枠/模型5、20は42GiB/CPU22枠/模型21。三本同時の指定は現行8模型と両立しないので、特に20は開始保留。受付や関門を省かず、開始の直接判断を待つ。このチャットから三本/比較を実行しない。

gate_compare.pyは指示26の承認済み(a)実在名集合が一致する全ファイル、(b)manifestの全研究者辞書の原字節、(c)原time/resultをoffと4、offと20で比べる。試験行除外0、実在ファイル除外0。ambig.csvが双方で原入口から出ない場合だけabsent_on_bothに記す。回答の原行数48、完了印、同じ機械・source・全旗を先に確認。第二段既定TIMEと非模型verbtiming実時間だけ比較用に扱い、原本を保持。先行不一致は後の比較で上書きしない。比だけで旗の性能を断定しない。

```sh
"$VERB_PY" "$VERB_PACKAGE/prepare_case.py" --source "$VERB_SOURCE" --output-root "$VERB_ROOT" --label gate100_birth0
"$VERB_PY" "$VERB_PACKAGE/prepare_case.py" --source "$VERB_SOURCE" --output-root "$VERB_ROOT" --label gate100_birth4
"$VERB_PY" "$VERB_PACKAGE/prepare_case.py" --source "$VERB_SOURCE" --output-root "$VERB_ROOT" --label gate100_birth20
```

将来、正常100の原三本がそろった機械でだけ以下を一度受付する。開始承認や完了をこの命令例で作ったことにしない。結果が違えば件数・欄・例と原ログを報告し旗つき結果を使わない。

```sh
python ~/jobs/jobs.py run --wait --owner 動詞28-off4 --mem 0.3 --disk-path "$VERB_COMPARE" -- python "$VERB_PACKAGE/gate_compare.py" "$VERB_ROOT/gate100_birth0" "$VERB_ROOT/gate100_birth4" "$VERB_COMPARE/gate_off_vs_4.json"
python ~/jobs/jobs.py run --wait --owner 動詞28-off20 --mem 0.3 --disk-path "$VERB_COMPARE" -- python "$VERB_PACKAGE/gate_compare.py" "$VERB_ROOT/gate100_birth0" "$VERB_ROOT/gate100_birth20" "$VERB_COMPARE/gate_off_vs_20.json"
```

## x86 Ubuntu・Python3.12での復元と準備だけ

既存の受付のある機械を使う。新しい専用場所へ取り出す。元checkoutは変えない。模型は標準ライブラリ、固定requirements.txtはpytestだけ（走行には必須でない）。復元にGitとPython3.12、走行には既存jobs.pyとGNU timeを使う。

```sh
VERB_PACKAGE=/srv/verb/report-results/control/動詞_クラウドの包み_2026-10-09/instruction27
VERB_BASE=/srv/verb/base_repository
VERB_SOURCE=/srv/verb/source_instruction27
VERB_ROOT=/srv/verb/production_instruction27
VERB_PY=/srv/verb/env/bin/python
"$VERB_PY" "$VERB_PACKAGE/restore_bundle.py" --base-repository "$VERB_BASE" --destination "$VERB_SOURCE"
"$VERB_PY" "$VERB_PACKAGE/prepare_case.py" --source "$VERB_SOURCE" --output-root "$VERB_ROOT" --label 19_seed001_birth4
```

prepare_caseは実パスのspecと受付command草稿を一つ作るだけで、模型は起動しない。40本と関門3本のlabelはplan.jsonとcommand_drafts/を使う。設定5000/horizon5000を保つ。実版・全argv・価格・観察SHAをspecへ残す。run_registered.pyはready_to_start、正常pushの列取得・spec SHA・関門証拠・固定SHA・開始期限・x86/Python3.12・最新の既存受付clearanceを先に要求する。

将来の受付commandは各case/admission_command.draft.json。形式は`python ~/jobs/jobs.py run --wait --owner <本> --mem 10.0 --disk-path <実出力> -- python run_registered.py <case> --clearance <既存受付の確認>`。clearanceはspec_sha256/machine_boot_sha256/checked_epoch(60秒以内)/memory_reservation_gb/memory_admission_ok/swap_stable_10min/thermal_ok/warning=false/physical_cpu_count/cpu_budget=physical−2が必要。列取得証拠queue_claim_published.jsonはnormal_push_succeeded/40桁commit/case_label/machine=x86/spec_sha256と、19種1/2ならcloud_pilot_authorized、種3〜10ならClaude_M1_confirmed、L25/L90ならAstra_cost_approvedを実証に基づき記す。本番はcloud_gate_comparison_path/cloud_gate_comparison_sha256/cloud_gate_published_commit（40桁）も必要で、実passed・同じ機械・同source・同旗（種/Bだけの変更）を要求。この包みは承認/原完了/clearanceを推測で作らない。

Mac用wait_for_start.pyは自分の既存22二本の原正常終了を読むだけで待ち、変化のない待ちに全Macps/commitを増やさない。原終了後、最新fetch/merge、未受領又は後続指示・列の先行行・取得済み行を先に確認し、実枠を開始直前に一度確認する。満たせば19p行を取得して通常push後に同じjobs10GiBへ一度通す。開始後の監督は自分の群/原警告を読み取り、本番の常駐停止/再開機構を入れない。

## 500ごとの読み合わせと全長の関門

同じMacの原19種1の古いrecordsコピーは拡張子.gzでも非圧縮。checkpoint_digest.pyはこの原コピーをそのまま読み、新側の元gzipの確定byte数までを読んで原SHA/行数/byte数を再確認する。後続の行は対象に混ぜず、原ファイルや欄を編集・削除・丸め・再配列しない。第二段の既定TIME値だけ既存定義で比較用に扱う。実在の名前集合・全ファイル・試験行も必須。状態/RNG/cache_sme/cache_raw/cache_posthoc_p10の全字節と禁止参照0を比較。新二旗はP10旗ではないため、guardがないNoneも元設定どおり両側で照合する。

比較は既存受付0.3GiB（1MiBのstream、実測があれば合わせる）とCPU枠、実出力先で一回だけ。両側のconfirmed後に各境の別JSONへ出し、件数・最初の差・欄のファイル・例を残す。例外は不合格/未検証として原ログを報告し、同じ比較を重ねない。先行不一致を後の境で上書きしない。

```sh
python ~/jobs/jobs.py run --wait --owner 動詞27-境500 --mem 0.3 --disk-path "$COMPARISON_ROOT" -- python "$VERB_PACKAGE/checkpoint_digest.py" "$OFF_CASE" "$ON_CASE" 500 "$COMPARISON_ROOT/checkpoint_0500.json"
```

5000境のhashだけでは全長合格にしない。両原終了0・原完了印・100時間50行・48問×50時点の2400回答と保存復元を確認後、別のfinal比較で閉じた全出力とmanifest研究者辞書（既存の同じ関数、原字節。stage2 TIMEと非模型verbtiming実時間だけ）も比較する。全長の関門まで旗について仮、動詞較正までλについて仮。一件不一致なら旗つきの結果を使わず直ちに報告する。走行中を勝手に止めない。

```sh
python ~/jobs/jobs.py run --wait --owner 動詞27-全長 --mem 0.3 --disk-path "$COMPARISON_ROOT" -- python "$VERB_PACKAGE/checkpoint_digest.py" "$OFF_CASE" "$ON_CASE" 5000 "$COMPARISON_ROOT/final_closed_outputs.json" --final
```

原19の501時点のM1は0始まり200〜500の301行を既存台本で報告し、種3〜10の判断はClaudeが行う。未記録の500/501や区間時間を総時間から補わない。原19実500recordsの55倍と実空き−30GBの容量見込みは指示26の3として待つ。

非模型18検査とbundle復元がpassed（preparation_checks.json、preparation_tests_attempt4.log）。前段11/13/17検査の原ログも保持。これは新しい本の実関門や全5000完了ではない。旧100関門・分類・集計を再投入せず、指示26の承認済み比較20/22をevidence/へ同梱。期限2026-10-13 09:00JST以降は新規開始なし、開始済みを期限だけで止めない。通知は変化・完了・失敗・必要な判断のときだけ。


## クラウド種1/2の確定501M1を読む

m1_at501.pyは同じsourceの種1/2の実comparison_checkpoints/m1_at_trial500.jsonだけを読み、SHAを付けて保存する。既存観察器の0始まり200〜500の301確定行・定義1個以下の割合/基準を保持。適用される元M1にapplicable欄が無いことは元形式で、Falseの適用外は通さない。501未記録を補わず、モデル・乱数を起動しない。Claudeの確認を代行せず種3〜10開始はFalseのまま。1000/2000/3000/4000/4999の原見張りにも対応する。

```sh
python ~/jobs/jobs.py run --wait --owner 動詞28-M1 --mem 0.3 --disk-path "$VERB_COMPARE" -- python "$VERB_PACKAGE/m1_at501.py" "$VERB_ROOT/19_seed001_birth4" "$VERB_ROOT/19_seed002_birth4" "$VERB_COMPARE/cloud_M1_at501.json"
```

子20を選ぶ場合も同じ原M1の定義で、caseの名前だけ実際の選択に合わせる。同じ出力を再集計しない。基準に当たっても稼働中を自動停止せず、原数を報告してClaude/アストラの判断を待つ。模型が出した成績の良し悪しは書かない。
