"""(b) を 20 種まで（2026-09-26）：走り終えた台帳を順に、クラウドの指紋（fp_*.json.gz）と比べる。★ 判定しない。
比べるもの：全試行の agent_state_snapshot_hash・行ごとの sha256 の頭 16 桁・見出しを除いた本体の sha256・本体の行数・見出しの全欄。
★ 見出しの code_commit だけは違って当然（クラウドは 556ef79、手元は --dump-slot-history を足した 70c1ba6 で走らせる）。
   違いとして記録するが、止める理由にはしない。それ以外が一つでも違えば MISMATCH を書き、走行を止める（アストラさんの指示）。
使い方  python3.12 tools/fp_check_v31.py <走行根> <指紋 json.gz> <走行の pid> <MISMATCH を書く場所>"""
import gzip, hashlib, json, os, subprocess, sys, time
from pathlib import Path

root, fpf, pid, mm = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), Path(sys.argv[4])
cloud = {(x["cell"], x["seed"]): x for x in json.load(gzip.open(fpf, "rt"))["ledgers"]}
print(f"{time.strftime('%F %T')} 指紋 {fpf}（{len(cloud)} 本）走行根 {root} pid {pid}", flush=True)
done = set()


def alive(p):
    try:
        os.kill(p, 0); return True
    except OSError:
        return False


def check(cell, seed):
    c = cloud.get((cell, seed))
    if c is None:
        return ["指紋に無い台帳"], []
    p = root / "ledgers" / "cells" / cell / f"seed{seed:03d}.jsonl.gz"
    snap, l16, body, header = [], [], hashlib.sha256(), None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == 0:
                header = json.loads(line); continue
            raw = line.encode("utf-8"); body.update(raw)
            l16.append(hashlib.sha256(raw).hexdigest()[:16]); snap.append(json.loads(line).get("agent_state_snapshot_hash"))
    bad = []
    if len(snap) != c["n_body"]: bad.append(f"本体の行 {len(snap)}／{c['n_body']}")
    if snap != c["snapshot_hashes"]: bad.append("試行の指紋")
    if l16 != c["line_sha16"]: bad.append("行ごとの sha16")
    if body.hexdigest() != c["body_sha256"]: bad.append("本体の sha256")
    hd = sorted(k for k in set(header) | set(c["header"]) if header.get(k) != c["header"].get(k))
    bad += [f"見出しの {k}" for k in hd if k != "code_commit"]
    return bad, [f"{k}: 手元 {header.get(k)}／クラウド {c['header'].get(k)}" for k in hd]


while True:
    running = alive(pid)
    man = root / "manifest.jsonl"
    rows = [json.loads(l) for l in man.read_text().splitlines()] if man.exists() else []
    for r in rows:
        k = (r["cell"], r["seed"])
        if k in done:
            continue
        done.add(k)
        bad, hd = check(*k)
        print(f"{time.strftime('%F %T')} {k[0]} seed{k[1]:03d} {'一致' if not bad else '不一致 ' + '・'.join(bad)}"
              f"｜見出しの違い {hd if hd else 'なし'}｜秒 {r.get('elapsed_sec')}", flush=True)
        if bad:
            mm.write_text(f"{time.strftime('%F %T')} {root} {k} {bad}\n")
            kids = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout.split()
            for q in [pid] + [int(x) for x in kids]:
                try: os.kill(q, 15)
                except OSError: pass
            print(f"{time.strftime('%F %T')} 不一致のため走行を止めた（pid {pid} と子 {kids}）", flush=True)
            sys.exit(1)
    if not running:
        print(f"{time.strftime('%F %T')} 走行が終わった。比べた台帳 {len(done)} 本（指紋 {len(cloud)} 本）", flush=True)
        break
    time.sleep(20)
