"""段1：重複を消す（2026-10-06、アストラの許可）。消す直前に各ファイルの sha256 を元ともう一度比べ、一致した普通のファイルとリンク（リンクそのもの、たどらない）だけを消す。
一致しないものは残して一覧へ。不一致が 10 件を超えたら止める。--dry で消さずに数えるだけ。
一覧：~/cleanup_2026-10-06/deleted.tsv（パス・大きさ・sha256・元の場所）、mismatch.tsv、links.tsv。"""
import gzip, hashlib, os, sys
H = os.path.expanduser("~"); OUT = f"{H}/cleanup_2026-10-06"; DRY = "--dry" in sys.argv
RES = f"{H}/v33prod/results/ataru-0608/sme_audit/check_runs_付帯"
PROD1 = f"{H}/smeprod/sme/w2_A_L50/seed001"

def sha(path, gz=False, skip_first=False):
    h = hashlib.sha256()
    with (gzip.open(path, "rb") if gz else open(path, "rb")) as f:
        if skip_first: f.readline()
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

VIEW = {"n3sel_view": lambda a: f"{H}/n3prod/{a}" if a.startswith("n3_") else f"{H}/n3lgrid/{a}",
        "lgrid_view": lambda a: f"{H}/lgrid/{a}", "chance_view": lambda a: f"{H}/chance/{a}", "dsel_view": lambda a: f"{H}/ufprod/full/{a}"}
CHECK = {"smefast_check": "w2_A_L50/seed001/", "smerng_check": "w2_A_L50/seed001/", "sme_audit/check4_sme": ""}

def original(top, rel):
    """(比べる元のパス, 比べ方) を返す。比べ方：'gz'＝元の .gz を展開、'raw'、'body'＝台帳の見出しを除く、'res'＝results の枝の写し。"""
    if top in VIEW:
        arm, r = rel.split("/", 1)
        o = os.path.join(VIEW[top](arm), r)
        if os.path.exists(o + ".gz"): return o + ".gz", "gz"
        if os.path.exists(o): return o, "raw"
        return None, None
    pre = CHECK[top]; name = os.path.basename(top)
    r = rel[len(pre):] if rel.startswith(pre) else None
    if r and r.startswith("ledgers/") and r.endswith(".jsonl.gz"): return os.path.join(PROD1, r), "body"
    if r and r.startswith("side/"): return os.path.join(PROD1, r), "raw"
    c = os.path.join(RES, name, rel)
    return (c, "res") if os.path.exists(c) else (None, None)

ded = open(f"{OUT}/deleted.tsv", "a"); mis = open(f"{OUT}/mismatch.tsv", "a"); lnk = open(f"{OUT}/links.tsv", "a")
nmis = 0; freed = 0; nfiles = 0; nlinks = 0
for top in list(VIEW) + list(CHECK):
    root = f"{H}/{top}"
    for dp, ds, fs in os.walk(root, topdown=True):
        for n in list(ds) + fs:
            p = os.path.join(dp, n); rel = os.path.relpath(p, root)
            if os.path.islink(p):
                nlinks += 1
                if not DRY: lnk.write(f"{p}\t{os.readlink(p)}\n"); os.unlink(p)
                continue
            if n in ds: continue
            o, how = original(top, rel)
            if o is None:
                nmis += 1; mis.write(f"{p}\t元が無い\n"); continue
            a = sha(p, gz=(how == "body"), skip_first=(how == "body"))
            b = sha(o, gz=(how in ("gz", "body")), skip_first=(how == "body"))
            if a != b:
                nmis += 1; mis.write(f"{p}\t{a}\t{o}\t{b}\n"); mis.flush()
                if nmis > 10: print("★ 不一致が 10 件を超えたので止める"); sys.exit(3)
                continue
            s = os.path.getsize(p); nfiles += 1; freed += s
            if not DRY:
                ded.write(f"{p}\t{s}\t{a}\t{o}{'（見出し一行を除く台帳本体の sha256）' if how == 'body' else ''}\n"); ded.flush()
                os.remove(p)
    print(top, "まで：消すファイル", nfiles, "リンク", nlinks, f"{freed/1e9:.2f}GB", "不一致", nmis, flush=True)
if not DRY:
    for top in list(VIEW) + list(CHECK):
        for dp, ds, fs in os.walk(f"{H}/{top}", topdown=False):
            if not os.listdir(dp): os.rmdir(dp)
print("終わり", "（数えただけ）" if DRY else "", nfiles, nlinks, f"{freed/1e9:.2f}GB", nmis)
