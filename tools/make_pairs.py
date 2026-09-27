"""世界ごとの「またぎの組の表」を種ファイルから作る（2026-09-27、委任書 5「世界を横に広げる」の材料）。読むだけ（種は変えない）。
規則（analysis_sbe_2026-09-19/pairs252_v3a2.json と同じ集まりになることを確かめた規則。所見記録_2026-09-20.md:1268-1273, 1301-1307）：
  媒介の層の述語を除いた述語の組 (a, b)（辞書順、無向）のうち、それぞれが出るモチーフの集まりが「交わるが等しくない」もの。
出力は [[a, b], ...]（辞書順）。grp.py の PAIRS と同じく、読む側は tuple(sorted(x)) の集まりとして使う。
使い方  python3.12 tools/make_pairs.py <種ファイル> <出力 json> [--check <比べる表の json>]"""
import collections, itertools, json, sys

a = sys.argv[1:]
chk = a[a.index("--check") + 1] if "--check" in a else None
seedf, out = a[0], a[1]
d = json.load(open(seedf, encoding="utf-8"))
ms = collections.defaultdict(set); lay = collections.defaultdict(set)
for c in d["constituents"]:
    ms[c["predicate"]].add(c["motif"]); lay[c["predicate"]].add(c["layer"])
preds = sorted(x for x in ms if "媒介" not in lay[x])
pairs = sorted([a_, b_] for a_, b_ in itertools.combinations(preds, 2) if ms[a_] & ms[b_] and ms[a_] != ms[b_])
json.dump(pairs, open(out, "w", encoding="utf-8"), ensure_ascii=False)
print(f"{seedf}：述語（媒介を除く）{len(preds)}・モチーフ {len({m for s in ms.values() for m in s})}・組 {len(pairs)} -> {out}")
if chk:
    ref = {tuple(sorted(x)) for x in json.load(open(chk, encoding="utf-8"))}
    got = {tuple(x) for x in pairs}
    print(f"  {chk} と比べる：同じ {got == ref}（表 {len(ref)}・作った {len(got)}）")
    if got != ref:
        sys.exit(3)
