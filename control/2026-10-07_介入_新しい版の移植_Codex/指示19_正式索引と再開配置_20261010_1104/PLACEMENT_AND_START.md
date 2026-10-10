# 指示19：正式索引とA/Bの再開配置・開始手順

指示19（2026-10-10 10:53）の番号付き回答で、正式原索引と再開先が確定した。指示17・18はこのチャットのアストラの2026-10-10T09:40:03 JSTの直接承認を受領・通常push済み（619d7e68）。追加の承認待ちはない。実機の配置・資源確認・走行はデスクトップが行う。

## 配るファイルと固定SHA

この文書の隣の `package/` を、新しい別名の包みディレクトリへ全ファイル同じ原字節で置く。元の包みと元索引を上書きしない。文書・後から作る指紋や一覧・走行出力は `package/` の外に置く。

正式原索引は `results-2026-09-27` の `control/集団化_クラウドの包み_2026-10-09/SHA256SUMS`、最終変更コミット `f35a579d85d8ceab11c3c87f41c7f81729cd89d6` の49行。索引SHAは `cec06dd9ec20b298ce0e42ac1d390c09b19a57610141ce67314a52014ef50a7a`。そのコミットから全49ファイルを取り出し、全掲載SHAとの一致を確認した。別の旧作業場所のUUと衝突を含む控えは変更せず保存する。旧控えを正式索引へ代用しない。

|ファイル|SHA256・内容|
|---|---|
|SHA256SUMS|上記cec06dd9…、正式原49行そのまま|
|observe_independent_spawn15.py|ae22f197a58289435387bbfb109084fabd26af15e3b5d0193d395b3f300faa5c|
|run_spawn15.py|d38b21f7e0e1f6033a545319d379e8a9ecf79c70ff1ceb125b6797c76486fea3|
|SHA256SUMS_instruction15|99784eb419f3cb443ac9c96b2b5699030d44d2323437bdf1470dbe25500deaec、原49行＋spawn15二行だけ（51行）|
|SHA256SUMS_instruction18|423781d1f0ef87337621f0a0fab251ab8a5341aba04d11abf7d0cc40119de180、上記51行＋指示18三行（54行）|
|PACKAGE_MANIFEST_instruction18.json|c67089046cdb85d43e7f62a153aeba80a7646e746a6310f455e74e34e7de5946、原索引・二別索引を含む全57ファイル。自己参照するmanifest自身だけをfilesから除く|

原のrun.py・observe_independent.py・compare.py・measurement.py・processes.py・runtime_capture.py・v311c_fingerprint.py・configs/・specs/・clearance.pyは全て原字節。候補二台本と指示18三台本も受け入れた準備候補の原字節を複製した。候補の構造5件・保存二本の25項目比較・指示18の構造24件は既存証拠を維持し、再実行していない。この配置の確認は実機関門の合格ではない。

## 正式な保存先と版

旧STOPのある `sfn-coll-gate:/mnt/coll_gate_gcp/run-same-host/` はそのまま残す。旧STOPの解除・削除・書換え・無視を行わない。

|機械|新しい永続root|同じ機械で行うon1比較|
|---|---|---|
|A（sfn-coll-gate）|/mnt/coll_gate_gcp/resume_spawn15_A/|on1_f0.1_collective200 と on1_f0.1_independent200|
|B（デスクトップ75の同じ種類の機械）|/mnt/coll_gate_gcp/resume_spawn15_B/|on1_f0.9_collective200 と on1_f0.9_independent200|

Bの機械名はデスクトップの実一覧を使い、架空名を登録しない。新rootにも既存出力・STOPがあれば開始しない。各機械の新rootでcomponents・off2・off8・off8-parallel・pilot20を実際に通す。旧STOP rootの合格札を新rootへ複製して前関門の再走行を代用しない。

模型の三作業場所は自分の新しいコード専用checkoutを使う。種別結果を展開せず、種21〜40を読まない。

- CANDIDATE：c4cfed12a3944071951775b2c9373ca27705fb25
- BASELINE：c55b8c1a62b04002413686b0405bc1960fa8d6b9
- PREPARATION（独立単独）：e9ed84ae3ee6c458f392cd58cadf9fc030639900

全旗・設定・試行数は同梱specsと元validateで固定する。候補92913206への置換、本番、新しい介入はこの配置へ含めない。

## 当該機械の開始手順

