
## 2026-10-06T20:06:28.074357+09:00：SME・N3先行80本（stopped）

利用者の順序変更に従い、支持の割合の旗の実装・関門を保留する。N3の80本の下見とその報告の後に再開する。支持の旗の試作は別の作業場所へ保存し、今回のN3走行には適用しない。

N3：模型0／80本、解析0／80本が完了。条件はA／D（τ=0.4）×skeleton・current・plus4・plus8×世界1・2×種1〜5、各1,740試行、λ=0.01873710622997919、Uは既定の答え。種21〜40には触れない。P-05cとD-04vは変更しない。

模型・解析を一本ずつ`~/jobs/jobs.py run --wait --mem --disk-path`へ渡す。CPUは前置きの上限（物理CPU数−2）と熱の条件を確認する。模型1.0GB、解析3.0GBを受付の見込みとして指定する。実測の時間と資源を各一本のresources.jsonへ保存する。

解析は既存のSME候補再生`tools/selcands_sme.py`を使用する。予測前の記憶・入力・設定・乱数、対応・答え・保留状態、学習／忘却後の記憶を全試行で元の状態記録と照合する。候補観測と記憶量の観測が状態を変えないことを確認する。元の全出力（完了印を含む）の前後のSHA-256を照合する。

旧版の残りを止めた記録時刻：2026-10-06T18:19:43.220358+09:00。完了は模型31本・解析31本。旧版の未完の条件は`plus8_support_D_w2_s001`。完了した出力と未完の出力を保存した。停止対象の稼働過程は0個。

次の一本を起動せず停止した。

```text
Traceback (most recent call last):
  File "/Users/tatsu-admin/Documents/ChatGPT/New project/codex_shop_deco_sme_2026-10-06/source/control/shop_deco_sme_2026-10-06/run_n3.py", line 112, in main
    registered(command(run, item["world"], item["seed"], item["retention"], item["level"]),
  File "/Users/tatsu-admin/Documents/ChatGPT/New project/codex_shop_deco_sme_2026-10-06/source/control/shop_deco_sme_2026-10-06/common.py", line 84, in registered
    assert peak <= mem * 1e9, f"受付の見込みを超えた: {out}"
           ^^^^^^^^^^^^^^^^^
AssertionError: 受付の見込みを超えた: /Users/tatsu-admin/Documents/ChatGPT/New project/codex_shop_deco_sme_2026-10-06/preview_n3/runs/plus8_N3_D_w2_s001

```

停止した条件と段階：`{'selection': 'N3', 'retention': 'D', 'world': 2, 'seed': 1, 'level': 'plus8', 'tag': 'plus8_N3_D_w2_s001', 'phase': 'run'}`。run.log・resources.json・validation.jsonをローカルに保存する。
