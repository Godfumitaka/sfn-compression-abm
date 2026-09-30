"""名前の付け替えの確かめ（2026-09-30 の委任書「U の席の問題の大きさを測る・名前の付け替えの確かめ」の 2）。★ 模型は変えない。
世界の名前を一貫して付け替えて、tools/v3_run.py をこの過程の中で一本だけ走らせる。
  述語の名前：種ファイルの述語の名前（marginal の鍵）を、すべての出どころ（bags の鍵・glue・role_unary・canon・marginal の鍵・constituents・
    motif_structure・subtrees）で同じ写像 名前→"p"+sha256(塩‖名前) の頭 12 桁 に置き換える。marginal の並び（固定辞書の順）は保つ。種の sha256 は計算し直す。
  物・関係・グラフの ID：abm.world.opaque_id に塩を足す（blake2b(塩‖run_seed‖試行‖役割名)）。同じ役割には同じ ID、違う役割には違う ID（一対一）。
  定義の名前：述語の名前の sha256 から作るので、述語の付け替えに連れて変わる（--nohash の「_t試行」もそのまま）。
  付け替えの写像は <出力の根>/relabel/map.json に書く。
使い方  python3.12 tools/histrole_checks/relabel_run.py <塩> <元の設定> <出力の根> -- <tools/v3_run.py の設定と出力の根より後の引数（--seeds は一つ、--workers 1）>
"""
from __future__ import annotations

import concurrent.futures
import json
import sys
from hashlib import blake2b, sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
SKIP = {"assumptions", "generated", "version", "sha256"}


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


def relabel_seed(src: Path, dst: Path, salt: str) -> dict:
    from abm.seed import seed_hash
    raw = json.loads(src.read_text(encoding="utf-8"))
    names = list(raw["marginal"].keys())
    mp = {n: "p" + sha256(f"{salt}\x1f{n}".encode("utf-8")).hexdigest()[:12] for n in names}
    if len(set(mp.values())) != len(mp):
        raise SystemExit("付け替え先が重なった")

    def rep(o):
        if isinstance(o, dict):
            return {mp.get(k, k): rep(v) for k, v in o.items()}
        if isinstance(o, list):
            return [rep(v) for v in o]
        if isinstance(o, str):
            return mp.get(o, o)
        return o
    out = {k: (v if k in SKIP else rep(v)) for k, v in raw.items()}
    out.pop("sha256", None)
    out["sha256"] = seed_hash(out)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return mp


def main():
    salt, cfg_src, out_root = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]).resolve()
    assert sys.argv[4] == "--"
    rest = sys.argv[5:]
    rd = out_root / "relabel"
    rd.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((ROOT / cfg_src).read_text(encoding="utf-8"))
    mp = relabel_seed(ROOT / cfg["seed_file"], rd / "seed_relabeled.json", salt)
    cfg["seed_file"] = str(rd / "seed_relabeled.json")
    (rd / "config_relabeled.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (rd / "map.json").write_text(json.dumps({"salt": salt, "predicates": mp}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    import abm.world as w

    def opaque_id(run_seed, trial_index, role_name):
        parts = (salt.encode("utf-8"), str(run_seed).encode("utf-8"), str(trial_index).encode("utf-8"), role_name.encode("utf-8"))
        return blake2b(b"\x1f".join(parts), digest_size=8).hexdigest()

    w.opaque_id = opaque_id
    import v3_run
    v3_run.ProcessPoolExecutor = Inline
    sys.argv = ["tools/v3_run.py", str(rd / "config_relabeled.json"), str(out_root), *rest]
    v3_run.main()


if __name__ == "__main__":
    main()
