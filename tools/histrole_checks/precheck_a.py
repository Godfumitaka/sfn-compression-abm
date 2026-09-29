"""追記（2026-09-30 深夜）A「本番の前の確かめ」。★ 記録だけ（模型の動きは変えない。台帳が同じ走行と同じことを確かめる）。
tools/v3_run.py をこの過程の中で一本だけ走らせ、走行末の状態・採点の記録から次を数える。
  1 走行末の各定義の一階の席の履歴（回数 1 以上の名）が、世界でその席の役割に入ったことのある名だけか。
    役割＝その席の親の行（生まれたときの述語）と、親の中の位置。世界の側は、この走行の全試行の場面（abm.world.generate_trial を台帳の run_seed で
    作り直す）で、同じ述語の関係の同じ位置に入った子の述語の集合。親の無い席は役割が決まらないので、別に数える。
  2 一つの定義の中で、役割の違う H の席の答え（tools/v39.py h_answer）が同じ名にそろっている席の組の数。
  3 採点された席の対応先の関係 ID が、開示された関係の ID と一致しているか（tools/v310be.py score_answers_role を記録だけの包みで見る）。
使い方  python3.12 tools/histrole_checks/precheck_a.py <出力 md> -- <tools/v3_run.py の引数（--hist-role --score-role を含む。--seeds は一つ、--workers 1）>
"""
from __future__ import annotations

