"""stage2 の記録を、時間の欄（名前に seconds・sec・time・elapsed を含む鍵）を除いて比べる。最初の違いと、違いのあった鍵の名前を出す。"""
import gzip, json, sys, re
A, B = sys.argv[1], sys.argv[2]
TIME = re.compile(r"(second|^sec$|_sec$|sec_|time|elapsed|wall|clock)", re.I)
keys_seen = set()
def strip(o):
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if TIME.search(str(k)): keys_seen.add(k); continue
            out[k] = strip(v)
        return out
    if isinstance(o, list): return [strip(x) for x in o]
    return o
def lines(p):
    if p.endswith(".gz"):
        with gzip.open(p, "rt", encoding="utf-8") as f: return f.read().splitlines()
    return open(p, encoding="utf-8").read().splitlines()
la, lb = lines(A), lines(B)
if len(la) != len(lb): print("★ 行の数が違う", len(la), len(lb)); sys.exit(1)
raw_diff = sum(1 for x, y in zip(la, lb) if x != y)
for i, (x, y) in enumerate(zip(la, lb)):
    if x == y: continue
    try: sx, sy = strip(json.loads(x)), strip(json.loads(y))
    except Exception: print("★ JSON でない行が違う", i); sys.exit(1)
    if sx != sy: print("★ 時間の欄を除いても違う 行", i, json.dumps(sx, ensure_ascii=False)[:300]); sys.exit(1)
print(f"同じ（時間の欄を除く）。行 {len(la)}、生のまま違った行 {raw_diff}、除いた鍵 {sorted(keys_seen)}")
