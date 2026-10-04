"""お店の種から M1 だけを残す。既存の種と abm/ は書き換えない。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from abm.seed import load_seed, seed_hash  # noqa: E402


def main():
    data = json.loads((ROOT / "tools/shop/U-011_seed_shop.json").read_text(encoding="utf-8"))
    for key in ("motif_structure", "pi_A", "one_minus_h", "role_unary"):
        data[key] = {"M1": data[key]["M1"]}
    data["bags"] = {word: ["M1"] for word, motifs in data["bags"].items() if "M1" in motifs}
    data["version"] = str(data.get("version", "")) + "+verb（M1 だけ）"
    if "sha256" in data:
        data.pop("sha256")
        data["sha256"] = seed_hash(data)
    out = ROOT / "tools/verb/U-011_seed_verb.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    seed = load_seed(out)
    assert tuple(seed.data["motif_structure"]) == ("M1",)
    print(out)


if __name__ == "__main__":
    main()
