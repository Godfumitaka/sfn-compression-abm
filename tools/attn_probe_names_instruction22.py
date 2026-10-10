"""指示22：実入力・実開示の名の受領時点を、固定試験のassertへ合わせる。

観察の学習・頻度・注意を進めず、試験の間だけ名前集合の写しを使う。
頻度表や固定試験の提示から名前を補わず、元の三つのassertを残す。
"""
from copy import copy


def install(attention):
    import abm.loop as loop
    from abm.domains import RevealedEdge
    import useforget_evaluation as evaluation

    receipts = {}
    native_input = loop._agent_input
    native_update = loop.update
    native_probe = attention.ST['predict_probe']

    def agent_input(trial, before):
        ai = native_input(trial, before)
        if not evaluation.active():
            # 元の入力口が既に本人へ渡した可視辺だけ。隠した辺は読まない。
            receipts[attention.ST['agent']] = {
                'trial': attention.ST['trial'],
                'names': {relation.predicate for relation in ai.target_graph_partial.relations},
            }
        return ai

    def update(pending, feedback):
        result = native_update(pending, feedback)
        if not evaluation.active() and isinstance(feedback, RevealedEdge):
            # 元の更新が受け取った実開示だけ。予測口へFeedbackを渡さない。
            receipt = receipts[attention.ST['agent']]
            if receipt['trial'] != attention.ST['trial']:
                raise RuntimeError('実開示と実入力の受領試行が異なる')
            receipt['names'].add(feedback.edge.predicate)
        return result

    def predict_probe(*args, **kwargs):
        original = attention.ST['individual']
        receipt = receipts.get(attention.ST['agent'])
        if receipt is None or receipt['trial'] != attention.ST['trial']:
            raise RuntimeError('固定試験に対応する実入力の受領記録がない')
        observation = copy(original['observations'])
        observation.names = original['observations'].names | receipt['names']
        individual = dict(original, observations=observation)
        try:
            attention.ST['individual'] = individual
            return native_probe(*args, **kwargs)
        finally:
            attention.ST['individual'] = original

    loop._agent_input = agent_input
    loop.update = update
    attention.ST['predict_probe'] = predict_probe
    # 構造検査用の受領口。模型の状態・研究者の正解や記録を参照しない。
    return receipts
