import json
from functools import lru_cache

def _canonical(labels, edges):
    """名前を含まない色つき有向図の正準形。区別不能な色を個別化して全探索。

    順つき引数を辺の色で保つ。色の細分だけで同型と決めず、残った組を
    個別化する。ID は探索の順にだけ使い、最小の符号には含めない。
    """
    incoming = [[] for _ in labels]
    outgoing = [[] for _ in labels]
    for a, b, label in edges:
        outgoing[a].append((label, b))
        incoming[b].append((label, a))

    def ranks(values):
        values = [json.dumps(v, separators=(",", ":")) for v in values]
        table = {s: i for i, s in enumerate(sorted(set(values)))}
        return tuple(table[s] for s in values)

    def refine(colors):
        while True:
            nxt = ranks([(colors[i], sorted((p, colors[j]) for p, j in outgoing[i]),
                          sorted((p, colors[j]) for p, j in incoming[i])) for i in range(len(labels))])
            if len(set(nxt)) == len(set(colors)):
                return nxt
            colors = nxt

    @lru_cache(None)
    def search(colors):
        colors = refine(colors)
        cells = {}
        for i, c in enumerate(colors):
            cells.setdefault(c, []).append(i)
        ambiguous = [(len(v), c, v) for c, v in cells.items() if len(v) > 1]
        if not ambiguous:
            order = sorted(range(len(labels)), key=colors.__getitem__)
            pos = {v: i for i, v in enumerate(order)}
            return json.dumps(([labels[v] for v in order],
                               sorted((pos[a], pos[b], p) for a, b, p in edges)), separators=(",", ":"))
        _, _, cell = min(ambiguous)
        return min(search(tuple(max(colors) + 1 if j == i else c for j, c in enumerate(colors))) for i in cell)

    return search(ranks(labels))

