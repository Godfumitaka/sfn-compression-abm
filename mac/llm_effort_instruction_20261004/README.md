# 今回の記録

報告：`control/2026-10-04_LLMの確かめ_考える量_Codex.md`。費用帳簿の今回32行も報告本文に載せている。

既存mediumの最後の16問と、条件A・Bの最後の16問を並べた記録。既存mediumの`trials.jsonl`には学習40行もそのまま残すが、比較集計は最後の試験だけを対象とする。A・Bは学習を実行していない。

- `scope.json`：条件・指定・単価・記号の一致の決め方。
- `offline_checks.json`：既存の履歴・問い・要求と、変更範囲の照合。
- `aggregate.json`：通常・例外、場合、答え方、確信、使用量と費用。
- `seal_summary_matching.tsv`／`.json`：48問の要約の一致数と指紋。
- `{baseline,A,B}/summaries/qNN.txt`：要約の全文。空の要約は空ファイル。対応するJSONに返り方を記録。
- `{A,B}/requests.jsonl`：実際に送った要求本体。
- `{A,B}/responses/`：識別欄を除いたAPIの応答。thinkingはsummarizedの指定で返った要約。
- `{A,B}/budget_events.jsonl`：各要求の最大費用の確保と確定費用。
- `ledger_before.json`：開始前の既存帳簿の長さ・指紋。
- `費用_今回.jsonl`：既存帳簿に追記した今回32行の写し。
- `execution_audit.json`：帳簿・試行・要求の照合。
- `design_estimates.json`：未実行三案の設計値・費用の仮定と計算。
- `source_73876dc.tar.gz`：使ったコードと関連仕様の保存用アーカイブ。
- `scripts/`：準備・実行・見積もり・集計の道具。

元の実行場所は `$WORKSPACE/codex_llm_effort_2026-10-04/`。`python3.12 report.py`と`python3.12 design_estimates.py`はAPIを呼ばない。保存したscriptsでも、このマックの前担当のコードの場所を参照して再集計できる。実行スクリプトは実行済みの条件を再送しないための停止を入れてある。新しい生成の委任として自動で使わない。

公開用の記録はsignature・応答ID・個人のローカルパスを除く。保存したscriptsの帳簿の場所は環境変数LLM_LEDGER_PATHで指定する。元の未公開記録はローカルで保持する。
