"""腕のあと：全部の種の台帳から試行ごとの小さな表を作り、台帳の本体の sha256 を控えてから、決まりどおり最初の二つの種の台帳だけ残す。
使い方：extract.py <腕の置き場所> <表の置き場所> <残す種（例 1,2）>
表 trials.tsv.gz の列：seed trial f_fired outcome(c/w/a) abstain_reason door(1/0) shop_type shop_cue door_pred bits_after defs
  bits_after・defs は side/<セル>/seed<種>.jsonl の kind=v39 の行（tools/v39.py total_bits、その試行の削除の段のあと）。
台帳を消すのは、その種の表の行が 1,740 そろい、sha256 を書けたときだけ。"""
import glob
import gzip
import hashlib
import json
import os
import sys

root, dest, keep = sys.argv[1], sys.argv[2], {int(x) for x in sys.argv[3].split(",")}
os.makedirs(dest, exist_ok=True)
ledgers = sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.jsonl.gz")))
sha_rows, out_rows, ok_seeds = [], [], []
for p in ledgers:
    if not os.path.exists(p[:-len(".jsonl.gz")] + ".done"):
        continue
    cell = os.path.basename(os.path.dirname(p))
    seed = int(os.path.basename(p)[4:7])
    side = os.path.join(root, "side", cell, f"seed{seed:03d}.jsonl")
    bits = {}
    with open(side, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("kind") == "v39":
                bits[r["trial"]] = (r["bits_after"], r["defs"])
    h = hashlib.sha256()
    n = 0
    header = None
    rows = []
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == 0:
                header = json.loads(line)
                continue
            h.update(line.encode("utf-8"))
            n += 1
            r = json.loads(line)
            if r.get("record_type") != "trial":
                continue
            t = len(rows)   # 台帳の試行の行は試行の順（番号の欄は無い）
            kind = "a" if r["prediction_kind"] == "Abstain" else ("c" if r["hit"] == 1 else "w")
            b, nd = bits.get(t, ("", ""))
            rows.append((seed, t, int(bool(r["f_fired"])), kind, r.get("abstain_reason") or "", int(bool(r.get("held_out_is_door"))),
                         r.get("shop_type", ""), r.get("shop_cue", ""), r.get("door_pred", ""), b, nd))
    sha_rows.append({"cell": cell, "seed": seed, "body_sha256": h.hexdigest(), "n_body": n, "code_commit": (header or {}).get("code_commit")})
    out_rows.extend(rows)
    if len(rows) == 1740 and all(x[9] != "" for x in rows):
        ok_seeds.append((seed, p))
    else:
        print(f"★ {root} 種 {seed}：試行の行 {len(rows)}、記憶のビットの欠け {sum(1 for x in rows if x[9] == '')}。台帳は消さない")
with gzip.open(os.path.join(dest, "trials.tsv.gz"), "wt", encoding="utf-8") as f:
    f.write("seed\ttrial\tf_fired\toutcome\tabstain_reason\tdoor\tshop_type\tshop_cue\tdoor_pred\tbits_after\tdefs\n")
    for x in out_rows:
        f.write("\t".join(str(v) for v in x) + "\n")
with open(os.path.join(dest, "sha256.jsonl"), "w", encoding="utf-8") as f:
    for r in sha_rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
removed = 0
for seed, p in ok_seeds:
    if seed not in keep:
        os.remove(p)
        removed += 1
print(f"{root}：表 {len(out_rows)} 行・種 {len(sha_rows)}、台帳を消した種 {removed}（残す {sorted(keep)}）")
