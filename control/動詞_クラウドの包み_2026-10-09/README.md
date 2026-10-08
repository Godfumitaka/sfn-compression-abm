# 指示9：動詞のクラウド用の包み

2026-10-09に準備。学習走行はこの包みの作成時点では未実行。Macの監督77418・retry2を止めず、計算用40e87b2・全旗・測定λ・観察driverも変えていない。継続確認と新規開始の期限は2026-10-11 09:00 JST。開始済みの処理を期限で止めない。

## 固定した版

| 用途 | 専用ローカル枝 | 包みのコミット | 模型の出所・観察入口 |
|---|---|---|---|
| on100二本と300 | codex/verb-cloud-package-2026-10-09 | 74d88e66f0ebcfcdaae007d80ad5df5514e465b7 | 模型40e87b2e1fbd8348141dd447ac49c3aaadd7d914。観察SHA6ca7af8f64dbc9599ac256f84d15930d37d102aeff56bf2e1f29b861c49217f4 |
| 速度off/on200の準備 | codex/verb-stage2-speed-2026-10-09 | 412b9ce8ff6274d6b1da548ed4b1509f2bbf1772 | 40eへ4ceadf63の二旗を移植。観察SHA235a580d6f43bfffb88bc332a8eb4dcba85b7971e1617ee364570fb41435816d |

指示10（2026-10-09 01:51）により、新しい枝はoriginへpushしない。差分とGit bundleを承認済みresults-2026-09-27へ置き、クラウドへ渡す。指示9の1の新枝pushの要求はこの方式へ替わり、追加の直接承認を求めない。bundleの土台は承認済みoriginの`e9ed84ae3ee6c458f392cd58cadf9fc030639900`。旧作業枝や他の係のcheckoutへ適用しない。

送信用の枝はCodexの公開用作者情報で作り、模型・観察・包みのファイルの木が、検査した専用ローカル版と全く同じであることを確認した。Macの40eの履歴や稼働中のcheckoutを書き換えていない。`source_manifest.json`が模型の全ファイルのGit blobとmodeを照合し、包みの付加ファイルだけを別にする。RunHeaderの出所タグ4dc6a05はMacと同じ。実際の包みのHEADと模型の出所40eはruntime・完了記録へ別々に残す。

`versions.json`、各フォルダの`files.json`にSHA256・サイズ・固定コミットを置いた。`source.patch`は同じ版の差分、`source.bundle`は復元可能なGitの包み。鍵・合い言葉は含めない。



| bundle | 取り出し後のHEAD | tree hash | bundle SHA256 | バイト |
|---|---|---|---|---|
| cloud | `74d88e66f0ebcfcdaae007d80ad5df5514e465b7` | `47f03f03cc26e40793dcce90cdc8c62d673ed9b9` | `a2c086a98da0fa2624cf14b327e13d59725d9a91f5c93659ca85a18a87e34ca5` | 78533 |
| speed200 | `412b9ce8ff6274d6b1da548ed4b1509f2bbf1772` | `07f9428b143b9fe82b89e918b9b6921d4ea03b6f` | `83aec21dad227ad5f0b9ec0c82f92544b8c9c2e74e58c53f352e45137a62eb24` | 93716 |

両bundleとも50MB以下。50MBを超える新しいbundleは送らず報告して待つ。取り出し後、HEADとtree hashの両方を上表と照合してから走行する。

## Ubuntu・Python3.12での準備

走行係が用意済みのUbuntu機械で行う。下の`/srv/verb`は、この係専用の書き込み可能な場所にする。報告用checkoutは最新をfetch・mergeした`results-2026-09-27`とする。出力先にはユーザー名や鍵を含めず、time.logを原本で共有できる場所を使う。