import collections
import concurrent.futures
import glob
import gzip
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
SCORED = []


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
    out_md = sys.argv[1]
    assert sys.argv[2] == "--"
    run_args = sys.argv[3:]
    if "--hist-role" not in run_args or "--score-role" not in run_args:
        raise SystemExit("--hist-role と --score-role を付けて走らせる")
    import v3_run
    import v310be
    real_score = v310be.score_answers_role

    def score_answers_role(seats, ans, received, t):
        out, scored = real_score(seats, ans, received, t)
        by_slot = {it["slot"]: it for it in ans["items"]}
        for x in scored:
            SCORED.append((t, ans["R"], x[0], by_slot[x[0]].get("cid"), received.relation_id))
        return out, scored

    v310be.score_answers_role = score_answers_role
    v3_run.ProcessPoolExecutor = Inline
    sys.argv = ["tools/v3_run.py", *run_args]
    v3_run.main()

    import sweep
    import v39
    from abm.filling import _is_higher
    from abm.world import generate_trial
    state = v3_run._LAST_STATE["state"]
    config = v39.CTX["config"]
    out_root = Path(run_args[1])
    led = sorted(glob.glob(str(out_root / "ledgers/cells/*/seed*.jsonl.gz")))[0]
    birth = {}
    trials = []
    with gzip.open(led, "rt", encoding="utf-8") as f:
        h = json.loads(next(f))
        for line in f:
            r = json.loads(line)
            if r.get("record_type", "trial") != "trial":
                continue
            trials.append(r["prediction_order"])
            reg = r.get("registration_event")
            if reg and not reg.get("was_extension"):
                birth[reg["R"]] = {c["slot_index"]: c["predicate"] for c in reg["constituents"]}
    cfg = json.load(open(ROOT / run_args[0], encoding="utf-8"))
    seed = sweep.load_seed(cfg["seed_file"])
    role_names = collections.defaultdict(set)
    for t in sorted(set(trials)):
        g = generate_trial(h["run_seed"], t, h["agent_ids"], seed=seed).G_star
        by_id = {x.relation_id: x for x in g.relations}
        for p in g.relations:
            for k, a in enumerate(p.arguments):
                if a in by_id:
                    role_names[(p.predicate, k)].add(by_id[a].predicate)

    C = collections.Counter()
    bad1 = []
    noparent = []
    pairs2 = []
    for R, d in sorted(state.definitions.items()):
        bp = birth[R]
        rel_ids = {row.relation.relation_id for row in d.constituents}

        def roles(row):
            return frozenset((bp[p.slot_index], k) for p in d.constituents
                             for k, a in enumerate(p.relation.arguments) if a == row.relation.relation_id)
        C["走行末の定義"] += 1
        hs = []
        for row in d.constituents:
            first = not _is_higher(row.relation, rel_ids)
            key = (R, row.slot_index)
            hist = state.slot_history.get(key)
            st = v39.seat_state(d, row, state.slot_history)
            rl = roles(row)
            if st == "H":
                ans = v39.h_answer(d, row, state.slot_history, state.p_hat, config.local_lambda, config.higher_order_predicates)[0]
                hs.append((row.slot_index, first, rl, ans))
            if not first or hist is None:
                continue
            names = {p for p, n in v39.hist_counts(hist).items() if n >= 1}
            C["一階の席（履歴あり）"] += 1
            C[f"一階の席（履歴あり）_{st}"] += 1
            C["一階の席の履歴の名（のべ）"] += len(names)
            if not rl:
                C["一階の席（履歴あり）_親が無い"] += 1
                noparent.append({"R": R, "slot": row.slot_index, "状態": st, "生まれたときの述語": bp[row.slot_index],
                                 "履歴": dict(v39.hist_counts(hist))})
                continue
            allowed = set().union(*(role_names.get(x, set()) for x in rl))
            extra = sorted(names - allowed)
            if extra:
                C["検査1_破れた席"] += 1
                C["検査1_役割に無い名（のべ）"] += len(extra)
                bad1.append({"R": R, "slot": row.slot_index, "状態": st, "役割": sorted(rl), "役割に入った名": sorted(allowed),
                             "履歴": dict(v39.hist_counts(hist)), "役割に無い名": extra})
        for (s1, f1, r1, a1), (s2, f2, r2, a2) in itertools.combinations(hs, 2):
            if r1 == r2:
                C["検査2_役割が同じ H の席の組"] += 1
                continue
            C["検査2_役割の違う H の席の組"] += 1
            if a1 is not None and a1 == a2:
                C["検査2_答えがそろった組"] += 1
                pairs2.append({"R": R, "席": [s1, s2], "一階": [f1, f2], "役割": [sorted(r1) or "根", sorted(r2) or "根"], "答え": a1})
        C["H の席"] += len(hs)
        C["H の席_一階"] += sum(1 for x in hs if x[1])
        C["H の席_答えが決まらない（棄権）"] += sum(1 for x in hs if x[3] is None)
    C["検査3_採点された席"] = len(SCORED)
    C["検査3_対応先と開示の ID が一致"] = sum(1 for x in SCORED if x[3] == x[4])
    C["検査3_一致しない"] = sum(1 for x in SCORED if x[3] != x[4])
    ok = C["検査1_破れた席"] == 0 and C["検査2_答えがそろった組"] == 0 and C["検査3_一致しない"] == 0
    keys = ["走行末の定義", "一階の席（履歴あり）", "一階の席（履歴あり）_F", "一階の席（履歴あり）_H", "一階の席（履歴あり）_親が無い",
            "一階の席の履歴の名（のべ）", "検査1_破れた席", "検査1_役割に無い名（のべ）",
            "H の席", "H の席_一階", "H の席_答えが決まらない（棄権）", "検査2_役割の違う H の席の組", "検査2_役割が同じ H の席の組", "検査2_答えがそろった組",
            "検査3_採点された席", "検査3_対応先と開示の ID が一致", "検査3_一致しない"]
    L = ["| 項目 | 数 |", "|---|---:|"] + [f"| {k} | {C.get(k, 0):,} |" for k in keys]
    L += ["", f"判定：{'三つとも通った' if ok else '★ 破れた'}（検査 1 の破れた席 {C.get('検査1_破れた席', 0)}・検査 2 のそろった組 {C.get('検査2_答えがそろった組', 0)}・検査 3 の一致しない席 {C.get('検査3_一致しない', 0)}）"]
    L += ["", "世界でそれぞれの役割（親の述語, 位置）に入った子の名の数：" +
          f"役割 {len(role_names)}、名が一つの役割 {sum(1 for v in role_names.values() if len(v) == 1)}、二つ以上 {sum(1 for v in role_names.values() if len(v) > 1)}"]
    Path(out_md).write_text("\n".join(L) + "\n", encoding="utf-8")
    json.dump({"数": dict(C), "通った": ok, "検査1_破れた席": bad1, "親が無い一階の席": noparent, "検査2_そろった組": pairs2,
               "検査3_一致しない": [x for x in SCORED if x[3] != x[4]],
               "役割に入った名": {f"{k[0]}#{k[1]}": sorted(v) for k, v in sorted(role_names.items())}},
              open(out_md.replace(".md", ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(L))
    sys.exit(0 if ok else 4)


if __name__ == "__main__":
    main()
