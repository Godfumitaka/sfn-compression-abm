"""親の無い一階の行の経路（委任書「物の組で見分ける箇所の洗い出し…」の 1）。★ 記録だけ。模型の動きは変えない（台帳が同じことを確かめる）。
tools/v3_run.py をこの過程の中で一本だけ走らせ（並列の子過程を使わない）、実際の鎖の誕生ごとに、
  土台（base）の関係・今の場面の関係・誕生の材料（v39 の _pool_pairs の対）・構造上必要な子を残したあとの行（_drop_childless）・写し
を控え、定義の一階の行のうち、定義の中に親の行が無いものを、その理由ごとに数える。
使い方  python3.12 tools/histrole_checks/birth_paths.py <出力 jsonl> -- <tools/v3_run.py の引数（--seeds は一つ、--workers 1）>
★ --hist-role と一緒には使わない（loop.m1 を先に包むため）。
"""
from __future__ import annotations

import concurrent.futures
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

OUT = []
LASTPOOL = {}


class Inline:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def submit(self, fn, *a, **k):
        f = concurrent.futures.Future()
        try:
            f.set_result(fn(*a, **k))
        except BaseException as e:  # noqa
            f.set_exception(e)
        return f

    def shutdown(self, *a, **k):
        pass


def main():
    out_path = sys.argv[1]
    assert sys.argv[2] == "--"
    run_args = sys.argv[3:]
    if "--hist-role" in run_args:
        raise SystemExit("--hist-role と一緒には使わない")
    import abm.abstraction as ab
    import abm.loop as loop
    import v3_run
    import v39
    from abm.filling import _is_higher

    real_pool = v39._pool_pairs

    def pool_pairs(base, target, alignment):
        pairs = real_pool(base, target, alignment)
        LASTPOOL.update(base=base, target=target, alignment=alignment, pairs=pairs)
        return pairs

    v39._pool_pairs = pool_pairs
    orig = ab.m1
    if loop.m1 is not orig:
        raise RuntimeError("loop.m1 が既に差し替えられている")

    def m1(state, base, target, alignment, trial, **kw):
        out, reg = orig(state, base, target, alignment, trial, **kw)
        if reg is None or reg["was_extension"]:
            return out, reg
        R = reg["R"]
        d = out.definitions[R]
        if LASTPOOL.get("base") is not base or LASTPOOL.get("target") is not target:
            raise RuntimeError(f"誕生の材料を控えられなかった（試行 {trial}）")
        al0 = LASTPOOL["alignment"]
        pool_ids = [l.relation_id for l, _ in LASTPOOL["pairs"]]
        S, dropped = v39._drop_childless([l for l, _ in LASTPOOL["pairs"]], {r.relation_id for r in base.relations})
        kept = {r.relation_id for r in S}
        rel_ids = {row.relation.relation_id for row in d.constituents}
        t_by_id = {r.relation_id: r for r in target.relations}
        base_rel_ids = {r.relation_id for r in base.relations}
        base_ent_ids = {e.entity_id for e in base.entities}
        rows = []
        for row in d.constituents:
            rid = row.relation.relation_id
            first = not _is_higher(row.relation, rel_ids)
            parents_def = [p.relation.relation_id for p in d.constituents if rid in p.relation.arguments]
            item = {"slot": row.slot_index, "rid": rid, "pred": row.relation.predicate, "args": list(row.relation.arguments),
                    "first": first, "parents_def": parents_def}
            if first and not parents_def:
                why = []
                for p in base.relations:
                    if rid not in p.arguments:
                        continue
                    tq = al0.relation_mapping.get(p.relation_id)
                    tr = t_by_id.get(tq)
                    if p.relation_id in pool_ids:
                        cause = "材料に入ったが、構造上必要な子が欠けて外れた（_drop_childless）"
                    elif tr is None and any(a not in base_rel_ids and a not in base_ent_ids for a in p.arguments):
                        cause = "土台の親が今の場面の関係に写らなかった（土台の記憶に、親の子が無い：伏せられて開示されなかった子）"
                    elif tr is None:
                        cause = "土台の親が今の場面の関係に写らなかった（土台の記憶に親の子はそろっている）"
                    elif tr.predicate != p.predicate:
                        cause = "土台の親は写ったが、述語が違った"
                    else:
                        cause = "その他"
                    why.append({"parent": p.relation_id, "parent_pred": p.predicate, "cause": cause,
                                "target": tq, "target_pred": tr.predicate if tr else None})
                item["base_parents"] = why
            rows.append(item)
        OUT.append({"trial": trial, "R": R, "base_written_at": kw.get("base_written_at"), "pool": len(pool_ids),
                    "dropped": dropped, "kept": len(kept), "rows": rows})
        return out, reg

    loop.m1 = m1
    v3_run.ProcessPoolExecutor = Inline
    sys.argv = ["tools/v3_run.py", *run_args]
    try:
        v3_run.main()
    finally:
        with open(out_path, "w", encoding="utf-8") as f:
            for r in OUT:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
