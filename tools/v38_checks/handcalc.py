"""v3.8 の手計算の期待値（付録 4 節）の検査台。同じプロセスの中で走らせ（~/diag0928/sync_exec.py）、目当ての試行 t の
会計の前後の参加率・削除の直前の保持価値・席の回数を取り出して、そこで止める。模型は変えない。
使い方（作業場所の根で）：HC_T=t HC_OUT=<json> [V38_FROM=t] python3.12 handcalc.py <v3_run.py の引数…>"""
import json, os, runpy, sys
ROOT = os.path.abspath("."); HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [ROOT, ROOT + "/tools", os.path.expanduser("~/diag0928")]
import sync_exec  # noqa: F401  （ProcessPoolExecutor を同じプロセスの中で回すものに替える）
import sweep
T = int(os.environ["HC_T"]); OUT = os.environ["HC_OUT"]
ROW = ("R_beb6d0d0aa09b5d2", 4, 3); SEAT = ("R_c891550efdbaa574", 10)
real_run_one = sweep.run_one


class Stop(Exception):
    pass


def run_one(task):
    import abm.deletion as dl
    import abm.loop as loop
    import abm.accounting as A
    from abm.definition import ExceptionAccumulator
    real_theta = loop.apply_theta; real_acc = loop._update_accounting; res = {"T": T, "V38_FROM": os.environ.get("V38_FROM")}

    def seat(state):
        v = state.slot_history.get(SEAT)
        return dict(v) if hasattr(v, "items") else (sorted(v) if v is not None else None)

    def row_alive(state):
        d = state.definitions.get(SEAT[0])
        c = next((c for c in d.constituents if c.slot_index == SEAT[1]), None) if d else None
        return None if c is None else bool(c.alive)

    def acc(state, output, scene, config, horizon, score, coin, revealed_edge):
        if coin.t == T:
            m = state.merit.get(ROW)
            res["会計の前"] = {"P": A.participation(m) if m else None, "席": seat(state), "席の行が生きている": row_alive(state),
                              "hit": bool(score.hit), "f_fired": bool(coin.f_fired), "R_used": output.trace.get("R_used")}
        out = real_acc(state, output, scene, config, horizon, score, coin, revealed_edge)
        if coin.t == T:
            m = out[0].merit.get(ROW)
            res["会計の後"] = {"P": A.participation(m) if m else None, "席": seat(out[0])}
        return out

    def theta(state, config, trial, *a, **kw):
        if trial == T:
            m = state.merit.get(ROW)
            if m is not None:
                row = next(c for c in state.definitions[ROW[0]].constituents if c.slot_index == ROW[1] and c.registered_at == ROW[2])
                emb = dl._embed_immediately_before_deletion(state)
                exc = state.exceptions.get(ROW[:2], ExceptionAccumulator((0.0,) * 16, 0.0, 0))
                t = A.constituent_value_terms(row.frozen_price, m, exc, emb[ROW], w=config.w, kappa=config.kappa, beta=config.beta,
                                              decay=None, elapsed=trial - ROW[2])
                res["削除の直前"] = {"P": A.participation(m), "V": t.total, "θ′": config.theta_prime}
            res["削除の直前の席"] = seat(state)
        after, ev = real_theta(state, config, trial, *a, **kw)
        if trial == T:
            res["削除"] = [e for e in ev if e.get("kind") == "deletion"]
            json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
            raise Stop()
        return after, ev

    loop._update_accounting = acc; loop.apply_theta = theta
    return real_run_one(task)


sweep.run_one = run_one
sys.argv = ["v3_run.py"] + sys.argv[1:]
runpy.run_path(ROOT + "/tools/v3_run.py", run_name="__main__")
