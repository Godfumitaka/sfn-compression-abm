"""段2：圧縮（2026-10-06、アストラの許可）。一度に一つずつ：gzip -k で写し → 展開した中身の sha256 が元と一致したら元を消す。
一致しなければ元を残し、写しを消して mismatch_gz.tsv へ。不一致が 10 件を超えたら止める。
~/smeprod/sme のファイルは、段0 で results の枝に上げた sha256（ataru-0608/sme_6e93e0b/*/sha256.jsonl）とも比べる。
一覧：compressed.tsv（パス・元の大きさ・圧縮後の大きさ・元の sha256）。各フォルダに README_圧縮.md。"""
import glob, gzip, hashlib, json, os, subprocess, sys, datetime
H = os.path.expanduser("~"); OUT = f"{H}/cleanup_2026-10-06"
targets = [l.split(" ", 1)[1].strip() for l in open(f"{OUT}/gz_targets_all.txt")]
stage0 = {}
for f in glob.glob(f"{H}/v33prod/results/ataru-0608/sme_6e93e0b/*/sha256.jsonl"):
    for l in open(f):
        r = json.loads(l)
        for name, v in r["side"].items(): stage0[(r["arm"], name)] = v["sha256"]
def sha(path, gz=False):
    h = hashlib.sha256()
    with (gzip.open(path, "rb") if gz else open(path, "rb")) as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
done = {l.split("\t")[0] for l in open(f"{OUT}/compressed.tsv")} if os.path.exists(f"{OUT}/compressed.tsv") else set()
cmp_ = open(f"{OUT}/compressed.tsv", "a"); mis = open(f"{OUT}/mismatch_gz.tsv", "a")
nmis = 0; before = after = 0; readme = {}
for i, rel in enumerate(targets):
    p = f"{H}/{rel}"
    if p in done or not os.path.exists(p): continue
    if os.path.exists(p + ".gz"):
        nmis += 1; mis.write(f"{p}\t.gz が既にある（触れない）\n"); mis.flush(); continue
    s0 = sha(p)
    if rel.startswith("smeprod/sme/"):
        arm = rel.split("/")[2]; ref = stage0.get((arm, os.path.basename(p)))
        if ref != s0:
            nmis += 1; mis.write(f"{p}\t段0 の sha256 と違う {s0} {ref}\n"); mis.flush()
            if nmis > 10: print("★ 不一致が 10 件を超えたので止める"); sys.exit(3)
            continue
    subprocess.run(["gzip", "-k", "-6", p], check=True)
    s1 = sha(p + ".gz", gz=True)
    if s1 != s0:
        os.remove(p + ".gz"); nmis += 1; mis.write(f"{p}\t展開の中身が違う {s0} {s1}\n"); mis.flush()
        if nmis > 10: print("★ 不一致が 10 件を超えたので止める"); sys.exit(3)
        continue
    a, b = os.path.getsize(p), os.path.getsize(p + ".gz")
    os.remove(p); before += a; after += b
    cmp_.write(f"{p}\t{a}\t{b}\t{s0}\n"); cmp_.flush()
    readme.setdefault(os.path.dirname(p), []).append((os.path.basename(p), a, b, s0))
    if i % 50 == 0: print(i, len(targets), f"{(before-after)/1e9:.2f}GB 減", flush=True)
today = datetime.date.today().isoformat()
for d, items in readme.items():
    with open(f"{d}/README_圧縮.md", "a", encoding="utf-8") as f:
        f.write(f"# 圧縮した記録（{today}、走行の係）\n\n"
                "中身を失わない掃除として、下のファイルを gzip で圧縮し、元を消した。展開した中身の sha256 が元と一致することを、消す前に確かめた。\n\n"
                "展開の仕方：`gunzip -k <ファイル>.gz`（.gz を残して元の名前で書き出す）、または `zcat <ファイル>.gz > <置き場所>`。\n\n"
                "注意：分類の道具（sealmem・selcands）は展開した side を読む。あとでこの走行を分類するときは、別の場所に展開した写しを作ってから読む（ここで展開し直してもよい）。\n\n"
                "| ファイル（元の名前） | 元の大きさ | 圧縮後 | 元の sha256 |\n|---|---:|---:|---|\n")
        for n, a, b, s in items: f.write(f"| {n} | {a} | {b} | {s} |\n")
print("終わり", f"元 {before/1e9:.3f}GB → {after/1e9:.3f}GB、{(before-after)/1e9:.3f}GB 減", "不一致", nmis)
