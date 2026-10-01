"""腕 D の報告の表（委任書 5 節の 2〜4）。使い方：report_tables.py <腕の名前…>  → 標準出力に markdown。
2：学習期間中（全 1,740 試行）の平均の記憶のビット（tools/v39.py total_bits、削除の段のあと）、全課題・ドアの課題（通常・例外別）の正解・誤答・棄権、
   成績の曲線（174 試行ずつ 10 区間の正解・誤答・棄権）。種 1〜20 の和（記憶のビットは試行と種の平均）。
3：診断（side/*/seed*.useforget.jsonl.gz）：
   - 一度も名前を使われないまま名前を失った席の割合（誕生の一回のほかに使用 0 で、U 又は退役になった席／名前を失った席）
   - 同じ試行に薄くなった席の割合（同じ定義の席がほかにも同じ試行に名前を失った席／名前を失った席）
   - 定義の中の席どうしの S のばらつき（10 試行ごとの写しで、生きている席が 2 つ以上の定義ごとの標準偏差の分布：25・50・75・90% 点）
   - 誕生の次の試行で薄くなった割合（名前を失った試行＝誕生の試行＋1 の席／名前を失った席）
4：シール・link・根・T 階の席の S と状態（10 試行ごとの写しを 174 試行ずつにまとめ、種類ごとの生きている席の数の平均と S の中央値。
   名前を失った席の数を種類ごとに）。"""
import glob
import gzip
import json
import os
import statistics
import sys

OUT = os.environ.get("UFOUT") or os.path.expanduser("~/ufprod")


def opn(p):
    return gzip.open(p, "rt", encoding="utf-8") if p.endswith(".gz") else open(p, encoding="utf-8")


def q(v, x):
    if not v:
        return float("nan")
    v = sorted(v)
    h = x * (len(v) - 1)
    i = int(h)
    return v[i] if i + 1 >= len(v) else v[i] + (h - i) * (v[i + 1] - v[i])


def cwa(rows):
    n = len(rows)
    c = sum(1 for r in rows if r[3] == "c")
    w = sum(1 for r in rows if r[3] == "w")
    return n, c, w, n - c - w


def fmt(t):
    n, c, w, a = t
    return f"{n:,} | {c:,} | {w:,} | {a:,}"


def table2(arms):
    print("### 学習期間中の平均の記憶のビットと、正解・誤答・棄権（種 1〜20 の和）\n")
    print("| 腕 | τ | 平均の記憶のビット | 全課題：課題 | 正解 | 誤答 | 棄権 | ドア・通常：課題 | 正解 | 誤答 | 棄権 | ドア・例外：課題 | 正解 | 誤答 | 棄権 |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    curves = {}
    for arm in arms:
        rows = [l.rstrip("\n").split("\t") for l in gzip.open(f"{OUT}/tables/{arm}/trials.tsv.gz", "rt", encoding="utf-8")][1:]
        bits = statistics.fmean(float(r[9]) for r in rows)
        door_n = [r for r in rows if r[5] == "1" and r[7] == "n"]
        door_e = [r for r in rows if r[5] == "1" and r[7] == "e"]
        tau = json.load(open(f"{OUT}/{arm}/flag.json")).get("use_forget", "") if os.path.exists(f"{OUT}/{arm}/flag.json") else ""
        print(f"| {arm} | {tau if isinstance(tau, str) else f'{tau:.6g}'} | {bits:,.0f} | {fmt(cwa(rows))} | {fmt(cwa(door_n))} | {fmt(cwa(door_e))} |")
        curves[arm] = [cwa([r for r in rows if b * 174 <= int(r[1]) < (b + 1) * 174]) for b in range(10)]
    print("\n### 成績の曲線（174 試行ずつ。正解／誤答／棄権、種 1〜20 の和）\n")
    print("| 腕 | " + " | ".join(f"{b*174}〜{b*174+173}" for b in range(10)) + " |")
    print("|---|" + "---|" * 10)
    for arm, cs in curves.items():
        print(f"| {arm} | " + " | ".join(f"{c}／{w}／{a}" for _, c, w, a in cs) + " |")


def table34(arms):
    print("\n### 診断（名前を失った席）\n")
    print("| 腕 | 名前を失った席 | 使用 0 のまま失った | 同じ試行に同じ定義のほかの席も失った | 誕生の次の試行で失った | 定義の中の S の標準偏差 25／50／75／90% 点 |")
    print("|---|---:|---:|---:|---:|---|")
    kinds_rows = {}
    for arm in arms:
        n = never = same = nextb = 0
        sds = []
        kb = {}   # (種類, 区間) → [生きている数の和, 写しの数, S の一覧]
        kf = {}
        for p in sorted(glob.glob(f"{OUT}/{arm}/side/*/seed*.useforget.jsonl*")):
            for line in opn(p):
                r = json.loads(line)
                fg = r["forgot"]
                byR = {}
                for x in fg:
                    byR[x[0]] = byR.get(x[0], 0) + 1
                for x in fg:
                    n += 1
                    never += x[7] == 0
                    same += byR[x[0]] >= 2
                    nextb += x[5] is not None and r["trial"] == x[5] + 1
                    for k in (x[8] or ["そのほか"]):
                        kf[k] = kf.get(k, 0) + 1
                if "snap" in r:
                    b = min(r["trial"] // 174, 9)
                    per = {}
                    cnt = {}
                    for R, s, reg, st, S, kd in r["snap"]:
                        per.setdefault(R, []).append(S)
                        for k in (kd or ["そのほか"]):
                            e = kb.setdefault((k, b), [0, 0, []])
                            e[2].append(S)
                            cnt[k] = cnt.get(k, 0) + 1
                    for k in ("シール", "link", "根", "T 階", "そのほか"):
                        e = kb.setdefault((k, b), [0, 0, []])
                        e[0] += cnt.get(k, 0)
                        e[1] += 1
                    sds.extend(statistics.pstdev(v) for v in per.values() if len(v) >= 2)
        pct = lambda a: f"{a:,}（{a / n:.1%}）" if n else "0"   # noqa: E731
        print(f"| {arm} | {n:,} | {pct(never)} | {pct(same)} | {pct(nextb)} | " + "／".join(f"{q(sds, x):.3g}" for x in (0.25, 0.5, 0.75, 0.9)) + " |")
        kinds_rows[arm] = (kb, kf)
    print("\n### シール・link・根・T 階の席：生きている席の数（写しあたりの平均）と S の中央値、174 試行ずつ\n")
    for arm, (kb, kf) in kinds_rows.items():
        print(f"\n{arm}（名前を失った席の数：" + "、".join(f"{k} {v:,}" for k, v in sorted(kf.items())) + "）\n")
        print("| 種類 | " + " | ".join(f"{b*174}〜" for b in range(10)) + " |")
        print("|---|" + "---|" * 10)
        for k in ("シール", "link", "根", "T 階", "そのほか"):
            cells = []
            for b in range(10):
                e = kb.get((k, b))
                cells.append(f"{e[0] / e[1]:.1f}・{q(e[2], 0.5):.3g}" if e and e[1] else "—")
            print(f"| {k} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    arms = sys.argv[1:]
    table2(arms)
    table34(arms)
