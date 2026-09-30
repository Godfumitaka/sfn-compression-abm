# 集団化 urta の重複箇所（2026-09-30、Codex）

土台は v3.10urta-main（74b60da）。集団化は v3.11ch-main（eeb524c）。指定の四つの直しを持つ土台へ、集団化の差分を適用した。

| ファイル・処理 | 内容 |
|---|---|
| tools/v3_run.py | 旗の導入順と flag.json の二か所で競合。集団化の m1 の後に relearninit の場面記録を入れ、受信も包んだ。四つの旗と集団化の記録を両方保持。 |
| tools/v311c.py receive_one | U→H の新世代の初期評価を通常採点と区別。post がゼロ、通常採点回数 n_scored が0のときだけ認める。 |
| tools/v311c.py probe | histrole・ustruct・relearninit・tiestruct の記録を回答一致試験の前後で保存・復元。 |
| tools/ustruct.py・relearninit.py・tiestruct.py・v39.py・v310be.py・histrole.py、abm/ | 指定の土台の内容を変更していない。 |

m1 は、二つの材料場面から定義を新しく作るか既存へ取り込む関数。post は、誕生・覚え直しの初期値とは別の、その後の通常採点の記録。

u-2026-09-30 側と共通する場所は運転部 tools/v3_run.py、および集団化が呼ぶ U の照合・覚え直し・同点・候補ごとの棄権の関数。土台の指定タグ後の u-2026-09-30 の変更は取り込んでいない。
