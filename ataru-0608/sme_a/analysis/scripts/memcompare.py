"""3. 古い本番との記憶の比べ（読むだけ）。

同じ条件・種の古い本番（~/smeprod/sme、台帳だけ残っている）と (a) 版の本の台帳を、試行ごとに比べる。
  記憶の比べ：各試行の state_snapshot と agent_state_snapshot_hash（control/2026-10-06_SME_(a)の記憶とlogPの誕生_Codex.md の (1) と同じ）。
  台帳本体の比べ（参考）：見出しの行を除く各試行の行の全欄。alignment_event_id（対応の記録の印）の違いは別に数え、記憶の違いに数えない。
使い方：python3.12 memcompare.py [--redo]   … 完了した (a) の本のうち、まだ比べていない本を比べ、out/memory_compare_<条件>.csv を書き直す。
"""
import json
import resource
import sys
import time
from collections import Counter
from datetime import datetime

from common import (ARMS, MEM_DIR, OLD_ROOT, OLD_SHA, OUT, complete_runs, diff_paths, ledger_path,
                    ledger_rows, run_commit, run_dir, sha256_file, write_csv)

MEMORY_FIELDS = ("state_snapshot", "agent_state_snapshot_hash")


def excluded(path):
    return path.split(".")[-1] == "alignment_event_id"


def old_done(arm, seed):
    d = OLD_ROOT / arm / f"seed{seed:03d}"
    import glob
    return d if glob.glob(str(d / "ledgers/cells/*" / f"seed{seed:03d}.done")) else None


def old_sha_record(arm, seed):
    p = OLD_SHA / arm / "sha256.jsonl"
    if not p.exists():
        return None
    for line in p.read_text().splitlines():
        r = json.loads(line)
        if r.get("arm") == arm and r.get("seed") == seed:
            return r
    return None


