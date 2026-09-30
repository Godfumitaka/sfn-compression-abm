"""お店の世界の種ファイルを作る（2026-10-01 未明の委任書「手がかりの世界」の 1-1）。★ 原本の seeds/ は変えない。
seeds/U-011_seed_v3a2.json を写し、motif_structure・pi_A・one_minus_h・role_unary から M3・M4 を除く。
袋（bags）は各語の型の並びから M3・M4 を除き、空になった語を落とす（M1・M2 の分はそのまま）。ほかの欄（subtrees・glue・marginal など）は変えない。
sha256 の欄があれば計算し直す。出力：tools/shop/U-011_seed_shop.json"""
import json
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, W)
from abm.seed import load_seed, seed_hash  # noqa: E402

src = os.path.join(W, "seeds/U-011_seed_v3a2.json")
out = os.path.join(W, "tools/shop/U-011_seed_shop.json")
d = json.load(open(src, encoding="utf-8"))
keep = ("M1", "M2")
for k in ("motif_structure", "pi_A", "one_minus_h", "role_unary"):
    d[k] = {m: v for m, v in d[k].items() if m in keep}
d["bags"] = {w: [m for m in ms if m in keep] for w, ms in d["bags"].items() if any(m in keep for m in ms)}
d["version"] = str(d.get("version", "")) + "+shop（M1・M2 だけ）"
if "sha256" in d:
    d.pop("sha256")
    d["sha256"] = seed_hash(d)
json.dump(d, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
s = load_seed(out)
print("ok", out, sorted(s.data["motif_structure"]), "sha256 欄" if "sha256" in d else "sha256 欄なし")
