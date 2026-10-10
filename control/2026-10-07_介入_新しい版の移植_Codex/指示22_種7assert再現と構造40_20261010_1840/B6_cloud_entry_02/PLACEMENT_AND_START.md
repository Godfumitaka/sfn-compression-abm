# B6：八体D＋注意の別受付入口の準備

この包みは種1・世界2・八体・先頭20・τ0.4の診断一本のための別入口です。計算論と人間的の各10本の本番specは `production_specs_01` に原字節で保存した草稿のままです。本番の列の取得でも、候補e96の受け入れでもありません。

元のB5入口と元c4の五requires、追加のoff2、計8実関門の対応を保持しています。各関門の実passed・版c4・同じhost/boot・原SHAを読む条件を外しません。旧STOP rootと旧出力を保持し、別の専用rootを指定してください。関門や予約を外して入口を通すことはありません。

候補は `e96ce25fc24ebe70b68a51218262e08de9eb753f`。元c4からの9ファイルの差分一覧と原SHAは `source_delta_manifest.json`。abm本体は差分にありません。元929の書き出し修正に、受け入れAのDのq/k2・試験/反実仮想をDの包みへ入る前に抑止する接続を加えた、関門前の候補です。

`run_B6.py` は受付前と受付後に次の四証拠の原SHAを直接読みます。証拠をここで新しく作ることはありません。

- B5(a)：保存二本の全27出力名・31比較・200試行・試験行を含む原比較結果。元c4/929の両側実メタデータ。
- B5(b)：元の同じhostでの929八体20の実自然終了と必要記録の点検結果。
- B6旗off：同じマックの保存929とe96のON200全27出力名・31比較・全原順/試験行・全控え/乱数、実メタデータの比較結果。現在の同じ一本の自然終了後に用意します。
- B6構造39：既存の通常受付25098の終了0・原資料不変のJSONと、原39 passedのログ。これは合成構造で、実20での試験実施の証拠にしません。

この四証拠の封筒をJSONで渡します。各項目は `path` と `sha256`、構造39だけはさらに `test_log_path` と `test_log_sha256` を持ちます。キーは `B5_a`、`B5_b`、`B6_off`、`B6_structure39` です。当地の機械に原字節で写し、その実パスを指定してください。未合格・不存在・SHA差を補わず拒否します。

通常受付の条件はowner/wait/実測mem/実出力disk-path、全体8模型、実CPU8枠、空き20GiB、予約合計24GB、資源警告なし、直前の資源札10分以内、同じhost/boot、受付後の全条件再点検です。開始期限は2026-10-13 09:00 JST（00:00 UTC）。走行中を期限だけで止めません。実測記録と条件差/余裕をデスクトップが確認した予約を使います。

命令の形は以下です。実行するのはデスクトップであり、この包みの準備や合成検査で実機の受付札を作りません。

```sh
python clearance_B6.py instruction12_B6_human8_f01_seed1_20 --root "$B6_ROOT" --source "$B6_SOURCE" --jobs "$JOBS" --mem "$MEASURED_GB" --existing-gb "$EXISTING_GB" --resource-file "$MEASURED_RESOURCE" --memory-note "$CONDITION_DIFFERENCE_AND_MARGIN" --no-resource-warning --record "$CLEARANCE"
python run_B6.py run instruction12_B6_human8_f01_seed1_20 --source "$B6_SOURCE" --root "$B6_ROOT" --jobs "$JOBS" --mem "$MEASURED_GB" --gate-root "$ORIGINAL_C4_GATE_ROOT" --intervention-gates "$INTERVENTION_GATES" --clearance "$CLEARANCE"
```

指定旗は元の八体命令を維持し、第二段/birth-huをoff、Dをτ0.4/q/k2注意にしています。`probe-every100` は100のままなので実20では集団試験を実行しません。個体別のuseforgetとretentionの原20行、原ST/AUDITに相当する物理記録、全台帳/manifest/通信/evictions/控え/乱数、完了札の実版/実サイズと原資料前後不変を点検します。存在する試験/反実仮想の不変チェックに差があれば拒否し、不存在を試験合格へ読み替えません。Dと直列は拒否します。

構造11件は通常受付に一度投入済みで、保存結果の自然終了を待っています。準備・構造合格・実模型の全関門・候補の受け入れを分け、B5(b)とB6旗offが揃うまで八体依頼と実模型は開始しません。全旧候補・停止・一時資料は保存します。
