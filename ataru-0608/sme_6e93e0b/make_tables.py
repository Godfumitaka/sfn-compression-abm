"""SME 版の本番の走行の記録（flag・台帳本体の sha256・試行ごとの表）を、条件ごとにまとめる。読むだけ（何も消さない・動かさない）。
使い方：make_tables.py <出力の根（~/smeprod/sme など）> <書き出し先>
書き出し先/<条件>/flag_seedNNN.json、sha256.jsonl（種ごと：台帳本体の sha256・行数・code_commit・side の各ファイルの sha256 と大きさ）、
trials.tsv.gz（試行ごと：seed trial f_fired f_realized outcome abstain_reason door shop_type shop_cue door_pred）。完了印（.done）のある本だけ。"""
import glob
import gzip
import hashlib
import json
import os
import sys

root, dest = sys.argv[1], sys.argv[2]


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


for arm in sorted(os.listdir(root)):
    rows, shas = [], []
    for run in sorted(glob.glob(f"{root}/{arm}/seed*")):
        led = glob.glob(f"{run}/ledgers/cells/*/seed*.jsonl.gz")
        if not led or not glob.glob(f"{run}/ledgers/cells/*/seed*.done"):
            continue
        seed = int(os.path.basename(run)[4:7])
        h = hashlib.sha256()
        n = 0
        with gzip.open(led[0], "rt", encoding="utf-8") as f:
            header = json.loads(f.readline())
            for t, line in enumerate(f):
                h.update(line.encode("utf-8"))
                n += 1
                r = json.loads(line)
                kind = "a" if r["prediction_kind"] == "Abstain" else ("c" if r["hit"] == 1 else "w")
                rows.append((seed, t, int(bool(r.get("f_fired"))), r.get("f_realized"), kind, r.get("abstain_reason") or "",
                             int(bool(r.get("held_out_is_door"))), r.get("shop_type", ""), r.get("shop_cue", ""), r.get("door_pred", "")))
        side = {os.path.basename(p): {"sha256": sha_file(p), "bytes": os.path.getsize(p)} for p in sorted(glob.glob(f"{run}/side/*/*"))}
        shas.append({"arm": arm, "seed": seed, "body_sha256": h.hexdigest(), "n_body": n, "code_commit": header.get("code_commit"),
                     "ledger_file_sha256": sha_file(led[0]), "side": side})
        os.makedirs(f"{dest}/{arm}", exist_ok=True)
        with open(f"{run}/flag.json", "rb") as a, open(f"{dest}/{arm}/flag_seed{seed:03d}.json", "wb") as b:
            b.write(a.read())
    if not shas:
        continue
    with open(f"{dest}/{arm}/sha256.jsonl", "w", encoding="utf-8") as f:
        for s in shas:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    with gzip.open(f"{dest}/{arm}/trials.tsv.gz", "wt", encoding="utf-8") as f:
        f.write("seed\ttrial\tf_fired\tf_realized\toutcome\tabstain_reason\tdoor\tshop_type\tshop_cue\tdoor_pred\n")
        for x in rows:
            f.write("\t".join("" if v is None else str(v) for v in x) + "\n")
    print(arm, len(shas), "本", flush=True)
