"""研究者用の種・場面IDを足した後の既存出力を照合する。模型の条件は変えない。"""
import json
from run_registered import AREA, PYTHON, command, compare_pair, registered


def main():
    dest = AREA / "observer_check"
    config = AREA / "gates_runs/small_config.json"
    resources = []
    for level in (None, "current"):
        out = dest / ("off" if level is None else "current")
        resources.append(registered(command(config, out, "N3", "A", 1, 1, level), out,
                                    f"Codex-shop-deco-observer-{level}", mem=0.2))
    comparison = compare_pair(dest / "off", dest / "current")
    assert comparison["passed"]
    out = dest / "plus8"
    resources.append(registered(command(config, out, "N3", "D", 2, 1, "plus8"), out,
                                "Codex-shop-deco-observer-plus8", mem=0.3))
    resources.append(registered([PYTHON, "-B", "control/shop_deco_2026-10-04/analyse_run.py", str(out), "1", str(dest / "analysis") ,"--pilot-all-spoken"],
                                dest / "analysis", "Codex-shop-deco-observer-analysis", mem=0.3, result_file="summary.json"))
    (dest / "check.json").write_text(json.dumps({"passed": True, "comparison": comparison,
        "resources": resources, "analysis_validation": json.loads((dest / "analysis/validation.json").read_text())}, ensure_ascii=False, indent=2) + "\n")
    print("研究者用記録の識別と全試行の読取、一致の再確認は合格", flush=True)


if __name__ == "__main__":
    main()