```sh
VERB_PACKAGE=/srv/verb/report-results/control/動詞_クラウドの包み_2026-10-09
VERB_SOURCE=/srv/verb/source
VERB_OUTPUT_ROOT=/srv/verb/measurements_20261009
VERB_JOBS=/srv/jobs/jobs.py
VERB_CLEARANCE_ROOT=/srv/verb/resource_clearance

git clone --no-checkout https://github.com/Godfumitaka/sfn-compression-abm.git "$VERB_SOURCE"
git -C "$VERB_SOURCE" checkout --detach e9ed84ae3ee6c458f392cd58cadf9fc030639900
test "$(sha256sum "$VERB_PACKAGE/cloud/source.bundle" | cut -d " " -f 1)" = a2c086a98da0fa2624cf14b327e13d59725d9a91f5c93659ca85a18a87e34ca5
git -C "$VERB_SOURCE" bundle verify "$VERB_PACKAGE/cloud/source.bundle"
git -C "$VERB_SOURCE" fetch --no-tags "$VERB_PACKAGE/cloud/source.bundle" refs/heads/codex/verb-cloud-package-2026-10-09
git -C "$VERB_SOURCE" checkout -b codex/verb-cloud-package-2026-10-09 74d88e66f0ebcfcdaae007d80ad5df5514e465b7
test "$(git -C "$VERB_SOURCE" rev-parse HEAD)" = 74d88e66f0ebcfcdaae007d80ad5df5514e465b7
test "$(git -C "$VERB_SOURCE" rev-parse "HEAD^{tree}")" = 47f03f03cc26e40793dcce90cdc8c62d673ed9b9
python3.12 -m venv /srv/verb/env
VERB_PY=/srv/verb/env/bin/python
VERB_TOOLS="$VERB_SOURCE/tools/verb_measurement"
"$VERB_PY" "$VERB_TOOLS/cloud_run.py" prepare --source "$VERB_SOURCE" --commit 74d88e66f0ebcfcdaae007d80ad5df5514e465b7 --root "$VERB_OUTPUT_ROOT"
```

`prepare`は三本のruntimeを作るだけで、模型を始めない。出力済みの根や走行済みの同じ場所への再投入は拒否する。OSがLinux、Pythonが3.12、HEADが固定、作業木がclean、模型の木と観察SHAが一致しなければ走行しない。

三本とも個体worker1本、親を含む開始CPU枠2、受付メモリ見込み2.0GB。Macのspecの全旗を`cloud/plan.json`へ転記した。種1、設定trial-count5000、horizon5000、実行は先頭100／100／300だけ。全部入り・出生HU on・速度旗既定off、測定λはe-priceとv39-priceとも0.01873710622997919。300には固定非学習試験が含まれる。本番のλへ代用しない。

## 受付と資源の確認

`VERB_JOBS`は、走行係が使っているUbuntu対応の既存jobs受付を指定する。Mac専用のpmset/sysctl版をそのままUbuntuへ持ち込まない。受付表・規則を外す代替の直起動はしない。

既存の受付・資源監督が、各本の`runtime.json`のSHAに結び付けた確認を`VERB_CLEARANCE_ROOT/<label>.json`へ作り、監督中も60秒以内の間隔で原子的に更新する。確認が用意できない場合は、開始前の条件が揃っていないので待つ。値を推測で真にしない。

必要な欄は`runtime_sha256`、`machine_sha256`（/etc/machine-idのSHA256）、`memory_reservation_gb=2.0`、`checked_epoch`、`warning`、`memory_admission_ok`、`swap_stable_10min`、`thermal_ok`、`physical_cpu_count`、`cpu_budget`。CPU予算は既存規則どおり物理芯数から2を引いた値。受付メモリ、直近10分のswap、熱について既存監督が確認する。

入口は実際の個体workerを数えて同時8本までを保ち、親・監督・time・resource_tracker・T/Zを模型の稼働数に足さない。Macの既存の数え方を変更せず複製した。未分類spawn、CPU枠超過、熱・受付確認の欠落や古さ、空き容量の警告では自分の測定群だけを既存方式で一時停止し、条件が戻れば自動再開する。他の係・本番を操作しない。開始時の空き20GiB、監督時の18.5GiBの境界も維持する。常駐が2.0GB予約を超えた場合は原記録を残して次の開始を待ち、新しい実測に合わせて次の予約を判断する。