def compare(arm, seed):
    t0, c0 = time.monotonic(), time.process_time()
    started = datetime.now().isoformat(timespec="seconds")
    old = old_done(arm, seed)
    res = {"arm": arm, "seed": seed, "new_commit": run_commit(arm, seed)[:7]}
    if old is None:
        res.update(status="古い本番の台帳なし")
        return res
    oldp, newp = ledger_path(old, seed), ledger_path(run_dir(arm, seed), seed)
    rec = old_sha_record(arm, seed)
    res["old_commit"] = json.loads((old / "flag.json").read_text()).get("commit", "")[:7]
    res["old_ledger_sha256_listed"] = rec["ledger_file_sha256"] if rec else ""
    res["old_ledger_sha256"] = sha256_file(oldp)
    res["old_ledger_sha256_matches_list"] = ("yes" if rec and rec["ledger_file_sha256"] == res["old_ledger_sha256"]
                                             else "no" if rec else "一覧に無い")
    mem_diff = {f: 0 for f in MEMORY_FIELDS}
    mem_trials = 0
    first_mem = None
    body_raw = body_excl = align_only = 0
    first_body = first_raw = None
    field_counts = Counter()
    n_old = n_new = 0
    header_diff = []
    oi, ni = ledger_rows(oldp), ledger_rows(newp)
    while True:
        a, b = next(oi, None), next(ni, None)
        if a is None and b is None:
            break
        if a is None or b is None:
            res["length_mismatch"] = "yes"
            n_old += a is not None
            n_new += b is not None
            for rest in (oi if a is not None else ni):
                if a is not None:
                    n_old += 1
                else:
                    n_new += 1
            break
        if a.get("record_type") == "run_header" or b.get("record_type") == "run_header":
            assert a.get("record_type") == b.get("record_type") == "run_header"
            header_diff = diff_paths(a, b)
            continue
        n_old += 1
        n_new += 1
        t = b.get("prediction_order")
        assert a.get("prediction_order") == t, (a.get("prediction_order"), t)
        # 記憶
        mem_bad = [f for f in MEMORY_FIELDS if a.get(f) != b.get(f)]
        for f in mem_bad:
            mem_diff[f] += 1
        if mem_bad:
            mem_trials += 1
            if first_mem is None:
                paths = []
                for f in mem_bad:
                    paths += [f + "." + p if p != "(全体)" else f for p in diff_paths(a.get(f), b.get(f))]
                first_mem = (t, paths)
        # 台帳本体（参考）
        if a != b:
            body_raw += 1
            paths = diff_paths(a, b)
            for p in paths:
                field_counts[p] += 1
            if first_raw is None:
                first_raw = (t, paths)
            rest = [p for p in paths if not excluded(p)]
            if rest:
                body_excl += 1
                if first_body is None:
                    first_body = (t, rest)
            else:
                align_only += 1
    res.update(status="ok", n_trials_old=n_old, n_trials_new=n_new, n_trials_compared=min(n_old, n_new),
               length_mismatch=res.get("length_mismatch", "no"),
               state_snapshot_diff_trials=mem_diff["state_snapshot"],
               agent_state_snapshot_hash_diff_trials=mem_diff["agent_state_snapshot_hash"],
               memory_diff_trials=mem_trials,
               memory_all_same="yes" if mem_trials == 0 and n_old == n_new else "no",
               first_memory_diff_trial="" if first_mem is None else first_mem[0],
               first_memory_diff_fields="" if first_mem is None else ";".join(first_mem[1][:20]),
               body_diff_trials_raw=body_raw,
               body_diff_trials_alignment_event_id_only=align_only,
               body_diff_trials_excluding_alignment_event_id=body_excl,
               first_body_diff_trial_raw="" if first_raw is None else first_raw[0],
               first_body_diff_fields_raw="" if first_raw is None else ";".join(first_raw[1][:20]),
               first_body_diff_trial_excluding_alignment_event_id="" if first_body is None else first_body[0],
               first_body_diff_fields_excluding_alignment_event_id="" if first_body is None else ";".join(first_body[1][:20]),
               body_diff_field_trial_counts=json.dumps(dict(sorted(field_counts.items())), ensure_ascii=False),
               header_diff_fields=";".join(header_diff),
               started=started, wall_seconds=round(time.monotonic() - t0, 2), cpu_seconds=round(time.process_time() - c0, 2),
               peak_rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1))
    return res


FIELDS = ["arm", "seed", "status", "old_commit", "new_commit", "old_ledger_sha256_matches_list",
          "n_trials_old", "n_trials_new", "n_trials_compared", "length_mismatch",
          "memory_all_same", "memory_diff_trials", "state_snapshot_diff_trials", "agent_state_snapshot_hash_diff_trials",
          "first_memory_diff_trial", "first_memory_diff_fields",
          "body_diff_trials_raw", "body_diff_trials_alignment_event_id_only", "body_diff_trials_excluding_alignment_event_id",
          "first_body_diff_trial_raw", "first_body_diff_fields_raw",
          "first_body_diff_trial_excluding_alignment_event_id", "first_body_diff_fields_excluding_alignment_event_id",
          "body_diff_field_trial_counts", "header_diff_fields",
          "old_ledger_sha256", "old_ledger_sha256_listed", "started", "wall_seconds", "cpu_seconds", "peak_rss_mb"]


def main():
    redo = "--redo" in sys.argv
    MEM_DIR.mkdir(parents=True, exist_ok=True)
    for arm, seed in complete_runs():
        p = MEM_DIR / arm / f"seed{seed:03d}.json"
        if p.exists() and not redo:
            continue
        r = compare(arm, seed)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n")
        print(f"{arm} 種{seed}: {r.get('status')} 記憶の同じ={r.get('memory_all_same')} 時間={r.get('wall_seconds')}秒", flush=True)
    for arm in ARMS:
        rows = [json.loads(p.read_text()) for p in sorted((MEM_DIR / arm).glob("seed*.json"))] if (MEM_DIR / arm).exists() else []
        if rows:
            write_csv(OUT / f"memory_compare_{arm}.csv", rows, FIELDS)


if __name__ == "__main__":
    main()