`PY` は実Python3.12、`PKG` は新しい包みの絶対パス、`RUN` は上表の当該root、`JOBS` と三模型パスは当該機械の実絶対パス。CPU8・空き20GiB・予約合計24GB・同じ機械に他模型がない条件と実過程の親子関係を直前に確認する。待つ親・jobs・resource_trackerを模型へ二重計数しない。停止中は別記する。各本の前に実予約合計を読み、資源警告なしを確認して新しい資源札を作る。空欄や未確認の0を使わない。

まず原と新の掲載SHAを照合する。

```bash
cd "$PKG"
sha256sum -c SHA256SUMS
sha256sum -c SHA256SUMS_instruction15
sha256sum -c SHA256SUMS_instruction18
```

各模型本は次の共通手順で通常受付へ通す。`NAME/SOURCE/MEM_GB/EXISTING_GB/RESOURCE/MEMORY_NOTE/CLEARANCE` はその一本の実値。RESOURCEは実測の原resource.json、初回pilotだけは原入口が許すbootstrap根拠を記してresource-fileを省く。元READMEのOFF2 1GB・OFF8 2GBは旧実測の既存予約であり、実機の警告と山を保存する。ONの予約はpilotや前段の実測と条件差から埋め、予約を下げて入場させない。

```bash
"$PY" "$PKG/clearance.py" "$NAME" --root "$RUN" --source "$SOURCE" --jobs "$JOBS" --mem "$MEM_GB" --existing-gb "$EXISTING_GB" --resource-file "$RESOURCE" --memory-note "$MEMORY_NOTE" --no-resource-warning --record "$CLEARANCE"
"$PY" "$PKG/run_spawn15.py" run "$NAME" --source "$SOURCE" --root "$RUN" --jobs "$JOBS" --mem "$MEM_GB" --clearance "$CLEARANCE"
```

clearanceが成功した後だけrunを行う。clearanceは各本で別名、10分以内の実確認。同じclearanceを使い回さない。run_spawn15.py自身がownerを明示したjobsのrun/--wait/--mem/実出力disk-pathへ通し、受付後も全条件を確認する。

1. `components.py run --source "$CANDIDATE" --root "$RUN" --jobs "$JOBS"`（この入口も通常受付を使う）。
2. off2_baseline200（BASELINE）、off2_candidate200（CANDIDATE）を順に自然終了させ、原compare.pyの `off2` を通常受付内で行う。
3. off8_baseline200（BASELINE）、off8_candidate200（CANDIDATE）、原比較 `off8`。
4. off8_parallel200（CANDIDATE）、原比較 `off8-parallel`。
5. on1_pilot20（CANDIDATE）を一度行い、20件・自然終了・全必要記録・実測resourceを確認する。外側終了0だけで合格にしない。
6. Aはf0.1、Bはf0.9のcollective200（CANDIDATE）→independent200（PREPARATION）を同じ機械・同じ起動で順に行い、原比較 `on1-f0.1` 又は `on1-f0.9`。

比較も受付外で重い控えを展開しない。命令の形は次のとおり。CHECK_MEMは比べる実出力サイズと実測から埋め、ownerと実出力先を明示する。

```bash
"$PY" "$JOBS" run --wait --owner '探索の腕と介入の係 指示19 関門比較' --mem "$CHECK_MEM" --disk-path "$RUN" -- "$PY" "$PKG/compare.py" "$RUN" "$PAIR"
```

原比較の全名前集合・原順/字節・模型欄・全控え/乱数・試験行・実版/実物理サイズ・必要メタデータを減らさない。時計は指示16のコード根拠がある指定欄だけを両側のファイル/行/欄名/値とともに残す。不一致・必要記録不足は最初のファイル/行を残して停止し、候補修正・並べ替え・許容差追加を行わない。旧compare.pyを変更しない。

受信/再生と八体測定の段をまたぐ証拠は、同梱 `PLACEMENT_AND_USE.md` の指示18の入口で読む。当地の前関門と同じ機械内の比較は維持する。入口期限2026-10-11 00:00 UTC（10/11 09:00 JST）を変更しない。継続確認の10/13 09:00 JSTとは別。期限後に新規開始せず、期限を理由に動いている本番を停止しない。

B5(a)マック修正後ON200は既存受付50927の同じ一本が走行中。二重起動・予約変更なし。B5(b)の入口の同じhost条件は指示18で変更していない。B5全体とB6、本番は未完了。B6は実際のB5(a/b)合格後に進む。