## 同じ機械の100二本と比較

この二本の全旗の差は`--probe-world`だけ。別の機械や別の版の片側と混ぜない。各本の資源確認を先に用意した後、順に実行する。

```sh
"$VERB_PY" "$VERB_TOOLS/cloud_run.py" run "$VERB_OUTPUT_ROOT/on100_without_probe" --jobs "$VERB_JOBS" --clearance "$VERB_CLEARANCE_ROOT/on100_without_probe.json"
"$VERB_PY" "$VERB_TOOLS/cloud_run.py" run "$VERB_OUTPUT_ROOT/on100_with_probe" --jobs "$VERB_JOBS" --clearance "$VERB_CLEARANCE_ROOT/on100_with_probe.json"
"$VERB_PY" "$VERB_JOBS" run --wait --mem .2 --disk-path "$VERB_OUTPUT_ROOT" -- "$VERB_PY" "$VERB_TOOLS/cloud_compare.py" "$VERB_OUTPUT_ROOT/on100_without_probe" "$VERB_OUTPUT_ROOT/on100_with_probe" "$VERB_OUTPUT_ROOT/on100_comparison.json"
```

300の資源確認には`first_pair_decision`も必要。`model_commit`と`observer_sha256`、`selected_pair`（Mac又はcloud）、`pairs.Mac`と`pairs.cloud`を含む。各組には`checked_epoch`、`state`（waiting又はcompleted）、完了なら`finished_epoch`と原本`comparison`を入れる。両方の確認時刻はクラウド組の完了時刻以降とし、早く完了した組を選ぶ。原比較の全ファイルのSHAと不一致0を再確認する。未確認の機械をwaitingと推測して記入しない。先行不一致は300を開始できず、後の組で上書きできない。

正常終了・manifest・partial_doneが100、設定とhorizonが5000、全5000完了ではないことを確認する。試験ありは48問・fingerprint1回、注意と問い回数の前後一致を確認する。本体・乱数の保存復元の検査は固定した非学習試験の接続に含まれる。資源警告付きの結果を無条件に合格へしない。

比べ方はMacのon100_retry2_compare.pyと同じ。`ledgers`・`side`・`evictions`・`attention`にある全ファイルの集合を比べ、gzipは内容の全バイトを比較する。欄を削除・丸め・再配列しない。固定試験だけの`.probe.jsonl`と`.done`は比較から除いて原本保存する。台帳、全side、順付き保存状態、evictions、注意は含む。必須の入口の一覧は次のとおりで、実際の出力で加わったsummaryや診断も同じ対象フォルダ内ならすべて比較する。完了後の正確な全一覧はcomparisonの`files`とSHA表になる。

| 対象 | cell以下の種1のファイル |
|---|---|
| 台帳 | ledgers/cells/<cell>/seed001.jsonl.gz |
| side | seed001.jsonl、seed001.ambig.csv、seed001.answers.csv、seed001.routing.jsonl |
| SMEと保存状態 | side/<cell>/seed001.sme.jsonl.gz、seed001.sme.states.jsonl.gz、付随する診断 |
| evictions | evictions/<cell>/seed001.keys.jsonl.gzとsummary |
| 注意 | attention/<cell>/seed001.jsonl.gzとsummary |

cellは`f0.5000_th2.1000_vt0.3842_first_order`。比較では件数・各欄のファイル・最初のバイト位置・例を記録する。一件でも不一致なら模型を直さず止まりとして報告し、300を始めない。第二段の秒を含む`stage2`、`timing`、gzip容器、time、manifest、flagは原本を別保存する。非模型の時間を一致させるために模型の出力を書き換えない。

Macの組とクラウドの組のうち、二本とも先に正常完了した同機械の組で関門を判定する。`finished_epoch`を保存する。両機械の結果が届いたら、先に完了した組を最新の報告で確認してから300の新規開始を決める。先に完了した組が不一致なら、後の組で上書きして合格にしない。先にMacが通った場合も、クラウドの二本が終わる前にこの包みの300は始めない。Macの既存処理は止めない。

