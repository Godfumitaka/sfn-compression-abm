"""手例だけを扱う段①の検査材料。元の走行・種の記録は読まない。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import replace
from fractions import Fraction
import io
import json
from pathlib import Path
from random import Random
from types import SimpleNamespace as NS
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]

import attnsel as A
import selectn3 as N
import v39
from abm.definition import Constituent, FrequencyTable, FrozenPrice, NamedDefinition
from abm.domains import AgentConfig, AgentInput, CorrectionMode, Entity, Prototype, Relation, RelationGraph, VerbatimTrace

SEEN = ("hold", "hold_b", "fold", "cause", "attach", "sig_n", "sig_e")


@contextmanager
def matching():
    """既存の F/H と --u-struct の照合。出るときに差し替えを戻す。"""
    import abm.sme as sme
    import ustruct
    old = sme._alignment_candidates
    old_select = v39.select_definition
    old_cfg = dict(v39.CFG)
    v39.CFG.setdefault("u_abstain", False)
    v39._install_candidates()
    undo = ustruct.install_matching()
    N.install_n3()
    try:
        yield
    finally:
        undo()
        sme._alignment_candidates = old
        v39.select_definition = old_select
        v39.CFG.clear()
        v39.CFG.update(old_cfg)


def example(*, extra_unknown=False):
    """甲の例外の日。通常はシール U、例外はシール F。物・構造は共通。"""
    price = FrozenPrice(1.0, 0, 0.0, 3)
    defs, history = [], {}
    for name, door, sig in (("R_normal", "hold", v39.ERASED), ("R_exception", "hold_b", "sig_e")):
        rels = [Relation("door", door, ("x", "y")), Relation("fold", "fold", ("x", "y")),
                Relation("root", "cause", ("door", "fold")), Relation("sig", sig, ("x",)),
                Relation("attach", "attach", ("sig", "root"))]
        if extra_unknown and name == "R_exception":
            rels.append(Relation("extra", v39.ERASED, ("x", "y")))
        rows = tuple(Constituent(i, 3, r, price, r.predicate != v39.ERASED) for i, r in enumerate(rels))
        defs.append(NamedDefinition(name, rows, len(rows), 3))
        history.update({(name, i): {r.predicate: 1} for i, r in enumerate(rels) if r.predicate != v39.ERASED})
    scene = RelationGraph("shop", (Entity("a"), Entity("b")),
                          (Relation("s_fold", "fold", ("a", "b")),
                           Relation("s_root", "cause", ("s_door", "s_fold")),
                           Relation("s_sig", "sig_e", ("a",)),
                           Relation("s_attach", "attach", ("s_sig", "s_root"))))
    truth = Relation("s_door", "hold_b", ("a", "b"))
    full = replace(scene, relations=(truth, *scene.relations))
    state = v39._state_class()(definitions={d.name: d for d in defs}, slot_history=history,
                              p_hat=FrequencyTable({p: 1 for p in SEEN}, len(SEEN), 0.1, frozenset(SEEN)),
                              prototype=Prototype((VerbatimTrace(1, full),)))
    config = AgentConfig(0.0, CorrectionMode.NONE, tau_acc=0.67, fill_selection="most_frequent",
                         higher_order_predicates=frozenset(("cause", "attach")))
    ai = AgentInput(full, scene, tuple(r.relation_id for r in scene.relations))
    return state, ai, config, truth


def feedback(trial, truth, *, disclosed=True, f=0.5):
    return {"prediction_order": trial, "agent_id": "agent", "f_realized": f, "f_fired": disclosed,
            "feedback_content": truth.to_dict() if disclosed else None}


def hand_values():
    state, ai, config, truth = example()
    rows = []
    with matching(), A.isolated():
        cs = A.candidates(state, ai.target_graph_partial)
        for w in (1, 2):
            weights = {p: 1.0 for p in SEEN}
            weights["sig_e"] = float(w)
            values = {}
            for c in cs:
                s, dd, xx = c.terms.scores(weights)
                q = c.terms.value(weights)
                values[c.definition.name] = {"S_dx": str(s), "S_dd": str(dd), "S_xx": str(xx),
                                             "Q": str(q), "Q_float": float(q)}
            gap = Fraction(values["R_exception"]["Q"]) - Fraction(values["R_normal"]["Q"])
            rows.append({"sig_e": w, "values": values, "exception_minus_normal": str(gap)})
    return rows


def tiny_grid(*, steps=80):
    """同じ手例の固定記憶で 80 回だけ更新を検査する。世界走行の成績ではない。"""
    out = []
    with matching():
        for beta in (1.0, 5.0, 10.0):
            for eta in (0.01, 0.05, 0.1):
                state, ai, cfg, truth = example(extra_unknown=True)
                learner = A.Attention(enabled=True, beta=beta, eta=eta, seen=SEEN)
                first_loss, last_loss, hits, changes = None, None, 0, 0
                for t in range(1, steps + 1):
                    prepared = learner.prepare("agent", t, ai, state, cfg, Random(1))
                    hits += A.answer_key(prepared.output.prediction) == (truth.predicate, truth.arguments)
                    rec = learner.finish(prepared, feedback(t, truth, f=1.0))
                    changes += rec["updated"]
                    if first_loss is None:
                        first_loss = rec["L"]
                    last_loss = rec["L"]
                out.append({"beta": beta, "eta": eta, "steps": steps, "correct_before_update": hits,
                            "updated": changes, "first_L": first_loss, "last_L_before_update": last_loss,
                            "weights_after": learner.weights})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--attn-select", action="store_true")
    ap.add_argument("--attn-log", action="store_true", help="記録だけ。選択・重みを変えない")
    ap.add_argument("--attn-beta", type=float, default=5.0)
    ap.add_argument("--attn-eta", type=float, default=0.05)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    state, ai, cfg, truth = example(extra_unknown=True)
    learner = A.Attention(enabled=args.attn_select, beta=args.attn_beta, eta=args.attn_eta, seen=SEEN)
    with matching():
        prepared = learner.prepare("agent", 1, ai, state, cfg, Random(1), record_only=args.attn_log)
        rec = learner.finish(prepared, feedback(1, truth))
    result = {"scope": "stage1_hand_example_only", "answer": A.answer_key(prepared.output.prediction),
              "attention": rec}
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "example.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        if rec is not None:
            with (args.output / "seed001.attn.jsonl").open("w", encoding="utf-8") as f:
                A.write_record(f, rec)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
