"""段 3：本番の場面での総当たりとの突き合わせ（2026-10-01 午前の返事の段 3。記録だけ）。★ 読むだけ。
材料：--strict-pc（段 1 の後）・--answer-gap つきの走行で、環境変数 STRICTPC_PAIRDUMP が書いた組（予測で選ばれた定義の照合のグラフと提示の場面、
  照合の前の候補の一覧（直しの前）、照合器の写像と点）。tools/strictpc.py _pairdump。
基準（tools/matcher_audit.py と同じ考え方を、本番の名前の条件に合わせたもの）：
  ・同一性：対は、照合の前の候補の一覧（F・H・U の名前の条件と引数の種類を含む、本番の候補の作り方そのもの）にあるものだけ。
  ・一対一（関係：対とその子の対応を合わせて、物：entity_pairs）。
  ・並行連結：対の子の対応 (l_c, r_c) で r_c が見えている関係なら、l_c が照合のグラフの行なら (l_c, r_c) が対として写像にあり、
    l_c が U の席なら (c)（引数の数と種類が合い、その子にも同じ決まり）。
  ・点：abm/sme.py:157-166 の式（tools/matcher_audit.py score と同じ）。
  総当たりは、一組 10 秒で打ち切る（打ち切った組は数えて除く）。走行ごとに、記録の全体から等間隔に 150 組を選ぶ（二本で 300 組。仮の決定）。
  打ち切った組は、その次の組で置き換えない（打ち切った数を書く）。
使い方  python3.12 tools/matcher_audit_prod.py <出力の .json> <名前>=<pairs.jsonl> …"""
import json
import sys
import time
from collections import Counter

W4, W1, W2, WU = 4.0, 1.0, 2.0, 0.25
LIMIT = 10.0
PER_RUN = 150


class Timeout(Exception):
    pass


def reference(rec):
    base = {r[0]: r for r in rec["基"]}
    tgt = {r[0]: r for r in rec["相手"]}
    tents = set(rec["相手の物"])
    urows = {r[0]: r for r in rec["U の席"]}
    def_ids = set(base) | set(urows)
    opts = {}
    for l, r, ep, rp in rec["候補（直しの前）"]:
        opts.setdefault(l, []).append((r, [tuple(x) for x in ep], [tuple(x) for x in rp]))
    rows = sorted(base, key=lambda l: len(opts.get(l, [])))
    t0 = time.time()

    def u_ok(lc, rc, chosen_pairs):
        u = urows.get(lc)
        if u is None:
            return False
        C = tgt[rc]
        if len(u[2]) != len(C[2]):
            return False
        for ua, ca in zip(u[2], C[2]):
            ua_rel = ua in def_ids
            ca_rel = ca in tgt
            ca_unobs = (not ca_rel) and (ca not in tents)
            if ua_rel and (ca_rel or ca_unobs):
                if ca_rel and not child_ok(ua, ca, chosen_pairs):
                    return False
            elif ua_rel or ca_rel or ca_unobs:
                return False
        return True

    def child_ok(lc, rc, chosen_pairs):
        if rc not in tgt:
            return True
        if lc in base:
            return (lc, rc) in chosen_pairs
        return u_ok(lc, rc, chosen_pairs)

    best, best_s = [], None
    nodes = [0]

    def score(pairs):
        rm = {}
        for l, r, ep, rp in pairs:
            for a, b in rp:
                rm[a] = b
            rm[l] = r
        sysm = 0
        for l, r in rm.items():
            if l in base and r in tgt:
                for la, ra in zip(base[l][2], tgt[r][2]):
                    if rm.get(la) == ra:
                        sysm += 1
        unmatched = sum(1 for x in base if x not in rm)
        arg = sum(len(ep) + len(rp) for _l, _r, ep, rp in pairs)
        return W4 * len(pairs) + W1 * arg + W2 * sysm - WU * unmatched, rm

    def rec_(i, chosen, rmap, rinv, emap, einv):
        nonlocal best, best_s
        nodes[0] += 1
        if nodes[0] % 2000 == 0 and time.time() - t0 > LIMIT:
            raise Timeout
        if i == len(rows):
            have = {(l, r) for l, r, _e, _p in chosen}
            for l, r, ep, rp in chosen:
                for lc, rc in rp:
                    if not child_ok(lc, rc, have):
                        return
            s, rm = score(chosen)
            key = (frozenset(rm.items()), frozenset(emap.items()))
            if best_s is None or s > best_s + 1e-9:
                best, best_s = [key], s
            elif abs(s - best_s) <= 1e-9 and key not in best:
                best.append(key)
            return
        l = rows[i]
        rec_(i + 1, chosen, rmap, rinv, emap, einv)
        for r, ep, rp in opts.get(l, []):
            nr, ni = dict(rmap), dict(rinv)
            ok = True
            for a, b in [(l, r)] + rp:
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
            rec_(i + 1, chosen + [(l, r, ep, rp)], nr, ni, ne, nei)

    rec_(0, [], {}, {}, {}, {})
    return best, best_s, time.time() - t0


