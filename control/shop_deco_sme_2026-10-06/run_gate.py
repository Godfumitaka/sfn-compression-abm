"""元のSMEと旗なし移植を、種1・世界1/2・200/1740試行で受付へ順に出す。"""
from pathlib import Path
import json
import subprocess
import traceback
from common import AREA, ROOT, PYTHON, command, digest, registered

BASELINE = AREA / "baseline"
DEST = AREA / "gates"
BASE = "10cd8bdd46416aff55d0015e9072fc2186deed83"


def save(record):
    (DEST / "run_gate.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")


def fingerprint(root):
    # 共通のgit情報だけでは未コミットの移植を区別できないので、模型の実ファイルも固定する。
    return {str(p.relative_to(root)):digest(p) for folder in ("abm", "tools")
            for p in sorted((root / folder).rglob("*.py"))}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    world = json.loads((ROOT / "control/shop_deco_sme_2026-10-06/gates/world_gate.json").read_text())
    assert world["passed"]
    for root in (ROOT, BASELINE):
        assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() == BASE
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=BASELINE, text=True).strip()
    protected = {"baseline":fingerprint(BASELINE), "ported":fingerprint(ROOT)}
    result = {"status":"running", "passed":False, "base_commit":BASE,
        "header_included":True, "same_HEAD_used_for_header":True,
        "timing_exception":"cfvalue.jsonlのsec_trial数値のみ（承認済み）。元の記録を保存",
        "source_sha256":protected, "pairs":[]}
    save(result)
    try:
        for trials in (200, 1740):
            for world in (1, 2):
                stem = f"A_w{world}_s001_t{trials}"
                pair = {"world":world, "seed":1, "trials":trials, "retention":"A", "runs":{}}
                result["current"] = stem;save(result)
                for kind, root in (("baseline",BASELINE), ("ported_off",ROOT)):
                    assert protected["baseline"] == fingerprint(BASELINE)
                    assert protected["ported"] == fingerprint(ROOT)
                    out = DEST / "runs" / f"{stem}_{kind}"
                    print(f"関門走行を受付へ: {stem}_{kind}", flush=True)
                    pair["runs"][kind] = registered(command(out, world, 1, trials=trials), out,
                        f"Codex-shop-deco-sme-gate-{stem}-{kind}", cwd=root, mem=1.0)
                left, right = (DEST / "runs" / f"{stem}_{kind}" for kind in ("baseline", "ported_off"))
                cmp_out = DEST / "comparisons" / stem
                cmp_out.mkdir(parents=True, exist_ok=True)
                registered([PYTHON, "-B", str(ROOT / "control/shop_deco_sme_2026-10-06/compare.py"),
                    str(left), str(right), str(cmp_out / "validation.json")], cmp_out,
                    f"Codex-shop-deco-sme-compare-{stem}", mem=0.2, result_file="validation.json")
                pair["comparison"] = json.loads((cmp_out / "validation.json").read_text())
                assert pair["comparison"]["passed"], f"全バイト比較が不通: {stem}"
                result["pairs"].append(pair);save(result)
                print(f"関門の一組が全バイト一致: {stem}", flush=True)
        result.update(status="passed", passed=True)
        result.pop("current", None);save(result)
    except BaseException:
        result.update(status="stopped", stopped_reason=traceback.format_exc())
        save(result)
        raise


if __name__ == "__main__":main()
