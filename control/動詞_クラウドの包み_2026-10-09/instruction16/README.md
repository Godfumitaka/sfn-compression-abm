# 指示16：未実行の本番草稿とspeed200原記録の読み手

指示16は2026-10-09T15:18:37+09:00に受領。受領push `1361f3916e7ee44c58f1f3228a6edec415f610b9`、送信確認 `c482885222f3b8208f86ab3183df6f0222d3a471` の後に作業した。

## 本番草稿

`../instruction11/production_templates.json` と39本の `../instruction11/command_drafts/` を、#19・#19c・#21・#22と並べる#19種1旗なしの全てで `--match-eps 0` にそろえた。既存の `--logp-eps 0.01` と他の旗・順・価格・受付・列の条件を保つ。#22の既存草稿にはlogp-eps指定が無く、その有無も変えていない。E価格0.01873710622997919とB価格の未記入欄を保つ。λ・正式なsourceはnull、全草稿ready_to_start=false。#21・#22の速度二旗offを保つ。

39草稿のtemplate_sha256には以前のテンプレートのSHAが残っていたため、今回のテンプレート内容にそろえた。元のSHAとファイルの前後SHAを `drafts_eps0_evidence.json` に記録した。ε・命令の同じ値・template_sha256以外のJSON欄と旗を照合した。instruction11/SHA256SUMSも更新済み。旧bundle・固定source・完了済み/走行中の模型と原記録は変更していない。指示16に従いεだけを理由に関門を再走行しない。本番は既存の関門と正式列を待ち、並べる旗なし一本の見張りを維持する。

## 試験の数

同梱済み977版のspeed200観察は設定・horizon5000の先頭200だけを反復する。lenは5000のまま。試行199でもapply_thetaを呼んだ後に台帳を追記するので、試験はt100とt200に呼ばれる。closeのprobesは固定問題の数48、rowsは二時点の回答96行、fingerprint_checksは2。注意と問い回数の保存復元も2件必要。実装の出所SHAと入口は `speed200_count_semantics.json`。

旧412版completeのprobes==96という検査は問題数と回答数を混同していた。現行の `cloud_run.py`（SHA d22265e6c4ca1ab29983b4468b9aebecd13b527ff82a47411a3e6526da95611d）は既にprobes48・rows96・fingerprint2を区別している。今回、同じ修正を再実装せず、その現行版と依存をバイト一致で `read_tools/` へそろえた。`speed_gate.py`（SHA dbeaa0b51b14a062f14488b96c332eecb682f7c48ceb0f755ac793dcd8b2187f）は試験行を外さず、.probe.jsonlの96回答と試験後100〜199の学習を含め、台帳・全side・保存状態・evictions・注意・第二段・研究者記録を比較する。既定の第二段TIME値の扱いも変えていない。比較対象・合格条件を減らしていない。

これは実装の読取確認で、クラウドの原出力の実数を確かめた結果ではない。実際に走行した旧版SHA、原manifestのrows、原回答行数は未着のため未確認。実際の値が96回答を満たさなければ条件を弱めず、欄・数・例を報告する。原出力と走行時の版・旗・観察を変更しない。

## 原記録がそろった後の読み取り

`read_tools/` は現行の読み手一式のレビュー用コピー。固定sourceへ上書きせず、別のこの一式から完了した同版・同機械の二本を読む。旧result/runtime/start/manifest/partial_done/checkpoints/time/outputをそのまま用い、原版と旗・観察SHAの一致を先に確認する。出力先は原出力と別の未作成の場所。受付のメモリは実測に合わせた既存条件で指定する。

```sh
"$VERB_PY" "$VERB_JOBS" run --owner verb-instruction16-speed200-read --wait --mem "$VERB_COMPARE_MEM" --disk-path "$VERB_COMPARISON_ROOT" -- "$VERB_PY" "$VERB_READ_TOOLS/speed_gate.py" "$VERB_RAW_ROOT/speed200_off" "$VERB_RAW_ROOT/speed200_on" "$VERB_COMPARISON_ROOT/speed200_instruction16" --on100-decision "$VERB_ON100_DECISION" --on100-report-commit 84273515fbabb6fb2c7ae45de00609b196f8e267
"$VERB_PY" "$VERB_JOBS" run --owner verb-instruction16-speed200-off-tables --wait --mem "$VERB_COMPARE_MEM" --disk-path "$VERB_COMPARISON_ROOT" -- "$VERB_PY" "$VERB_READ_TOOLS/export_tables.py" "$VERB_RAW_ROOT/speed200_off" "$VERB_COMPARISON_ROOT/speed200_off_tables_instruction16"
"$VERB_PY" "$VERB_JOBS" run --owner verb-instruction16-speed200-on-tables --wait --mem "$VERB_COMPARE_MEM" --disk-path "$VERB_COMPARISON_ROOT" -- "$VERB_PY" "$VERB_READ_TOOLS/export_tables.py" "$VERB_RAW_ROOT/speed200_on" "$VERB_COMPARISON_ROOT/speed200_on_tables_instruction16"
```

上記は未実行。on100承認済み先行組判断と実際の送信コミットを先に確認する。`first_pair_instruction15.json` は既存の承認済みMac判定の同一コピー。較正200はその原二本がそろった場合に別の出力へ同じ全比較を行い、通常200と混ぜない。読取コピーのcloud_runは開始入口も含むが、ここではcompleteだけを依存として用い、prepare/runや模型の起動は行わない。

## 未完了

クラウドon100の承認済み再比較、通常/較正200の原全バイト比較と実発生数、原100区間の時間からの5000見込み更新は未完了。AWSログインの人間の回答は未着で、同じ質問・ログイン・期限切れアクセスは繰り返していない。31,329秒・25,617秒と比1.223は指示16と走行係の報告値で、原記録の測定値として確認したものではない。総時間から100区間を推測していない。P5/P7rは今後依頼予定であり、今回の移植委任として開始していない。

300取消、本番未開始、模型起動0・比較起動0・再検査0。Macの指示15の2(a)(b)は完了済みの記録を保ち、再投入していない。指示16の1は草稿反映済み、2の実比較を残し、指示16全体は実施中。