def classify(rec, best):
    m = (frozenset(rec["照合器の関係"].items()), frozenset(rec["照合器の物"].items()))
    common = (frozenset.intersection(*[b[0] for b in best]), frozenset.intersection(*[b[1] for b in best]))
    if len(best) == 1 and m == best[0]:
        return "一致（唯一の最大）"
    if len(best) > 1 and m == common:
        return "共通部分と一致"
    if m in best:
        return "最大の一つと一致（共通部分ではない）"
    mr, me = m
    if mr == common[0] and me < common[1]:
        return "食い違い：関係は共通部分と同じ・物が共通部分より少ない"
    if mr == common[0] and me > common[1]:
        return "食い違い：関係は共通部分と同じ・物が共通部分より多い"
    if mr == common[0]:
        return "食い違い：関係は共通部分と同じ・物が別"
    if mr < common[0]:
        return "食い違い：関係が共通部分より少ない"
    if mr > common[0]:
        return "食い違い：関係が共通部分より多い"
    return "食い違い：関係が共通部分と別"


def main():
    out = sys.argv[1]
    res = {}
    for spec in sys.argv[2:]:
        name, path = spec.split("=", 1)
        c = Counter()
        ex = {}
        sizes = Counter()
        done = 0
        timeouts = 0
        seen = 0
        lines = open(path, encoding="utf-8").read().splitlines()
        step = max(1, len(lines) // PER_RUN)
        picks = lines[::step][:PER_RUN]
        size = Counter()
        for line in picks:
            rec = json.loads(line)
            seen += 1
            nopt = Counter(c[0] for c in rec["候補（直しの前）"])
            size["基の行"] += len(rec["基"])
            size["相手の関係"] += len(rec["相手"])
            size["候補"] += len(rec["候補（直しの前）"])
            size["候補が二つ以上ある基の行"] += sum(1 for v in nopt.values() if v >= 2)
            try:
                best, bs, sec = reference(rec)
            except Timeout:
                timeouts += 1
                sizes["打ち切り：基の行 %d" % len(rec["基"])] += 1
                continue
            done += 1
            k = classify(rec, best)
            c[k] += 1
            if k.startswith("食い違い") and (k not in ex or len(rec["基"]) + len(rec["相手"]) < ex[k]["大きさ"]):
                ex[k] = {"大きさ": len(rec["基"]) + len(rec["相手"]), "基の行": len(rec["基"]), "照合器の点": rec["照合器の点"], "基準の点": bs,
                         "基準の数": len(best), "照合器の関係": rec["照合器の関係"], "基準の共通部分の関係": dict(frozenset.intersection(*[b[0] for b in best])),
                         "照合器の物": rec["照合器の物"], "基準の共通部分の物": dict(frozenset.intersection(*[b[1] for b in best])),
                         "基": rec["基"], "U の席": rec["U の席"], "相手": rec["相手"]}
        res[name] = {"記録の組": len(lines), "見た組": seen, "突き合わせた組": done,
                     "一組あたりの平均": {k: round(v / max(seen, 1), 2) for k, v in size.items()}, "打ち切った組（10 秒）": timeouts, "判定": dict(c), "打ち切った組の大きさ": dict(sizes),
                     "食い違いの形ごとのいちばん小さい例": ex}
        print(name, seen, done, timeouts, dict(c), flush=True)
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
