指示32のクラウド専用機械の上限変更は、このチャットへのアストラの直接承認後に適用した。対象はGoogle Cloudで関門と本番だけを走らせる専用機械。Macの既存checkout/台本・受付表・模型上限8は変更無し。

新しい専用checkoutへ最新の包みを取り出す。run_registered.py / run_registered21.py / run_registered22.py の開始前条件は、既存受付clearanceの dedicated_google_cloud_gate_and_production_machine がboolのtrueである場合だけ、走行中の模型＋出生子＋親1の上限を既存のcpu_budget=physical_cpu_count-2へする。Google Cloudの専用機械だという実確認を、既存受付の担当が最新の資源記録に加える。未確認/省略/文字列true/他機械では8を保つ。Macの台本は以前の8のまま。CPU外側＋子＋2 <= cpu_budget、物理芯−2/affinity、記憶/受付/swap10分/熱/空き、未知spawn0、同機械の原関門・正式列・全旗・版・通常push・期限の他条件は全て既存のまま。

この上限変更はクラウド専用機械の枠だけの承認。子20の開始には最大21模型/CPU22枠/初回42GiBと既存の全条件が必要。三本同時なら最大27模型/CPU30枠/初回54GiB。台本の改版を走行開始/関門合格/費用承認に置き換えず、このチャットからクラウド模型は起動しない。すでに走行中の機械のimport/台本/版/旗/観察/出力は替えない。次の新規開始にだけ最新の台本を使う。模型と観察器の固定SHA、旧結果/例外の原本は変更無し。

差分はcap.patch、3台本の前後SHAはversions.json、現行の全固定SHAはinstruction27/fixed_tools.jsonに記す。instruction32_review_onlyは以前の未適用草稿の履歴で、現行の台本はinstruction27の3ファイル。この変更だけを新しい機械へ反映する場合も、台本とfixed_tools.jsonのSHAを同時に確認する。デスクトップへの受け渡しは承認済みresults-2026-09-27の通常pushによる。
