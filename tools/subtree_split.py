"""読むだけ（2026-09-26）：中心的過程を通った定義（L=6・3）を、中身の部分木（T1〜T4・一番上）で分ける。★ 判定しない。
(a) 走行末の生きている行の述語だけで：一つの部分木に収まる／二つ以上にまたがる。
    ★ 生きている行の述語は、各腕のまとめの side の最後の行（alive_end・last_alive_preds）から取る（rows2 と同じ時点＝走行末）。
    ★ 述語 → 部分木は種ファイル（subtrees・motif_structure）から作る。一番上（govern・sustainedby）は独立の単位「一番上」として数える。
       構造の述語でないもの（媒介・飾り・周縁・役割ユナリー）が混ざれば「構造外」として数える（生きている行には無いはず）。
(b) 墓石の席の slot_history まで含めて：★ この版では作れない（台帳の最後の状態が要る。手元に無い）。
分類ごとに
    見ていない型（版 5）の世界偽の率 ＝（五未見未話 ＋ 五未見話）の世界偽 ÷（世界偽＋世界真）。defs_spoke5 の n_unseen2・wf_unseen2・n_unseen2_spoke・wf_unseen2_spoke。
    外で当たる／外で外す（2026-09-26 の呼び名）：中心的過程（L）を通り、内の世界偽の率 5% 以下、内外とも主張 20 本以上。外 ≤5% で外で当たる、外 ≥50% で外で外す。
      内外は版 5：内 ＝ 見た（五見話＋五見未話）、外 ＝ 見ていない（五未見未話＋五未見話）。
使い方  python3.12 tools/subtree_split.py <出力.md> <まとめの場所> <腕> ..."""
import collections, csv, io, json, statistics as st, sys, tarfile
from pathlib import Path
B = Path("/Users/tatsu-admin/sfn/sfn-compression-abm")
out, PULL, arms = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
seed = json.load(open(B / "seeds/U-011_seed_v3a2.json"))
UNIT = {}
def walk(tname, top):
    node = seed["subtrees"][tname]
    UNIT[node["higher"]] = top
    for c in node.get("subtrees", []):
        walk(c, top)
    for p in node.get("first_order", []):
        UNIT[p] = top
for m, row in seed["motif_structure"].items():
    UNIT[row["third"]] = "一番上"
    for t in row["subtrees"]:
        walk(t, t)


def latest(pat):
    return sorted(PULL.glob(pat))[-1]


def num(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0


L = ["# 中心的過程を通った定義の、中身の部分木による分け（(a) 生きている行だけ）　判定しない", "",
     "★ 部分木：T1〜T4 と一番上（govern・sustainedby）を単位にした。述語はどれも一つの単位にだけ属する（種ファイルから）。",
     "★ 見ていない型（版 5）の世界偽の率 ＝ 見ていない型の主張の世界偽 ÷（世界偽＋世界真）を、分類の中の定義で合計した値。",
     "★ 外で当たる／外で外す：内（見た）の世界偽 ≤5%、内外とも主張 ≥20 の定義のうち、外（見ていない）≤5% ／ ≥50%。", ""]
for arm in arms:
    pack = latest(f"{arm}_hide_s1*.tar.gz")
    tf = tarfile.open(pack)
    side_member = [m for m in tf.getmembers() if m.name.endswith("side.tar.gz")][0]
    side = tarfile.open(fileobj=io.BytesIO(tf.extractfile(side_member).read()))
    alive_preds = {}
    for m in side.getmembers():
        if not m.name.endswith(".jsonl"):
            continue
        parts = m.name.split("/"); cell, sd = parts[-2], parts[-1].replace(".jsonl", "")
        fin = None
        for line in side.extractfile(m).read().decode().splitlines():
            if '"kind": "final"' in line:
                fin = json.loads(line)
        for R in fin["alive_end"]:
            alive_preds[(cell, sd, R)] = fin["last_alive_preds"].get(R, [])
    sp = tarfile.open(latest(f"spoke5_{arm}_hide_s1*.tar.gz"))
    dm = [m for m in sp.getmembers() if m.name.endswith(".csv") and "defs_spoke" in m.name][0]
    T = list(csv.DictReader(io.StringIO(sp.extractfile(dm).read().decode("utf-8"))))
    L += [f"## {arm}（まとめ {pack.name}・{dm.name.split('/')[-1]}）", "",
          "| L | 分け | 定義 | 見ていない型の世界偽の率（世界偽／主張） | 外で当たる | 外で外す | 対象（内≤5%・両側≥20） |",
          "|---:|---|---:|---:|---:|---:|---:|"]
    miss_alive = 0
    for Lx in (6, 3):
        C = collections.defaultdict(collections.Counter)
        for r in T:
            if r[f"L{Lx}"] != "1":
                continue
            cell, sd, R = r["defid"].split("/")
            preds = alive_preds.get((cell, sd, R))
            if preds is None:
                miss_alive += 1; continue
            units = {UNIT.get(p, "構造外") for p in preds}
            k = "一つの部分木" if len(units) == 1 else "二つ以上にまたがる"
            if "構造外" in units:
                k += "（構造外あり）"
            c = C[k]; c["定義"] += 1
            nu = num(r["n_unseen2"]) + num(r["n_unseen2_spoke"]); wu = num(r["wf_unseen2"]) + num(r["wf_unseen2_spoke"])
            ns = num(r["n_seen2_spoke"]) + num(r["n_seen2_quiet"]); ws = num(r["wf_seen2_spoke"]) + num(r["wf_seen2_quiet"])
            c["nu"] += nu; c["wu"] += wu
            if ns >= 20 and nu >= 20 and ws / ns <= 0.05:
                c["対象"] += 1
                ro = wu / nu
                c["外で当たる"] += ro <= 0.05; c["外で外す"] += ro >= 0.5
            c["単位" + str(len(units))] += 1
        for k in sorted(C):
            c = C[k]
            rate = f"{c['wu']/c['nu']:.4f}（{int(c['wu']):,}／{int(c['nu']):,}）" if c["nu"] else "—"
            L.append(f"| {Lx} | {k} | {c['定義']:,} | {rate} | {c['外で当たる']:,} | {c['外で外す']:,} | {c['対象']:,} |")
    if miss_alive:
        L.append(f"\n★ 通過したのに走行末の生存の記録が無い定義：{miss_alive}（数えていない）")
    L.append("")
Path(out).write_text("\n".join(L) + "\n", encoding="utf-8")
print("->", out)
