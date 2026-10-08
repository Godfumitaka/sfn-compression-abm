"""一本の出力の「比べ用の sha256」の一覧を作る（読むだけ）。デスクトップとクラウドの出力を、ファイルを運ばずに比べるため。
- gzip は展開した中身で比べる。
- 台帳（ledgers の seed*.jsonl.gz）は見出しの一行を除く。
- JSON（一行ずつ、又はファイル全体）は、名前が時間を表す鍵（seconds・sec・time・elapsed・wall・clock を含む）を除き、鍵の順をそろえて書き直してから比べる。
- 付帯の記録（flag.json・manifest.jsonl・*.done）は比べから外し、一覧に「付帯」と書く。
使い方：norm_hash.py <出力のフォルダ> <一覧の TSV>   ／   norm_hash.py --compare <一覧 A> <一覧 B>"""
import gzip, hashlib, json, os, re, sys
TIME = re.compile(r"(second|^sec$|_sec$|sec_|time|elapsed|wall|clock)", re.I)
def strip(o):
    if isinstance(o, dict): return {k: strip(v) for k, v in o.items() if not TIME.search(str(k))}
    if isinstance(o, list): return [strip(x) for x in o]
    return o
def norm_bytes(path, rel):
    data = gzip.open(path, "rb").read() if path.endswith(".gz") else open(path, "rb").read()
    if rel.startswith("ledgers/") and rel.endswith(".jsonl.gz"):
        data = data.split(b"\n", 1)[1] if b"\n" in data else b""
    name = rel[:-3] if rel.endswith(".gz") else rel
    if name.endswith(".json"):
        try: return json.dumps(strip(json.loads(data)), sort_keys=True, ensure_ascii=False).encode()
        except Exception: return data
    if name.endswith(".jsonl"):
        out = []
        for line in data.split(b"\n"):
            try: out.append(json.dumps(strip(json.loads(line)), sort_keys=True, ensure_ascii=False).encode())
            except Exception: out.append(line)
        return b"\n".join(out)
    return data
if sys.argv[1] == "--compare":
    a = dict(l.rstrip("\n").split("\t") for l in open(sys.argv[2]))
    b = dict(l.rstrip("\n").split("\t") for l in open(sys.argv[3]))
    keys = sorted(set(a) | set(b)); bad = [k for k in keys if a.get(k) != b.get(k) and a.get(k) != "付帯" and b.get(k) != "付帯"]
    print(f"ファイル {len(keys)}、違い {len(bad)}"); [print("★", k, a.get(k), b.get(k)) for k in bad]
    sys.exit(1 if bad else 0)
root, out = sys.argv[1], sys.argv[2]
rows = []
for dp, ds, fs in os.walk(root):
    for f in fs:
        p = os.path.join(dp, f); rel = os.path.relpath(p, root)
        if f in ("flag.json", "manifest.jsonl") or f.endswith(".done"): rows.append((rel, "付帯")); continue
        rows.append((rel, hashlib.sha256(norm_bytes(p, rel)).hexdigest()))
with open(out, "w") as fo:
    for rel, h in sorted(rows): fo.write(f"{rel}\t{h}\n")
print(len(rows), "ファイル →", out)
