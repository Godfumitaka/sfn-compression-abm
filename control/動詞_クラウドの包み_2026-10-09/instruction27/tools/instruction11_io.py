"""指示11の原記録の読み手。模型の欄・順・数値を変えない。"""
from pathlib import Path
import gzip, hashlib, json, re, zlib

TIME_KEYS = frozenset(("seconds", "wrapper_seconds", "engine_seconds",
                      "rematch_fraction_of_stage2_seconds"))
ROOTS = frozenset(("ledgers", "side", "evictions", "attention", "stage2", "researcher"))

def sha(data):
    return hashlib.sha256(data).hexdigest()

def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("x") as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2)+"\n")

def content(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as f:
            return f.read()
    return path.read_bytes()

def confirmed_content(path):
    """監督中のgzipも、flush済みの完全な行だけを別の証拠へ写す。"""
    path = Path(path)
    if path.suffix != ".gz":
        data = path.read_bytes()
    else:
        obj = zlib.decompressobj(31)
        pieces = []
        with path.open("rb") as f:
            while raw := f.read(1024*1024):
                while raw:
                    pieces.append(obj.decompress(raw))
                    raw = obj.unused_data
                    if obj.eof and raw:
                        obj = zlib.decompressobj(31)
                    else:
                        break
        data = b"".join(pieces)
    assert not data or data.endswith(b"\n"), "確定していない行は比較へ入れない"
    return data

def copy_confirmed(path, destination):
    """確認済みの記録を小分けに写す。gzip容器の閉じを補作しない。"""
    path,destination=Path(path),Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256();size=0;last=b""
    obj=zlib.decompressobj(31) if path.suffix==".gz" else None
    with path.open("rb") as f,destination.open("xb") as g:
        while raw:=f.read(1024*1024):
            while raw:
                if obj is None:data,raw=raw,b""
                else:
                    data=obj.decompress(raw);raw=obj.unused_data
                    if obj.eof and raw:obj=zlib.decompressobj(31)
                    elif not raw:raw=b""
                if data:
                    g.write(data);digest.update(data);size+=len(data);last=data[-1:]
    assert not size or last==b"\n", "確定前の行を補わない"
    return dict(sha256=digest.hexdigest(),bytes=size)

def compare_paths(path, left, right, *, raw_evidence=False):
    """字節を小分けに比べ、TIME以外の順や数値を作り直さない。"""
    path,left,right=Path(path),Path(left),Path(right)
    def opener(p):
        return gzip.open(p,"rb") if p.suffix==".gz" and not raw_evidence else p.open("rb")
    time_only=path.parts[0]=="stage2"
    def chunks(p):
        with opener(p) as f:
            if not time_only:
                while data:=f.read(1024*1024):yield data
            elif path.suffix==".json" and not path.name.endswith(".jsonl"):
                yield without_time(f.read())
            else:
                # 一行の字節を保持する。比較用の読み幅だけを同じに揃える。
                buffer=b""
                for line in f:
                    buffer+=without_time(line)
                    while len(buffer)>=1024*1024:
                        yield buffer[:1024*1024];buffer=buffer[1024*1024:]
                if buffer:yield buffer
    from itertools import zip_longest
    hashes=[hashlib.sha256(),hashlib.sha256()];sizes=[0,0];bad=0;first=None;example=None;n=0
    for x,y in zip_longest(chunks(left),chunks(right),fillvalue=b""):
        for i,data in enumerate((x,y)):hashes[i].update(data);sizes[i]+=len(data)
        if x!=y:
            bad+=sum(a!=b for a,b in zip(x,y))+abs(len(x)-len(y))
            if first is None:
                j=next((j for j,(a,b) in enumerate(zip(x,y)) if a!=b),min(len(x),len(y)))
                first=n+j;example=dict(left=x[max(0,j-80):j+160].decode("utf-8","replace"),
                                      right=y[max(0,j-80):j+160].decode("utf-8","replace"))
        n+=max(len(x),len(y))
    return dict(path=str(path),equal=first is None,left_sha256=hashes[0].hexdigest(),
                right_sha256=hashes[1].hexdigest(),content_bytes=sizes,mismatching_bytes=bad,
                first_mismatch_byte=first,example=example,
                mode="TIME値だけ除いた全バイト" if time_only else "内容の全バイト")

def names(folder):
    return {p.relative_to(folder) for p in Path(folder).rglob("*")
            if p.is_file() and p.relative_to(folder).parts[0] in ROOTS
            and p.suffix != ".done"}

def without_time(data):
    """D-07αυ(a)。許されたTIME欄の値だけを印にし、他の字節はそのまま。"""
    text = data.decode("utf-8")
    # JSONはまず検証する。行の順・空白・キーの順を作り直さない。
    try:
        json.loads(text)
    except json.JSONDecodeError:
        for line in text.splitlines():
            json.loads(line)
    keys = "|".join(re.escape(x) for x in TIME_KEYS)
    pattern = re.compile(r'("(?:'+keys+r')"\s*:\s*)(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|null)')
    return pattern.sub(r'\g<1>0', text).encode("utf-8")

def byte_row(path, x, y, mode="全バイト"):
    bad = sum(a != b for a, b in zip(x, y))+abs(len(x)-len(y))
    first = next((i for i, (a,b) in enumerate(zip(x,y)) if a != b),
                 min(len(x),len(y))) if x != y else None
    return dict(path=str(path), equal=x==y, mode=mode,
                left_sha256=sha(x), right_sha256=sha(y),
                content_bytes=[len(x),len(y)], mismatching_bytes=bad,
                first_mismatch_byte=first,
                example=None if first is None else dict(
                    left=x[max(0,first-80):first+160].decode("utf-8","replace"),
                    right=y[max(0,first-80):first+160].decode("utf-8","replace")))

def compare_outputs(left, right, *, confirmed=False):
    left, right = Path(left), Path(right)
    a, b = names(left), names(right)
    rows = []
    for rel in sorted(a|b):
        if rel not in a or rel not in b:
            rows.append(dict(path=str(rel), equal=False, left_exists=rel in a,
                             right_exists=rel in b, mismatching_bytes=None))
            continue
        if confirmed:
            x,y=confirmed_content(left/rel),confirmed_content(right/rel)
            raw=dict(left_content_sha256=sha(x),right_content_sha256=sha(y))
            if rel.parts[0]=="stage2":x,y=without_time(x),without_time(y)
            row=byte_row(rel,x,y)
        else:
            def digest_content(path):
                h=hashlib.sha256()
                opener=gzip.open if path.suffix==".gz" else open
                with opener(path,"rb") as f:
                    while data:=f.read(1024*1024):h.update(data)
                return h.hexdigest()
            raw=dict(left_content_sha256=digest_content(left/rel),
                     right_content_sha256=digest_content(right/rel))
            row=compare_paths(rel,left/rel,right/rel)
        rows.append({**row,**raw,"left_exists":True,"right_exists":True})
    return dict(passed=bool(rows) and a==b and all(r["equal"] for r in rows),
                file_count=len(rows), mismatching_files=sum(not r["equal"] for r in rows),
                files=rows)
