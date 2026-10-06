"""予測とEで使う逐語の場面の選びが分かれる、手で確率を与えた小例。"""
from pathlib import Path
from dataclasses import replace
import json
import sys

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'source/tools'), str(ROOT/'source')]
from sme2017 import Graph, Matcher
from cstar_matcher import CstarMatcher, validate
from test_cstar_fixed import toy

scene = toy()
trace_a = Graph(tuple(replace(n, names=frozenset({'sig_n'})) if n.key == 'seal' else n for n in scene.nodes))
trace_b = Graph(tuple(n for n in scene.nodes if n.key != 'link'))
old = Matcher(tie_seed=4107, tie_uniform=True)
new = CstarMatcher(tie_seed=4107, tie_uniform=True)
rows = []
for label, graph, probability in [('逐語A：全構造・sig_n', trace_a, .45),
                                   ('逐語B：linkなし・sig_e', trace_b, .95)]:
    # 指定のおもちゃと同じく、シール以外のqを1として固定する。
    distributions = {n.key: {next(iter(n.names)):1.0} for n in graph.nodes if n.kind == 'relation'}
    distributions['seal'] = {'sig_e':probability, 'sig_n':1-probability}
    a = old.match(graph, scene, tie_seed=4107)
    b = new.match(graph, scene, probabilities=distributions, tie_seed=4107)
    assert validate(graph, scene, b)
    rows.append({'trace':label,'old_score':a.best.score,'cstar_score':b.best.score,
                 'old_mapping':a.best.relation_mapping,'cstar_mapping':b.best.relation_mapping,
                 'supplied_q':distributions})
record = {'kind':'synthetic_component_only','world_run':False,
          'scene':'指定のおもちゃのsig_eの提示', 'rows':rows,
          'old_selected':max(rows,key=lambda x:x['old_score'])['trace'],
          'cstar_selected':max(rows,key=lambda x:x['cstar_score'])['trace'],
          'scope_question':'予測の逐語の選びを保つか、EがC*で逐語の場面から選び直すか',
          'choices':['予測の逐語を保ち、同じ二材料にE側の照合を適用',
                     'E用の逐語を全候補から選び、二材料をE側の選びで決める']}
assert record['old_selected'] != record['cstar_selected']
(ROOT/'material_scope_example_01.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(record,ensure_ascii=False,indent=2))