## 300の一本測定

同機械の100二本が通り、先に完了した組の判断も記録された後に行う。版・旗・λは変えない。

```sh
"$VERB_PY" "$VERB_TOOLS/cloud_run.py" run "$VERB_OUTPUT_ROOT/allin_s01_300" --jobs "$VERB_JOBS" --clearance "$VERB_CLEARANCE_ROOT/allin_s01_300.json" --gate "$VERB_OUTPUT_ROOT/on100_comparison.json"
```

完了数300を全5000完了と書かない。上の入口は比較passed、同じ機械、同じ版・観察SHA、両側の完了と固定試験をもう一度確認する。Mac側の300は別の未起動監督であり、この命令で二重起動しない。Macの監督もinstruction9_first_pair_decision.jsonを先に確認する。Macの比較へ時刻を付けるときは、二本の原resultのfinished_epochの最大をcomparisonのfinished_epochとして添える。内容比較のfilesを変更しない。先行組の判断が未生成なら300を始めない。

## 終了後に報告枝へ同梱するもの

各本について、time.log原本、result、版・全旗の出所、100ごとの実時間とCPU秒・常駐の表、全出力のraw/content SHA表、第二段・誕生・再照合の時間内訳を作る。比較結果も同梱する。全出力原本は機械に保持し、100MB超の台帳や秘密をGitへ上げない。

```sh
"$VERB_PY" "$VERB_JOBS" run --wait --mem .5 --disk-path "$VERB_OUTPUT_ROOT" -- "$VERB_PY" "$VERB_TOOLS/export_tables.py" "$VERB_OUTPUT_ROOT/on100_without_probe" "$VERB_OUTPUT_ROOT/report_on100_without_probe"
"$VERB_PY" "$VERB_JOBS" run --wait --mem .5 --disk-path "$VERB_OUTPUT_ROOT" -- "$VERB_PY" "$VERB_TOOLS/export_tables.py" "$VERB_OUTPUT_ROOT/on100_with_probe" "$VERB_OUTPUT_ROOT/report_on100_with_probe"
"$VERB_PY" "$VERB_JOBS" run --wait --mem .5 --disk-path "$VERB_OUTPUT_ROOT" -- "$VERB_PY" "$VERB_TOOLS/export_tables.py" "$VERB_OUTPUT_ROOT/allin_s01_300" "$VERB_OUTPUT_ROOT/report_allin_s01_300"
```

第二段のJSONLと整形済みJSON summaryをそれぞれの形式で読み、時間内訳へ記録する。出力表の非模型検査はクラウド用15件、速度用13件が通った。

報告表は`checkpoints.tsv`、`sha256.tsv`、`timing_breakdown.tsv`、`provenance.json`、`result.json`、`time.log`。300では`conditional_5000_estimate.json`も作る。100・200・300の累積と各区間の実時間、user/sys・合計CPU秒を区別する。Linuxのru_maxrssはKiB、MacはBなので、観察driverの原記録を変更せずLinux報告表で1024倍し、原値と単位も残す。GNU time -v原本も保持する。

5000見積りは、実測三つの100区間の最小〜最大と同じ負荷が残り4700で続く場合の条件付き幅。重さの増大や資源待ちの上限を保証しない。第二段のwrapper・本体・再照合には包含があるので時間を無条件に足さない。結果の良し悪しは書かない。

走行係は小さい報告物をこの包みの下の機械別の新しいフォルダへコピーし、comparisonのローカルパスは匿名の出力根へ置き換えて共有する。原本は機械に残す。秘密・個人情報・100MB超、送るlogとdiff --statを確認し、報告枝を最新へfetch・mergeして通常pushする。rebase・force-pushは禁止。種21〜40の読み取りや走行、削除、本番の停止、受付・関門の規則外しは行わない。

## 二の次：速度off/on200の包み

