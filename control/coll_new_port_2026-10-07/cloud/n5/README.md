# 指示5：八体クラウド台本の準備

候補版は `c4cfed12a3944071951775b2c9373ca27705fb25`、土台は `e9ed84ae3ee6c458f392cd58cadf9fc030639900`。本体の `abm/`・`v39.py` は変更していない。このフォルダは準備物で、模型・AWS資源・受付を自動で開始しない。

候補版は自分の `codex/coll8-allin-2026-10-08` へ通常push済み。クラウドではこのコミットを固定し、Python3.12と必要な既存依存を備えた実行環境を使う。受付後に実際の版・作業差分・Python・OSを記録する。OSをまたぐ値の一致も実際の関門で確かめ、差があれば修正して通すことはしない。

指示で指定された `control/ataru-0608/cloud/` は、2026-10-08 15:47の results に存在せず、形式は未照合。所在地を照会している。これは同形式へ移す前の独立した案。

## 保っている順番

1. 二体OFFの指示3の再判定（完了済み）。元の不合格を保全する。
2. 既存の八体OFF直列200と旧版の一致。マックのPID44480は待機中で、ここから再起動しない。クラウドで直列を行うなら、マックの模型未開始・待機の引き継ぎ・一意の取得を先に確認した `off8-cloud-handoff.json` が必要。台本はその確認を自動で作らず、待機を止めない。直列の完走があれば保存済み出力をクラウドで比較できる形に置き、直列を再走行しない。
3. 同じ候補版・同じ値の八体並列OFF200。`--v311c-serial` だけが違う。状態・乱数・控え・台帳本体・通信事象を `compare_off8.py` で比較する。不一致の判定は新しい名前へ残し、直さず停止する。
4. 一体ONとe9の独立単独200以上、状態隔離・材料・誕生・墓石・未知名停止・受信と再生の元の関門。ここは未走行で、合格を示すファイルはまだ作らない。
5. 八体の短い測定。案は世界2・種1・300試行、f0.1×4・0.9×4、q0.2・m0.1・受信A、誕生HU on、診断100、audit off、高速化off。四体の旧い関門の除外は継続確認本文の禁止により「保留：アストラの承認待ち」。元の指定を未承認で削除しない。
6. #20の未着手指定後、最新の列の版・旗・出力先を一致させ、取得を通常pushしてから本番。案は八体全部同じf0.1又は0.9、種1〜5の計10集団。q・mなどは列が埋まるまでは案。本番L50_ref、受付予約も未確定で、draftは実行不可。

## 台本の役割

- `cloud_run.py plan specs/<名前>.json`：模型をimportせず計画を表示。AWS API・SSH・ネットワークを呼ばない。
- `cloud_run.py run ...`：Linux上の既存の受付 `jobs.py run --wait --mem ... --disk-path ...` を呼ぶ。受付の設定・予算を変更しない。新しい出力だけを使用し、固定版・作業差分・期限・八体の空き・20GiB・資源確認・先行関門を受付後にも検査する。模型の開始後に過程を止める信号を送らない。
- `observe.py`：既存の外部観測台本のコピー。Linuxのru_maxrssのKiB換算と、並列でserial_lockがNoneの場合の時計だけを適応した。模型の戻り値・乱数・argv・取り付け順は変えない。原台本と差は `observer-provenance.json` とdiffに残す。
- `compare_off8.py`：両側の完走出力を読む。固定版、台帳の実サイズ、同版の見出し全欄、200行と実f、終了と墓石・辞書外0を必須検査する。cfvalueの時計と、検査済みの終了メタデータだけを別にする。台帳と状態・乱数は生バイト。
- `export_tables.py`：本体をクラウドに残し、新規の報告先へ `runs.tsv` と `sha256.tsv` だけを保存する。鍵、環境変数、認証ファイルを取得・記録・GitHubへpushする機能は無い。運用担当はこの二つの表と関門の判定を自分の報告枝へ通常pushする。

## 実行前に確定が必要なもの

クラウドの実行場所・受付・CPU8本の割当て・実測の予約値・永続出力先はまだ提供されていない。25GBはN4の条件付き外挿であって、予約値や安全上限ではない。手元の24GBの受付設定をこの台本で外さない。新しいONの予約は一体の短い実測と受信を含む測定から決める。

関門の証拠は `passed:true` と候補版が一致している必要がある。本番には `queue-proof` の #20・固定版・通常push済みのresults commit・取得状態・spec SHA256・L50_refの出典が必要。列を埋める権限はClaudeにある。この証拠を台本自身が捏造する機能は無い。

資源の確認ファイルには `warning:false`, `spec_sha256`（plan specのsort_keys JSONのSHA256）, `source`, `output`, `reservation_gb` を、当該実行場所の確認から記録する。仕様・出力先・予約が一致しなければ開始しない。受付後の警告は新しい走行を禁じる。既存の本番は止めない。

同じ出力又はevidenceフォルダがあれば再走行しない。失敗したフォルダを消してやり直すことも無い。期限は2026-10-09 09:00 JST。受付待ちの後も模型を始める前に検査する。期限後に新たな走行を始めず、既に開始した模型は自然終了まで保つ。

## 計画だけを確認する例

```sh
python3 cloud_run.py plan specs/cloud_off8_parallel200.json
python3 cloud_run.py plan specs/cloud_prod8_f0.1_seed01_draft.json
```

実走行用の値が確定した後の入口は次の形（いまは未実行）。`CLOUD_*` はその場で指定し、合い言葉や鍵を値に入れない。

```sh
python3 cloud_run.py run specs/cloud_off8_parallel200.json \
  --source "$CLOUD_SOURCE" --root "$CLOUD_RUN_ROOT" \
  --python "$CLOUD_PYTHON" --jobs "$CLOUD_JOBS" \
  --gate-root "$CLOUD_GATE_ROOT" --resource-clearance "$CLOUD_RESOURCE_CLEARANCE"
```

比較と表作成も重い保存記録の読み取りなので、クラウドの受付を通す。比較は結果を上書きせず、本体を手元にダウンロードする必要は無い。

```sh
"$CLOUD_PYTHON" "$CLOUD_JOBS" run --wait --mem 1 --disk-path "$CLOUD_RUN_ROOT" -- \
  "$CLOUD_PYTHON" compare_off8.py "$CLOUD_SERIAL_EVIDENCE" "$CLOUD_PARALLEL_EVIDENCE" "$CLOUD_NEW_GATE"
"$CLOUD_PYTHON" "$CLOUD_JOBS" run --wait --mem 1 --disk-path "$CLOUD_RUN_ROOT" -- \
  "$CLOUD_PYTHON" export_tables.py "$CLOUD_PARALLEL_EVIDENCE" "$CLOUD_NEW_TABLE_DIR"
```
