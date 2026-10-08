"""既存の署名判定と同じ範囲を、可視の関係の索引から作る。"""


def signature_index(target, definition_graph):
    """候補側の出現も従来どおりtargetの引数型で判定する。"""
    relation_ids = {row.relation_id for row in target.relations}
    index = {}
    for row in (*target.relations, *definition_graph.relations):
        signature = (len(row.arguments), tuple(
            'relation' if argument in relation_ids else 'entity'
            for argument in row.arguments))
        index.setdefault(row.predicate, []).append(signature)
    return index


def signature_pool(vocabulary, signature, index):
    """語彙の巡回順・出現しない名前の扱いを既存の式とそろえる。"""
    return frozenset(predicate for predicate in vocabulary
                     if predicate not in index or any(
                         seen == signature for seen in index[predicate]))