準備のみ。99件の構造検査、別の200観察入口の20件の非模型検査が通った。全バイトの学習関門は未実行。本番の速度旗や全長の関門は300の後にClaudeとアストラが判断する。

別の専用checkoutを土台e9から作り、`speed200/source.bundle`をverify・fetchして`412b9ce8ff6274d6b1da548ed4b1509f2bbf1772`をcheckoutする。上の三本用checkoutや出力へ上書きしない。芯2・メモリ2.0GB・同機械二本・種1・trial-count/horizon5000・完了200。全旗はMacの試験あり全部入りを保ち、二本の差は`--stage2-speed`と`--stage2-cache-prune`のoff/onだけ。固定試験は各96問、fingerprint2回。観察driverの追加差分は先頭200の許可と完了説明だけ。現在のMacdriverは変更していない。

```sh
VERB_SPEED_SOURCE=/srv/verb/speed_source
VERB_SPEED_ROOT=/srv/verb/speed200_20261009
VERB_SPEED_TOOLS="$VERB_SPEED_SOURCE/tools/verb_measurement"
git clone --no-checkout https://github.com/Godfumitaka/sfn-compression-abm.git "$VERB_SPEED_SOURCE"
git -C "$VERB_SPEED_SOURCE" checkout --detach e9ed84ae3ee6c458f392cd58cadf9fc030639900
test "$(sha256sum "$VERB_PACKAGE/speed200/source.bundle" | cut -d " " -f 1)" = 83aec21dad227ad5f0b9ec0c82f92544b8c9c2e74e58c53f352e45137a62eb24
git -C "$VERB_SPEED_SOURCE" bundle verify "$VERB_PACKAGE/speed200/source.bundle"
git -C "$VERB_SPEED_SOURCE" fetch --no-tags "$VERB_PACKAGE/speed200/source.bundle" refs/heads/codex/verb-stage2-speed-2026-10-09
git -C "$VERB_SPEED_SOURCE" checkout -b codex/verb-stage2-speed-2026-10-09 412b9ce8ff6274d6b1da548ed4b1509f2bbf1772
test "$(git -C "$VERB_SPEED_SOURCE" rev-parse HEAD)" = 412b9ce8ff6274d6b1da548ed4b1509f2bbf1772
test "$(git -C "$VERB_SPEED_SOURCE" rev-parse "HEAD^{tree}")" = 07f9428b143b9fe82b89e918b9b6921d4ea03b6f
"$VERB_PY" "$VERB_SPEED_TOOLS/cloud_run.py" prepare --source "$VERB_SPEED_SOURCE" --commit 412b9ce8ff6274d6b1da548ed4b1509f2bbf1772 --root "$VERB_SPEED_ROOT"
# 走行の指示を受け、受付・同機械・資源確認が揃ってから使う命令。
"$VERB_PY" "$VERB_SPEED_TOOLS/cloud_run.py" run "$VERB_SPEED_ROOT/speed200_off" --jobs "$VERB_JOBS" --clearance "$VERB_CLEARANCE_ROOT/speed200_off.json"
"$VERB_PY" "$VERB_SPEED_TOOLS/cloud_run.py" run "$VERB_SPEED_ROOT/speed200_on" --jobs "$VERB_JOBS" --clearance "$VERB_CLEARANCE_ROOT/speed200_on.json"
"$VERB_PY" "$VERB_JOBS" run --wait --mem .2 --disk-path "$VERB_SPEED_ROOT" -- "$VERB_PY" "$VERB_SPEED_TOOLS/cloud_compare.py" "$VERB_SPEED_ROOT/speed200_off" "$VERB_SPEED_ROOT/speed200_on" "$VERB_SPEED_ROOT/speed200_comparison.json" --limit 200
```

比較対象と不一致時の扱いは100と同じ。P10の禁止参照の件数やキャッシュsummaryも原本保存して報告する。200一致を全5000の一致や本番採用に読み替えない。指示3・6・7・8・9は実施中。
