実装前の根拠と関門の範囲。

1. reuse/pruneは旧c7a2949の実装のまま移す。唯一の適合はcache_rngのpolicyを(a)のcall-seed-uniform-v1にすること。式と上限は変えない。省略のside記録を隠さない。旧関門は台帳だけで、今回のsideの一致が通らない可能性がある。不通の案はそれ以上全走行しない。
2. 不変の部分の実体の共有：sme2017.HypothesisとCandidateはfrozen dataclass。全ての子は文字列、整数、float、None、tupleと整数frozenset。exactは再帰で型と全ての順つきの値を確認し、floatはIEEE754の8バイトを比べる。未対応の型は同一視しない。
3. 本来の_Engine.runが全部終わった後でのみhypotheses/candidatesを既存の実体に置く。乱数は本来の回数だけ実行済み。選ばれた番号、同点の組、choices、fingerprint、settingsは変えない。実体のidを記録する模型の経路は無い。smereplay.encodeは型・フィールド・順つきの内容を記録し、参照番号は記録しない。
4. 論理的なcache/RESULTS/GRAPHS/CHOICES/STATSの項目は一つも消さない。共有を探す表だけ512組に抑え、古い作業用の参照を外す。古い本来の照合結果は元のcacheに残る。表の寿命の違いは共有の有無にだけ影響し、式・選び・乱数・記録の内容に影響しない。
5. この根拠とは別に、旗なし・reuse・prune・実体共有を(a)とlog Pの200試行で、台帳本体・全side・全保存状態・毎試行の同点の乱数と控えの印・全控えの終わりの保存の圧縮バイトで検査する。通った案だけ1740試行へ。sec_trialと見出し一行だけ除く。模型の値の変更は許さない。
