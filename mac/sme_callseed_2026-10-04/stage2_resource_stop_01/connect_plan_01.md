# 接続前の作業の区分（全走行の関門未通過、まだ接続しない）

- 段0のstage1_audit_01/summary.json passed後だけ別clone/枝codex/sme-callseed-light-2026-10-04を作る。走行中の7632f2eを変更しない。
- 新しい入口はtools/smeopt.py、smeshared.pyとv3_run.pyに旗の差し込みだけ。_Engineの式・係数・設定とabm/は変更しない。
- (a) --sme-reuse：positionsの全頂点が一意、原結果choicesが空のものだけ、512件の匿名の結果の控えから戻す。元と現のfingerprintが同じなら原の不変Resultそのものを共有。違う場合は全Candidate/Hypothesis/推論を現IDへ戻してvalidateする。真の同点/一意でない位置は本物の照合に戻す。kind/seedをまたぐのは全経路で乱数なしの証拠がある場合だけ。通常の完全なcache/cache_rng/self_cacheのキーは現の局所seedを含むまま維持。通常の控えの試行窓はこの(a)と分け、今回の(a)/(b)/鍵の測定に混ぜない（既存の案として記録に残す）。
- alias控えと統計と省いた理由をsmeshared.snapshot/restoreへ含める。元のsnapshot関数の上にflag時だけ包む（probeworldの既存の包みはruntimeのsnapshotを読む）。flagoffは新しいfalseのCTX/CFG/状態/ログを作らない。
- (b) --sme-prune：strict_bound_v2.pyの有理数の総和と上への丸めを使用。自己の点は本物を使う。N3上限<現在の最大q AND support_upper<ar._need(tau,n)の二つで省く。同点を省かない。previewのv39_graph→typed_graph→unregisterを使い、実際のmapは必ずv39.map_v39から（kindを変えない）。unsupported settings/kinds・F/Hの行の数!=n_FH・非有限の値は省略せず本物の計算へ戻す。support_upperは一対一の最大対応。本物の新しい選びは元のranked/definition_choice/passed/projectionと同じ式。
- 省いたものはsme_skippedとしてtrial/kind/version/seed/理由/元のfingerprint又は厳密な上限をログへ保存。SharedAlignmentの本物のauditへ省略メタデータを混ぜない。候補の記録の省いた行・cache/result/保存の量の違いを明記する。世界・開示・学習の記憶・頻度・最終の判断は変えない。
- 各重い処理はjobs claim/release、開始前free>=20GiB、走行中18.5GiB未満等で自分だけ停止。まず小走行13本を比較し、次に全1740を比較（新基準の判断5列と台帳本体）。一件でもmodel mismatchは修正せず案を捨て、報告して停止。
- 時間の条件を分ける：(a)だけ、(b)だけ、鍵だけ、三つを合わせる。先の二つは元の_canonicalのsource、鍵だけと合わせるものは段1通過後に2a82dc1の関数を載せたsource_key（別の枝/checkout）。flags/value/output以外を変えない。鍵だけは記録も全バイト比較できる。
- 受入済み13小走行の参考はsmall_extra_plan_01.json（13行/11個の異なる完了記録）。全1740の参考はfull_baseline_01、同点用乱数の新基準。大きな保存状態をresultsに複製しない。
