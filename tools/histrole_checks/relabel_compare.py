"""名前の付け替えの前と後を比べる（2026-09-30 の委任書の 2）。★ 数えるだけ。判断しない。
名前に依らない量だけを試行ごとに並べて比べる。
  台帳：coverage・hit・prediction_path、予測した述語（付け替えの写像で元の名に戻す）、登録（同化か誕生か・行の数）。
  side（kind＝v39）：F・H・U の席の数・定義の数・変換の中身（種類・V・ΔC・理由・同点の数の並び）・退役の数。
  side（kind＝v310be）：新しい定義を選んだか・K・r・ΔC の予測・同点の数。
  答えごとの記録：出どころ・当たり・席の状態。
使い方  python3.12 tools/histrole_checks/relabel_compare.py <元の走行根> <付け替えた走行根> <種>
"""
import csv
import glob
import gzip
import json
import sys


def load(root, s, inv):
    led = glob.glob(f"{root}/ledgers/cells/*/seed{s:03d}.jsonl.gz")[0]
    L = {}
    with gzip.open(led, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            r = json.loads(line)
            if r.get("record_type", "trial") != "trial":
                continue
            reg = r.get("registration_event") or {}
            pe = r.get("predicted_edge") or {}
            L[r["prediction_order"]] = {"coverage": r.get("coverage"), "hit": r.get("hit"), "path": r.get("prediction_path"),
                                        "pred": inv.get(pe.get("predicate"), pe.get("predicate")),
                                        "reg": (bool(reg.get("was_extension")), len(reg.get("constituents") or [])) if reg else None}
    V, B = {}, {}
    for line in open(glob.glob(f"{root}/side/*/seed{s:03d}.jsonl")[0], encoding="utf-8"):
        d = json.loads(line)
        if d.get("kind") == "v39":
            V[d["trial"]] = {"F": d["F"], "H": d["H"], "U": d["U"], "defs": d["defs"],
                             "conv": [(c[0], round(c[3], 9) if isinstance(c[3], float) else c[3], c[4], c[5], c[6]) for c in d.get("conv") or []],
                             "conv_slots": [(c[1][:6], c[2]) for c in d.get("conv") or []], "retire": len(d.get("retire") or [])}
        elif d.get("kind") == "v310be":
            B[d["trial"]] = {"new": d.get("chosen", "x") is None, "K": round(d["K"], 9) if isinstance(d.get("K"), float) else d.get("K"),
                             "r": round(d["r"], 9) if isinstance(d.get("r"), float) else d.get("r"), "dC": d.get("dC_pred"), "ties": d.get("ties")}
    A = {}
    af = glob.glob(f"{root}/side/*/seed{s:03d}.answers.csv")
    if af:
        for r in csv.DictReader(open(af[0], encoding="utf-8")):
            A[int(r["trial"])] = (r["source"], r["hit"], r["seat_state"])
    return L, V, B, A


def first_diff(a, b, keyf=lambda x: x):
    for t in sorted(set(a) | set(b)):
        if keyf(a.get(t)) != keyf(b.get(t)):
            return t
    return None


def main():
    ro, rr, s = sys.argv[1], sys.argv[2], int(sys.argv[3])
    mp = json.load(open(f"{rr}/relabel/map.json", encoding="utf-8"))["predicates"]
    inv = {v: k for k, v in mp.items()}
    Lo, Vo, Bo, Ao = load(ro, s, {})
    Lr, Vr, Br, Ar = load(rr, s, inv)
    vkey = lambda x: None if x is None else {k: v for k, v in x.items() if k != "conv_slots"}  # noqa: E731
    fd = {"台帳": first_diff(Lo, Lr), "v39（席の状態・定義・変換）": first_diff(Vo, Vr, vkey), "v310be（E の選択）": first_diff(Bo, Br), "答えごとの記録": first_diff(Ao, Ar)}
    tot = lambda L_, V_, A_: {"答えた": sum(1 for x in L_.values() if x["coverage"] == 1), "当たり": sum(1 for x in L_.values() if x["hit"] == 1),  # noqa: E731
                              "走行末の定義": V_[max(V_)]["defs"] if V_ else None, "変換": sum(len(x["conv"]) for x in V_.values()),
                              "変換（同点あり）": sum(1 for x in V_.values() for c in x["conv"] if (c[4] or 1) > 1),
                              "誕生": sum(1 for x in L_.values() if x["reg"] and not x["reg"][0]), "同化": sum(1 for x in L_.values() if x["reg"] and x["reg"][0])}
    res = {"種": s, "最初に違った試行": fd, "元": tot(Lo, Vo, Ao), "付け替え": tot(Lr, Vr, Ar),
           "答えが違った試行": sum(1 for t in set(Ao) | set(Ar) if Ao.get(t) != Ar.get(t)),
           "台帳が違った試行": sum(1 for t in set(Lo) | set(Lr) if Lo.get(t) != Lr.get(t))}
    t0 = min((t for t in fd.values() if t is not None), default=None)
    if t0 is not None:
        res["最初の違いの試行"] = t0
        res["その試行の中身"] = {"元": {"台帳": Lo.get(t0), "v39": Vo.get(t0), "v310be": Bo.get(t0)},
                            "付け替え": {"台帳": Lr.get(t0), "v39": Vr.get(t0), "v310be": Br.get(t0)}}
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
