"""照合器の検査（2026-10-01 朝の委任書「照合の直し（親子の並行連結）と照合器の検査」の 3-1・3-2）。★ 検査だけ。模型は変えない。
基準（総当たり）：関係 6 本以下の小さなグラフの対について、基の行ごとに「相手の行のどれか、又は対にしない」をすべて数え上げ、次を満たす写像のうち、
  点が最大のものの集合を基準とする。
  ・同一性：対 (l, r) は、述語が同じ・引数の数が同じ・引数の種類が合う（物↔物、関係↔関係、関係↔相手に見えていない ID）ときだけ
    （abm/sme.py:280-323 の候補の作り方と同じ条件）。
  ・一対一：関係（対と、対が引数で含意する子の対応 relation_pairs を合わせて）も物（entity_pairs）も、関数かつ単射。
  ・物の対応の一貫：同じ基の物が二つの相手に、又は二つの基の物が同じ相手に写らない（一対一に含まれる）。
  ・並行連結（tools/strictpc.py の決まり）：対 (l, r) の子の対応 (l_c, r_c) で、r_c が相手に見えている関係なら、(l_c, r_c) 自体が対として写像にある。
  ・点：abm/sme.py:157-166 の式をそのまま写す（重みは SMEParams の既定）。
      点 ＝ 4.0 × 対の数 ＋ 1.0 × Σ（対ごとの entity_pairs の数 ＋ relation_pairs の数）＋ 2.0 × 体系性 − 0.25 × 写らない基の関係の数
      体系性 ＝ 関係の写像（対と子の対応）のうち、両側とも見えている関係の (l, r) について、引数の位置ごとに「写像(l の引数) ＝ r の引数」の数。
      写らない基の関係 ＝ 関係の写像（対と子の対応）の鍵に無い基の関係。
突き合わせ：照合器（この作業場所の abm.sme.map_graphs。tools/fixorder2.py・fix2・v39 の候補・ustruct・--strict-pc を入れた本番の差し替えの状態）の
  写像（関係と物）を、基準と比べる。
  ・一致（唯一の最大）・共通部分と一致（最大が複数で、照合器の写像がそれらの共通部分）・最大の一つと一致（共通部分ではない）・食い違い。
  ・あわせて、照合器の点（alignment.total_score）と、上の式で照合器の写像から計算し直した点が同じか（式の写しの確かめ）。
例：手で作った例（T1〜T5 と幾つか）と、乱数で作った例（述語・物・高さを少しずつ変える）。食い違う例は、小さい順に残す。
使い方  SW_TREE=<作業場所> SW_FLAGS=u_struct,relearn_init,tie_struct,amb_local python3.12 tools/matcher_audit.py <出力の .json> [乱数の例の数（既定 400）]"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.expanduser("~/sw_audit"))
import swcommon as sw  # noqa: E402,F401  （本番と同じ差し替えを入れる）
import abm.sme as sme  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402
import strictpc  # noqa: E402

W = sme.SMEParams()


def G(gid, ents, rels):
    return RelationGraph(gid, tuple(Entity(e) for e in ents), tuple(Relation(i, p, tuple(a)) for i, p, a in rels))


def pairs_of(l, r, bids, tids, tents):
    """対 (l, r) の entity_pairs と relation_pairs。種類が合わなければ None（abm/sme.py:290-311 と同じ）。"""
    if l.predicate != r.predicate or len(l.arguments) != len(r.arguments):
        return None
    ep, rp = [], []
    for la, ra in zip(l.arguments, r.arguments):
        lrel = la in bids
        rrel = ra in tids
        unobs = (not rrel) and (ra not in tents)
        if lrel and unobs:
            rp.append((la, ra))
            continue
        if lrel != rrel:
            return None
        (rp if lrel else ep).append((la, ra))
    return ep, rp


def score(B, T, pairs):
    """pairs：[(l, r, ep, rp)]。abm/sme.py:157-166 の式。"""
    bids = {r.relation_id: r for r in B.relations}
    tids = {r.relation_id: r for r in T.relations}
    rm = {}
    for l, r, ep, rp in pairs:
        for a, b in rp:
            rm[a] = b
        rm[l] = r
    sysm = 0
    for l, r in rm.items():
        if l in bids and r in tids:
            for la, ra in zip(bids[l].arguments, tids[r].arguments):
                if rm.get(la) == ra:
                    sysm += 1
    unmatched = sum(1 for x in B.relations if x.relation_id not in rm)
    arg = sum(len(ep) + len(rp) for _l, _r, ep, rp in pairs)
    return W.predicate_match_weight * len(pairs) + W.argument_consistency_weight * arg + W.higher_order_weight * sysm \
        - W.unmatched_penalty * unmatched, rm


def reference(B, T):
    bids = {r.relation_id for r in B.relations}
    tids = {r.relation_id for r in T.relations}
    tents = {e.entity_id for e in T.entities}
    brels = list(B.relations)
    opts = []
    for l in brels:
        o = [None]
        for r in T.relations:
            pr = pairs_of(l, r, bids, tids, tents)
            if pr is not None:
                o.append((r.relation_id, pr[0], pr[1]))
        opts.append(o)
    best = []
    best_s = None

    def rec(i, chosen, rmap, rinv, emap, einv):
        nonlocal best, best_s
        if i == len(brels):
            pairs = [(l, r, ep, rp) for l, r, ep, rp in chosen]
            have = {(l, r) for l, r, _e, _r in pairs}
            for l, r, ep, rp in pairs:
                for lc, rc in rp:
                    if rc in tids and (lc, rc) not in have:
                        return
            s, rm = score(B, T, pairs)
            em = dict(emap)
            key = (frozenset(rm.items()), frozenset(em.items()))
            if best_s is None or s > best_s + 1e-12:
                best, best_s = [key], s
            elif abs(s - best_s) <= 1e-12 and key not in best:
                best.append(key)
            return
        l = brels[i].relation_id
        for o in opts[i]:
            if o is None:
                rec(i + 1, chosen, rmap, rinv, emap, einv)
                continue
            r, ep, rp = o
            new_r = [(l, r)] + list(rp)
            nr, ni = dict(rmap), dict(rinv)
            ok = True
            for a, b in new_r:
                if (a in nr and nr[a] != b) or (b in ni and ni[b] != a):
                    ok = False
                    break
                nr[a] = b
                ni[b] = a
            if not ok:
                continue
            ne, nei = dict(emap), dict(einv)
            for a, b in ep:
                if (a in ne and ne[a] != b) or (b in nei and nei[b] != a):
                    ok = False
                    break
                ne[a] = b
                nei[b] = a
            if not ok:
                continue
            rec(i + 1, chosen + [(l, r, ep, rp)], nr, ni, ne, nei)

    rec(0, [], {}, {}, {}, {})
    return best, best_s


def compare(B, T):
    al = sme.map_graphs(B, T).alignment
    m = (frozenset(al.relation_mapping.items()), frozenset(al.entity_mapping.items()))
    best, bs = reference(B, T)
    # 照合器の写像から点を計算し直す（式の写しの確かめ）
    res = sme.map_graphs(B, T)
    pairs = [(c.base_relation_id, c.partial_relation_id, c.entity_pairs, c.relation_pairs) for c in res.candidates]
    s_re, _ = score(B, T, pairs)
    common = (frozenset.intersection(*[b[0] for b in best]), frozenset.intersection(*[b[1] for b in best])) if best else None
    if len(best) == 1 and m == best[0]:
        verdict = "一致（唯一の最大）"
    elif len(best) > 1 and m == common:
        verdict = "共通部分と一致"
    elif m in best:
        verdict = "最大の一つと一致（共通部分ではない）"
    else:
        verdict = "食い違い"
        mr, me = m
        if mr == common[0] and me < common[1]:
            verdict = "食い違い：関係は共通部分と同じ・物が共通部分より少ない"
        elif mr < common[0]:
            verdict = "食い違い：関係が共通部分より少ない"
        elif mr > common[0]:
            verdict = "食い違い：関係が共通部分より多い"
        else:
            verdict = "食い違い：関係が共通部分と別"
    return {"判定": verdict, "照合器の点": al.total_score, "式で計算し直した点": s_re, "点の式が同じ": abs(al.total_score - s_re) < 1e-9,
            "基準の点": bs, "基準の数": len(best), "照合器の関係": dict(al.relation_mapping), "照合器の物": dict(al.entity_mapping),
            "基準の関係": [dict(b[0]) for b in best][:4], "基準の物": [dict(b[1]) for b in best][:4],
            "共通部分の関係": dict(common[0]) if common else None}


def hand_cases():
    T1B = [("c1", "hold", "ab"), ("c2", "wrap", "ab"), ("P", "P", ("c1", "c2"))]
    return {
        "T1": (T1B, "ab", [("d1", "push", "xy"), ("d2", "wrap", "xy"), ("Q", "P", ("d1", "d2"))], "xy"),
        "T2": ([("c1", "hold", "ab"), ("c2", "push", "ab"), ("P", "P", ("c1", "c2"))], "ab",
               [("d1", "push", "xy"), ("d2", "hold", "xy"), ("Q", "P", ("d1", "d2"))], "xy"),
        "T4": (T1B, "ab", [("d2", "wrap", "xy"), ("Q", "P", ("dHIDDEN", "d2"))], "xy"),
        "T5": ([("c1", "hold", "ab"), ("m1", "M", ("c1", "c1")), ("c2", "wrap", "ab"), ("P", "P", ("m1", "c2"))], "ab",
               [("d1", "push", "xy"), ("n1", "N", ("d1", "d1")), ("d2", "wrap", "xy"), ("Q", "P", ("n1", "d2"))], "xy"),
        "対称（同じ名の子が二本）": ([("c1", "p", "ab"), ("c2", "p", "ab"), ("P", "P", ("c1", "c2"))], "ab",
                          [("d1", "p", "xy"), ("d2", "p", "xy"), ("Q", "P", ("d1", "d2"))], "xy"),
        "物の取り合い": ([("c1", "p", "ab"), ("c2", "q", "ac")], "abc", [("d1", "p", "xy"), ("d2", "q", "zy")], "xyz"),
        "向きの入れ替え": ([("c1", "p", "ab"), ("c2", "p", "ba")], "ab", [("d1", "p", "xy")], "xy"),
        "親だけ合う（子は伏せ）": ([("c1", "p", "ab"), ("c2", "q", "ab"), ("P", "P", ("c1", "c2"))], "ab",
                         [("Q", "P", ("h1", "h2"))], "xy"),
    }


def rand_case(rng):
    """述語・物・高さを少しずつ変えた対。基：物 2〜3、一階 2〜4 本（述語 p・q・r）、高階 0〜2 本（P・Q、引数は前の関係 2 本）。
    相手：基を写して、述語を確率 0.2 で替え、関係を確率 0.15 で伏せ（親の引数には ID が残る）、物を入れ替え、一階を一本足すことがある。合計 6 本以下。"""
    ne = rng.choice((2, 3))
    ents = "abc"[:ne]
    rels = []
    for i in range(rng.randint(2, 4)):
        a, b = rng.sample(ents, 2)
        rels.append((f"c{i}", rng.choice("pqr"), (a, b)))
    for j in range(rng.randint(0, 2)):
        if len(rels) >= 6:
            break
        x, y = rng.sample([r[0] for r in rels], 2)
        rels.append((f"H{j}", rng.choice("PQ"), (x, y)))
    emap = dict(zip(ents, rng.sample("xyz"[:ne], ne)))
    tr = []
    hidden = set()
    for rid, p, args in rels:
        nid = "t" + rid
        if rng.random() < 0.15 and not rid.startswith("H"):
            hidden.add(nid)
            continue
        p2 = p if rng.random() >= 0.2 else rng.choice("pqr" if p.islower() else "PQ")
        a2 = tuple(emap[a] if a in emap else "t" + a for a in args)
        tr.append((nid, p2, a2))
    if rng.random() < 0.3 and len(tr) < 6:
        a, b = rng.sample("xyz"[:ne], 2)
        tr.append(("tx", rng.choice("pqr"), (a, b)))
    return rels, ents, tr, "xyz"[:ne]


def main():
    out = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    sw.setup()
    strictpc.install()
    res = {"手で作った例": {}, "乱数の例": {"数": {}, "食い違いの例": [], "点の式が違う例": []}}
    for k, (b, be, t, te) in hand_cases().items():
        B, T = G("b", be, b), G("t", te, t)
        res["手で作った例"][k] = {"基": b, "相手": t, **compare(B, T)}
    rng = random.Random(20261001)
    from collections import Counter
    cnt = Counter()
    bad = []
    for i in range(n):
        b, be, t, te = rand_case(rng)
        B, T = G("b", be, b), G("t", te, t)
        c = compare(B, T)
        cnt[c["判定"]] += 1
        cnt["点の式が同じ"] += c["点の式が同じ"]
        if c["判定"].startswith("食い違い") or c["判定"].startswith("最大の一つ"):
            bad.append((len(b) + len(t), i, {"基": b, "相手": t, **c}))
        if not c["点の式が同じ"]:
            res["乱数の例"]["点の式が違う例"].append({"基": b, "相手": t, **c})
    bad.sort(key=lambda x: (x[0], x[1]))
    res["乱数の例"]["数"] = dict(cnt)
    res["乱数の例"]["食い違いの例"] = [x[2] for x in bad[:30]]
    res["乱数の例"]["食い違い・共通部分でない例の数"] = len(bad)
    res["strictpc"] = strictpc.stats()
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    for k, v in res["手で作った例"].items():
        print(k, v["判定"], "点", v["照合器の点"], "基準", v["基準の点"], v["基準の数"])
    print(dict(cnt), "残した例", len(bad))


if __name__ == "__main__":
    main()
