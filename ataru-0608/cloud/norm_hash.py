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
def _norm_line(line):
    try: return json.dumps(strip(json.loads(line)), sort_keys=True, ensure_ascii=False).encode()
    except Exception: return line


def norm_hash(path, rel):
    """前の norm_bytes と全く同じ並びのバイトの sha256 を、ファイル全体を記憶に置かずに作る（10/09 22:30 の直し：
    大きい sme.states などで記憶を数十 GB 使い、クラウドの機械で OOM で落ちたため）。
    前の作り方：data（gz は展開）→ 台帳は最初の改行まで（見出し）を除く → .json は全体を JSON として書き直す →
    .jsonl は data.split(b"\n") の各要素を書き直して b"\n" でつなぐ。ここでは同じ要素の並びを一行ずつ作って足していく。"""
    h = hashlib.sha256()
    opener = (lambda: gzip.open(path, "rb")) if path.endswith(".gz") else (lambda: open(path, "rb"))
    name = rel[:-3] if rel.endswith(".gz") else rel
    ledger = rel.startswith("ledgers/") and rel.endswith(".jsonl.gz")
    if name.endswith(".json"):
        data = opener().read()
        if ledger:
            data = data.split(b"\n", 1)[1] if b"\n" in data else b""
        try: h.update(json.dumps(strip(json.loads(data)), sort_keys=True, ensure_ascii=False).encode())
        except Exception: h.update(data)
        return h.hexdigest()
    with opener() as f:
        if ledger:
            first = f.readline()
            if not first.endswith(b"\n"):
                # 改行が無い：前の作り方では data が b"" になる
                return hashlib.sha256(_norm_line(b"") if name.endswith(".jsonl") else b"").hexdigest()
        if not name.endswith(".jsonl"):
            for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
            return h.hexdigest()
        first_el = True; ended_nl = True
        for line in f:
            ended_nl = line.endswith(b"\n")
            el = line[:-1] if ended_nl else line
            if not first_el: h.update(b"\n")
            h.update(_norm_line(el)); first_el = False
        if ended_nl:
            # split は最後の改行の後に空の要素を一つ作る（ファイルが空でも一つ）
            if not first_el: h.update(b"\n")
            h.update(_norm_line(b""))
    return h.hexdigest()


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
        rows.append((rel, norm_hash(p, rel)))
with open(out, "w") as fo:
    for rel, h in sorted(rows): fo.write(f"{rel}\t{h}\n")
print(len(rows), "ファイル →", out)
