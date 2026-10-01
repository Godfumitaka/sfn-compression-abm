"""現行の二本で、世界と状態の全試行一致、通常世界の読み手の回帰を検査する。"""
import gzip
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / "source"
sys.path[:0] = [str(SOURCE / "tools"), str(SOURCE)]
from extrap_reader import iter_run
from run_worldv4 import CELL, PYTHON, completed, run_root
from worldvariant import variant_rng
from abm.seed import load_seed
from abm.world import opaque_id

def body_sha(path):
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as f:
        next(f)
        for line in f:
            digest.update(line)
    return digest.hexdigest()

def main():
    seed_data = load_seed(SOURCE / "seeds/U-011_seed_v3a2.json").data
    out = dict(code_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip())
    old_spec = importlib.util.spec_from_file_location("extrap_reader_before", ROOT / "extrap_reader_before.py")
    old = importlib.util.module_from_spec(old_spec)
    old_spec.loader.exec_module(old)
    for arm in ("v4spc_A_lam020", "gate_plain_A_lam020"):
        assert completed(arm, 1)
        root = run_root(arm, 1)
        ledger = root / "ledgers/cells" / CELL / "seed001.jsonl.gz"
        before = body_sha(ledger)
        n = 0
        counts = {"A": 0, "B": 0}
        if arm.startswith("v4"):
            for tr in iter_run(str(root), CELL, 1):
                t, row, wt = tr["t"], tr["row"], tr["world"]
                expected_variant = "A" if variant_rng(1, t).random() < 0.8 else "B"
                assert row["world_variant"] == expected_variant
                switch = {opaque_id(1, t, f"relation:tree:{i}.0.0"): name
                          for i, name in enumerate(seed_data["motif_structure"][wt.motif]["subtrees"])}
                assert row["held_out_switch"] == switch.get(wt.held_out_edge.relation_id)
                counts[expected_variant] += 1
                n += 1
        else:
            before_iter = old.iter_run(str(root), CELL, 1)
            after_iter = iter_run(str(root), CELL, 1)
            for prior, after in zip(before_iter, after_iter, strict=True):
                assert prior == after
                n += 1
        assert n == 1740
        assert body_sha(ledger) == before
        out[arm] = dict(trials=n, world_hash=tr["header"]["world_hash"] if arm.startswith("v4") else after["header"]["world_hash"],
                        body_sha=before, variant_counts=counts if arm.startswith("v4") else None,
                        checks=dict(world_fingerprint=n, state_fingerprint=n, old_reader_equal=n if not arm.startswith("v4") else None))
        role_dir = ROOT / "gate1_roles" / arm
        log = ROOT / "logs" / f"gate1_roles_{arm}.log"
        with log.open("x") as f:
            subprocess.run([PYTHON, "tools/roletarget_recompute.py", str(root), str(role_dir), "1"], cwd=SOURCE,
                           stdout=f, stderr=subprocess.STDOUT, check=True)
        role = json.loads((role_dir / "checks.json").read_text())[0]
        for key in ("check1_mismatch", "check2_mismatch", "hash_mismatch", "args_unrestored", "score_R_differs", "answer_R_differs"):
            assert role[key] == 0, (arm, key, role[key], role["examples"])
        assert role["trials"] == 1740
        out[arm]["roletarget"] = role
        assert body_sha(ledger) == before
    (ROOT / "gate1_passed.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
