"""段3の走行比較と資源計測。失敗したら次の走行を起動しない。"""
import itertools
import json
from run_registered import AREA, CONFIG, ROOT, command, compare_pair, registered


def main():
    dest = AREA / "gates_runs"
    dest.mkdir(parents=True, exist_ok=True)
    config = json.loads(CONFIG.read_text())
    config["trial_count"] = 64
    config["seeds"] = {"start": 1, "count": 1}
    config_path = dest / "small_config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    result = {"passed": False, "trial_count": 64, "seed": 1, "comparisons": [], "resources": []}
    result_path = dest / "run_gate.json"
    try:
        # 先に旗なし／currentの8組。研究者用research/はside比較の外。
        for selection, retention, world in itertools.product(("N3", "support"), ("A", "D"), (1, 2)):
            stem = f"{selection}_{retention}_w{world}"
            for level in (None, "current"):
                label = "off" if level is None else level
                out = dest / f"{stem}_{label}"
                rec = registered(command(config_path, out, selection, retention, world, 1, level), out,
                                 f"Codex-shop-deco-gate-{stem}-{label}")
                result["resources"].append(rec)
                result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            comparison = {"selection": selection, "retention": retention, "world": world,
                          **compare_pair(dest / f"{stem}_off", dest / f"{stem}_current")}
            result["comparisons"].append(comparison)
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            assert comparison["passed"], f"旗なし／currentの台帳本体・sideが異なる: {stem}"
            print(f"旗なし／current一致: {stem}", flush=True)
        for level, selection, retention, world in itertools.product(("skeleton", "plus4", "plus8"), ("N3", "support"), ("A", "D"), (1, 2)):
            stem = f"{selection}_{retention}_w{world}_{level}"
            out = dest / stem
            result["resources"].append(registered(command(config_path, out, selection, retention, world, 1, level),
                out, f"Codex-shop-deco-gate-{stem}"))
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            print(f"資源計測済み: {stem}", flush=True)
        result["passed"] = True
    except Exception as error:
        result["stopped_reason"] = repr(error)
        raise
    finally:
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"段3の走行関門合格: {result_path}", flush=True)


if __name__ == "__main__":
    main()
