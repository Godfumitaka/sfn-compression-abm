"""誕生時の答えの条件を交差集計した表を指定報告へ追記する。"""
from append_complete_report import ROOT,NAME,read,table,label,link

title='## 背景の読みの条件を記録で照合（2026-10-05）'
path=ROOT/(NAME+'.md');text=path.read_text();assert title not in text
rows=read('birth_score_conditions_summary.csv')
body=[title,
      '通常＋通常の誕生について、誕生の採点記録のHの答えと二材料のUの答えを、保持変換後の状態と交差集計した。これらのラベルは集計にだけ用いた。',
      table(['腕','誕生のH/Uの答え','F','H','U','総数'],[[label(r['arm']),r['score_condition'],*[r[k] for k in ('F','H','U','total')]] for r in rows]),
      '従来の採点のN3・世界2では、Hも二材料のUもsig_nを答える835件がすべてUになった。同じ条件のL-B・世界2・λ主の203件はすべてFだった。両腕の出生材料の集合は同一ではないので、203件と835件を一対一の介入とは扱わない。同じ出生材料の局所的な0/ℓとlog Pの比較は先行報告の三例で行った。',
      '一方、従来採点でUが二材料ともsig_nを答えてもHがsig_nを答えない291件はFで残った。F→H→Uという一段ずつの変換では、Uの費用が0でもF→Hの増加費用が0とは限らない。「既定のsig_nが当たる」という条件に加え、Hも正しく答える場合に、名前を持つ局所的な費用差が0になるという読みがこの記録に対応する。',
      '具体的にはN3・世界2・種1・試行1の通常＋通常の誕生（R_f35c5fd29759b79e、シール席2）は、Uの答えが二材料ともsig_n、Hの履歴が空でHは黙りだった。記録のrF=0、rH=5、rU旧=rU今=0。候補のRH−RF=7.052270534、ΔC_FH=6、V_FH=1.175378422で、λ主を上回りFが残った。',
      link('birth_score_conditions.csv','全6177件の通常＋通常のシールの採点と識別子')+'、'+link('birth_score_conditions_per_seed.csv','種ごとの交差集計')+'、'+link('birth_score_conditions_summary.csv','20種の集計')+'。この補足も保存済みの誕生採点を読むだけで、模型の再走行は行っていない。']
path.write_text(text+'\n'+'\n\n'.join(body)+'\n')
print(path)
