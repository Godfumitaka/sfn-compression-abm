"""選別には使わず、既定設定の点の厳密な上限だけを外で計算する。"""
from fractions import Fraction


def upper_score(left, right, settings):
    # 検査済みの本番の係数に限る。係数を選び直さない。
    if settings.same_functor != 0.0005 or settings.same_function != 0.0002 or settings.trickle_down != 8.0:
        raise ValueError('上限の証明の対象は既定の三係数だけ')
    if settings.max_local_score is not None:
        raise ValueError('上限の証明の対象は上限なしの既定設定だけ')

    def one_side(graph, other):
        parents = {n.key: [] for n in graph.nodes}
        for node in graph.nodes:
            for child in node.args or ():
                parents[child].append(node.key)  # 同じ子への引数の重複も保つ。
        by = graph.by_id
        values = {}

        def visit(key):
            if key in values:
                return values[key]
            node = by[key]
            local = 0.0
            if node.kind not in ('entity', 'unknown') and node.state != 'U':
                if any(node.names & v.names for v in other.nodes if v.kind == node.kind and v.state != 'U'):
                    local = settings.same_functor
                elif node.kind == 'function' and any(v.kind == 'function' and v.state != 'U' for v in other.nodes):
                    local = settings.same_function
            # 正の有限の値の丸めを各演算で2倍まで見込む、緩い上限。
            values[key] = 2 * Fraction(local) + 8 * Fraction(settings.trickle_down) * sum((visit(p) for p in parents[key]), Fraction())
            return values[key]

        return 2 * sum((visit(n.key) for n in graph.nodes), Fraction())

    return min(one_side(left, right), one_side(right, left))


def upper_n3(left, right, settings, self_left, self_right):
    denominator = Fraction(self_left) + Fraction(self_right)
    if denominator <= 0:
        return None
    return 2 * upper_score(left, right, settings) / denominator
