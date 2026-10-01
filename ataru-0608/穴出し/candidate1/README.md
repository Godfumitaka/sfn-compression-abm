# 候補 1（機械による台帳の相違）の比べのための、デスクトップの台帳一本 — 走行の係

- 頼み：control/2026-10-01_穴出しと集団化_Codex.md の候補 1（Codex）。走らせ直しはしていない。既存の走行の写し。
- 走行：fg_f050_A_L50（f を振る格子、お店の世界 2・A・λ＝--e-price＝0.01873710622997919・f＝0.5・種 1・1,740 試行）、コード 88e0e38、並列 14。
- ファイル：
  - seed001.jsonl.gz：台帳（見出しを含む、圧縮のまま）。seed001.done。
  - flag.json：旗の全部。manifest_seed001.json：その種の manifest の行（world_hash・code_commit など）。
  - side/：同じ種の記録（answers・ambig・jsonl・cfvalue・probe・routing・shop。大きいものは gzip）。
  - environment.json：台帳本体の sha256、Python の版、OS の情報。
- 台帳本体の sha256（見出しの一行を除く）は bcb3bcf0aabdf9e2eb56b5271214973c8da56798de38f2197e7b845c6ff13f68。
  - 関門の基の走行（bc5cd13、~/sfn/audit/_dev/uf_gate_bc5cd13/base、並列 1）の台帳本体とも同じ値。
    - その走行の --e-price と --v39-price は 0.0187371（丸めた値）だった。
  - つまりデスクトップの中では、コード（bc5cd13／88e0e38）、並列（1／14）、λ の書き方（0.0187371／0.01873710622997919）が違っても、同じ台帳本体になった。
