"""6e93e0b などの本番の大きな状態を消す（2026-10-06、アストラの許可）。
list：消すファイルごとに sha256 と大きさを計算し、results の枝の ataru-0608/sme_6e93e0b/*/sha256.jsonl に載っているかを確かめて
      del6e93_list.tsv に書く（載っていない／圧縮後の .gz は、ここで計算した値を足す）。
delete：一覧のファイルの大きさと更新時刻が一覧を作ったときと同じことを確かめて消す。各本のフォルダに README_消去.md を置く。"""
import glob, hashlib, json, os, sys, datetime
H = os.path.expanduser("~"); OUT = f"{H}/cleanup_2026-10-06"; LIST = f"{OUT}/del6e93_list.tsv"
KINDS = (".sme.states.jsonl.gz", ".sme.jsonl.gz", ".sme.diagnostics.jsonl.gz", ".routing.jsonl.gz", ".useforget.jsonl.gz", ".cflearn.jsonl.gz")
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
def kind(name):
    for k in KINDS:
        if name.endswith(k): return k
    import re
    if re.fullmatch(r"seed\d{3}\.jsonl\.gz", name): return "seed*.jsonl.gz（side）"
    return None
if sys.argv[1] == "list":
    ref = {}
    for f in glob.glob(f"{H}/v33prod/results/ataru-0608/sme_6e93e0b/*/sha256.jsonl"):
        for l in open(f):
            r = json.loads(l)
            for n, v in r["side"].items(): ref[(r["arm"], r["seed"], n)] = v
    comp = {}
    for l in open(f"{H}/v33prod/results/ataru-0608/cleanup_2026-10-06/compressed.tsv"):
        p, a, b, s = l.rstrip("\n").split("\t"); comp[p] = (a, s)
    rows = []
    for run in sorted(glob.glob(f"{H}/smeprod/sme/*/seed*")):
        arm, seed = run.split("/")[-2], int(run[-3:])
        for p in sorted(glob.glob(f"{run}/side/*/*")):
            n = os.path.basename(p); k = kind(n)
            if not k: continue
            s = sha(p); st = os.stat(p); r = ref.get((arm, seed, n))
            if r: note = "sha256.jsonl に載っている・一致" if (r["sha256"] == s and r["bytes"] == st.st_size) else "★ sha256.jsonl と違う"
            elif p[:-3] in comp: note = f"sha256.jsonl には圧縮前の {n[:-3]} が載っている（元 {comp[p[:-3]][0]} バイト・sha256 {comp[p[:-3]][1]}）。.gz の値はここで足した"
            else: note = "載っていない。ここで足した"
            rows.append((p, st.st_size, s, k, note, st.st_mtime_ns))
    for top in ("stopped_2026-10-05", "止まった"):
        for dp, ds, fs in os.walk(f"{H}/smeprod/{top}"):
            for n in sorted(fs):
                p = os.path.join(dp, n); st = os.stat(p)
                rows.append((p, st.st_size, sha(p), f"途中で止めた本（{top}）", "載っていない。ここで足した", st.st_mtime_ns))
    with open(LIST, "w") as f:
        f.write("path\tbytes\tsha256\tkind\tsha256_source\tmtime_ns\n")
        for r in rows: f.write("\t".join(map(str, r)) + "\n")
    bad = [r for r in rows if r[4].startswith("★")]
    print(len(rows), "ファイル", f"{sum(r[1] for r in rows)/1e9:.2f}GB", "★ 不一致", len(bad))
elif sys.argv[1] == "delete":
    rows = [l.rstrip("\n").split("\t") for l in open(LIST)][1:]
    if any(r[4].startswith("★") for r in rows): sys.exit("★ 一覧に不一致がある。消さない")
    freed = 0; runs = {}
    for p, b, s, k, src, mt in rows:
        st = os.stat(p)
        if st.st_size != int(b) or st.st_mtime_ns != int(mt): sys.exit(f"★ 一覧を作ったあとで変わった：{p}")
    for p, b, s, k, src, mt in rows:
        os.remove(p); freed += int(b)
        if "/smeprod/sme/" in p: runs.setdefault(p.split("/side/")[0], set()).add(k)
    for top in ("stopped_2026-10-05", "止まった"):
        for dp, ds, fs in os.walk(f"{H}/smeprod/{top}", topdown=False):
            if not os.listdir(dp): os.rmdir(dp)
    today = datetime.date.today().isoformat()
    for run, ks in runs.items():
        arm, seed = run.split("/")[-2], run[-3:]
        with open(f"{run}/README_消去.md", "w", encoding="utf-8") as f:
            f.write(f"# 消した記録（{today}、走行の係、アストラの許可）\n\n"
                    f"消した種類：{'、'.join(sorted(ks))}（side の下）。\n\n"
                    "残したもの：台帳（ledgers の seed*.jsonl.gz）、answers.csv、shop.jsonl、ambig.csv（あれば）、flag.json・manifest.jsonl・.done、README_圧縮.md。\n\n"
                    "元の sha256 の場所（results-2026-09-27 の枝）：\n"
                    f"- ataru-0608/sme_6e93e0b/{arm}/sha256.jsonl（種 {int(seed)} の行。side の各ファイルの、圧縮前の sha256 と大きさ）\n"
                    "- ataru-0608/cleanup_2026-10-06/compressed.tsv（圧縮した各ファイルの元の大きさ・sha256）\n"
                    "- ataru-0608/cleanup_2026-10-06/del6e93_list.tsv（消した各ファイルの、消す直前の大きさ・sha256）\n\n"
                    "★ 保存状態（sme.states）と照合の記録（sme.jsonl）を消したので、この本の誤りの型（選び間違い・区別の喪失）を、保存した記憶の再生で分類することは、もうできない。"
                    "台帳本体と試行ごとの表（ataru-0608/sme_6e93e0b/<条件>/trials.tsv.gz）は残っている。\n")
    print("消した", len(rows), "ファイル", f"{freed/1e9:.2f}GB", "README_消去.md", len(runs), "本")
