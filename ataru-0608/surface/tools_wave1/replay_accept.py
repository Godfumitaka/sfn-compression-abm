"""受け箱の指示 73 の 1：2a の再生の採用の確かめ（再生の台本・模型は変えない、replay.json も書き換えない）。
replay.json の status が failed で、errors が「旗の違い ['config']」だけ、flag_diff が ['config'] だけ、台帳本体の違う行 0、side の違い無し、
候補の記録の行が試行の数と同じ本について、本番の設定ファイル（AWS の m7a の上の同じ置き場、~/surface/replay_config_sha_aws_m7a.txt）と
再生の設定ファイル（デスクトップ）の sha256 が同じで、本番と再生の manifest の world_hash・seed_file_sha256 も同じなら「採用」。
結果は ~/surface/replay_accept.json（arm/seedNNN → 採用か、理由、両方の sha256）。"""
import glob, hashlib, json
from pathlib import Path
H = Path.home(); AWS = {l.split()[1]: l.split()[0] for l in open(H / "surface/replay_config_sha_aws_m7a.txt")}
out = {}
for rj in sorted(glob.glob(str(H / "surface/replay/q2*/seed*/replay.json"))):
    d = json.load(open(rj)); key = rj.split("/replay/")[1].rsplit("/", 1)[0]
    prod = json.load(open(Path(d["run_dir"]) / "flag.json")); rep = json.load(open(Path(d["kept_tmp"]) / "out/flag.json"))
    pm = json.loads(open(Path(d["run_dir"]) / "manifest.jsonl").readline()); rm = json.loads(open(Path(d["kept_tmp"]) / "out/manifest.jsonl").readline())
    ps, rs = AWS.get(prod["config"]), hashlib.sha256(open(rep["config"], "rb").read()).hexdigest()
    checks = {"status": d["status"] in ("ok", "failed"), "errors_config_only": d["errors"] in ([], ["旗の違い ['config']"]),
              "flag_diff_config_only": d.get("flag_diff") in ([], ["config"]), "ledger_body_diff_rows_0": d.get("ledger_body_diff_rows") == 0,
              "side_same": d.get("side_diff") == {}, "candidate_rows_all": d.get("candidate_rows") == d.get("ledger_body_rows") == pm["trial_count"],
              "config_sha256_same": ps is not None and ps == rs,
              "manifest_world_seed_same": (pm["world_hash"], pm["seed_file_sha256"]) == (rm["world_hash"], rm["seed_file_sha256"])}
    out[key] = dict(adopted=all(checks.values()), checks=checks, production_config=prod["config"], production_config_sha256=ps,
                    replay_config=rep["config"], replay_config_sha256=rs, replay_status=d["status"])
json.dump(out, open(H / "surface/replay_accept.json", "w"), ensure_ascii=False, indent=1)
print(len(out), "本、採用", sum(v["adopted"] for v in out.values()))
for k, v in out.items():
    if not v["adopted"]: print("採用しない", k, [c for c, ok in v["checks"].items() if not ok])
