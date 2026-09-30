"""保存した結果の指紋・版・空き容量を記録する。台帳は変更しない。"""
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
RESULTS = ROOT.parents[1] / "codex_v310ans_2026-09-30/results"
TARGET = RESULTS / "mac/v311cu_1on1"


def physical_sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(1024*1024):
            h.update(block)
    return h.hexdigest()


def ledger_info(path):
    h = hashlib.sha256()
    count = 0
    with gzip.open(path,"rt",encoding="utf-8") as f:
        next(f)
        for line in f:
            h.update(line.encode("utf-8"))
            count += 1
    relative = path.relative_to(TARGET)
    if relative.parts[0] == "acceptance":
        source = ROOT / "outputs" / Path(*relative.parts[1:])
    else:
        source = ROOT / "outputs" / relative
    sha = physical_sha(path)
    assert sha == physical_sha(source)
    return {"path":str(relative),"bytes":path.stat().st_size,"file_sha256":sha,"body_sha256":h.hexdigest(),"body_rows":count}


if __name__ == "__main__":
    paths = sorted(TARGET.rglob("ledgers/cells/*/*.jsonl.gz"))
    assert len(paths) == 54, len(paths)
    with ThreadPoolExecutor(max_workers=3) as ex:
        ledgers = list(ex.map(ledger_info, paths))
    assert sum(p["body_rows"] for p in ledgers if not p["path"].startswith("acceptance/")) == 62640
    pops = json.loads((RESULTS / "control/2026-09-30_集団化_一対一_urta_Codex.json").read_text())
    commit = subprocess.check_output(["git","rev-parse","v3.11cu-main^{commit}"],cwd=SOURCE,text=True).strip()
    flags = {name:json.loads((TARGET/name/"flag.json").read_text()) for name in [arm+"_"+c for arm in ["L50","lam020"] for c in ["recvA","recvB","no_comm"]]}
    for name, flag in flags.items():
        assert flag["hist_role"] and flag["score_role"] and flag["v39_price"] == (0.01873710622997919 if name.startswith("L50_") else 0.2)
        assert all(flag[k] for k in ["u_struct","relearn_init","tie_struct","amb_local"])
        assert flag["commit"] == commit
        assert flag["v311c"]["runs"] == "1,2,3" and flag["v311c"]["f"] == "0.5,0.5"
    free = shutil.disk_usage(ROOT).free
    meta = {"date":"2026-09-30","python":"3.12.13","code_branch":"codex-collective-urta","code_tag":"v3.11cu-main",
            "code_commit":commit,"baseline_tag":"v3.10urta-main","baseline_commit":"74b60da63b640929810b693b93228fb3d1bfbc45",
            "world_trials":62640,"population_runs":18,"agents_per_run":2,"trials_per_agent":1740,
            "population_seeds":[1,2,3],"world_seeds":[1,2,3,1001,1002,1003],"probe_world_seeds":[900001,900002,900003],
            "forbidden_seeds_21_40_used":False,"eight_agent_runs":0,"deleted_files":0,
            "flag_files":flags,"source_files":json.loads((ROOT/"outputs/executed_code_sha256.json").read_text()),
            "original_output_root":str(ROOT/"outputs"),"free_bytes":free,"ledgers":ledgers,
            "world_input_sha256":[{"condition":p["condition"],"run":p["run"],"agent_sha256":p["world_input_sha256"]} for p in pops]}
    path = TARGET / "metadata.json"
    if path.exists():
        raise RuntimeError(f"既存の記録がある：{path}")
    path.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n")
    shutil.copy2(__file__,TARGET/"derive_metadata.py")
    readme = """# 集団化の一対一（Codex、2026-09-30）

コード：v3.11cu-main。基準：v3.10urta-main。2体、f=0.5、λ=L50・0.2。
各価格の recvA・recvB は送信確率0.2、no_comm は送信なし。各集団の種1〜3、各個体1,740試行。

各条件の ledgers/ は原本をそのまま保存した台帳。side/ と comm/ の jsonl は圧縮して保存した補助記録と通信記録。元の未圧縮の記録も専用作業場所に保持している。
acceptance/ に受入検査の台帳18本と検査の件数・指紋を保存した。本走行の台帳36本と合わせて54本。

name_tables.csv.gz は最終の名札回数表。wrong_provenance.csv.gz は誤答ごとの席の出どころと受信の由来。metadata.json は原本とのファイル一致と台帳本文の指紋、版、種、空き容量。
報告：control/2026-09-30_集団化_一対一_urta_Codex.md。

derive_report.py と derive_metadata.py は記録を読むだけの集計台本。専用作業場所の collective_report_urta.py と metadata_export_urta.py の写し。
verify_provenance_snapshots.py は台帳の前試行の状態と通信記録による独立照合。provenance_checks/ に各集団の照合件数を保存。
再集計は元の未圧縮の補助記録を使う。derive_report.py の第1引数に元の専用作業ルートを渡す。既存の報告を上書きせずに停止する。

台帳本体の指紋は、圧縮を解き、見出し1行を除いた全行をUTF-8のままSHA-256へ加えた値（tools/prod_post_one.pyのbody_shaと同じ）。
"""
    (TARGET/"README.md").write_text(readme)
    print(json.dumps({"保存台帳":len(ledgers),"世界課題":62640,"空きGB":round(free/1e9,3)},ensure_ascii=False),flush=True)
