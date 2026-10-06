# 照合のおもちゃ（Claude、2026-10-06 夜）。
# シールの席の状態だけを替えた定義を、シール sig_e の場面と照合し、点と N3 を出す。
# 使い方：codex/sme-evict-a-2026-10-06 の tools/sme2017.py を同じ場所に置いて
#   python3 2026-10-06_照合のおもちゃ_Claude.py
# 模型の本番の図ではない。点の流れ（局所の点と親からの伝達）を見るための小さな図。
import sys
from fractions import Fraction
sys.path.insert(0, ".")
from sme2017 import Node, Graph, Matcher, Settings


def graph(seal_state, seal_names):
    # 物 d・s、シール seal(d)、at(d,s)、open(d)、top=implies(at,open)、link=attach(seal,top)
    return Graph((
        Node("d", "entity", args=()), Node("s", "entity", args=()),
        Node("seal", "relation", frozenset(seal_names), ("d",), seal_state),
        Node("at", "relation", frozenset({"at"}), ("d", "s")),
        Node("open", "relation", frozenset({"open"}), ("d",)),
        Node("top", "relation", frozenset({"implies"}), ("at", "open")),
        Node("link", "relation", frozenset({"attach"}), ("seal", "top")),
    ))


scene = graph("F", {"sig_e"})
m = Matcher(Settings(), tie_seed=0)
sxx = m.self_score(scene)
cases = {
    "F[sig_e]": ("F", {"sig_e"}), "F[sig_n]": ("F", {"sig_n"}), "U": ("U", set()),
    "H{sig_n}": ("H", {"sig_n"}), "H{sig_n,sig_e}": ("H", {"sig_n", "sig_e"}),
}
for label, (state, names) in cases.items():
    d = graph(state, names)
    best = m.match(d, scene).best
    sdx = best.score if best else 0.0
    sdd = m.self_score(d)
    n3 = 2 * Fraction(sdx) / (Fraction(sdd) + Fraction(sxx))
    print(f"{label:16s} S_dx={sdx:.4f} S_dd={sdd:.4f} N3={float(n3):.4f}")
    if best:
        # 各対：(左, 右, 局所の点, 親から渡った点)。席の点＝局所＋渡った点。
        for row in sorted(best.breakdown):
            print("    ", row[0], row[1], f"local={row[2]:.4f}", f"passed={row[3]:.4f}")
