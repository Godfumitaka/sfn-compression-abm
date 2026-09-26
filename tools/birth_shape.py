"""読むだけ（2026-09-25）：台帳の誕生の登録イベントから、生まれたときの行数と、行どうしのつながりを数える。★ 判定しない。
つながり ＝ 定義の中で、引数（実体か関係 ID）を一つ以上ほかの行と共有している行の割合
  ★ 親子（行の関係 ID がほかの行の引数に入っている）は、登録イベントに行の関係 ID が載っていないので数えていない。
あわせて、登録・消滅（定義の丸ごとの削除）・走行末に生きている定義の数を台帳から数える。
使い方  python3.12 tools/birth_shape.py <ラベル>:<台帳.jsonl.gz> ..."""
import collections, gzip, json, statistics as st, sys
for spec in sys.argv[1:]:
    lab, p = spec.split(":", 1)
    births = []; removed = 0; alive_end = None
    with gzip.open(p, "rt") as f:
        next(f)
        for line in f:
            r = json.loads(line)
            if r.get("record_type") != "trial":
                continue
            for e in r.get("reg_del_events") or ():
                if e.get("kind") == "registration" and not e.get("was_extension"):
                    births.append(e["constituents"])
                elif e.get("kind") == "definition_removed":
                    removed += 1
            last = r
    alive_end = len({s["R"] for s in (last.get("constituent_states") or ()) if s.get("alive")})
    sizes = collections.Counter(len(c) for c in births)
    share = []
    for cons in births:
        ids = {c["uid"]: c for c in cons}
        rids = set()
        for c in cons:
            for a, k in zip(c["arguments"], c["arg_kinds"]):
                if k == "relation": rids.add(a)
        n = len(cons); s1 = s2 = 0
        for i, c in enumerate(cons):
            my = set(c["arguments"])
            others = [d for j, d in enumerate(cons) if j != i]
            sh = any(my & set(d["arguments"]) for d in others)
            s1 += sh
        share.append(s1 / n)
    print(f"■ {lab}  台帳 {p.split('/')[-3]}/{p.split('/')[-1]}")
    print(f"  登録（誕生）{len(births):,}　消滅（定義ごと）{removed:,}　走行末に生きている定義 {alive_end:,}")
    print(f"  生まれたときの行数　中央 {st.median(len(c) for c in births)}　分布 {sorted(sizes.items())}")
    print(f"  つながり（引数を共有する行の割合）　平均 {st.mean(share):.3f}　中央 {st.median(share):.3f}　1.0 の定義 {sum(1 for x in share if x == 1.0)}/{len(share)}")
