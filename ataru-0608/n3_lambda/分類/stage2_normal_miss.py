"""段 2：N3・世界 2・A・λ＝0.0187（n3l_w2_A_lam0.0187）の通常の日のドアの外れで、何が選ばれたか。記録を読むだけ。
材料：selcands の候補の記録（通常の日の外れだけを作り直したもの、~/n3sel_out/selcands_n/<腕>/seed*.cands.jsonl.gz）。
  候補ごとに：N3 と三項（名前・引数・つながり）、S(d,x)、S(d,d)、S(x,x)、シール・ドア・link の席（状態・述語・履歴・写り先）、
  その定義での答え（選びのあとの段をその定義でやり直したもの）。作り直しは本物と全件一致を確かめてある。
  （--select-log の記録 select.jsonl.gz の N3 と、作り直した N3 は同じ数え方。選ばれた定義の N3 が一致することを下で確かめる。）
選ばれた定義：N3 の並べ方（N3 → 席の数 → 新しさ → 名前）の一位。正しく答える定義：使えば門を通って正しく答える候補のうち、同じ並べ方で一番上。
シールの席の名前：F は述語、H は履歴で回数がいちばん多い名（同数なら名の順の最初）、U は名前なし。席が無ければ「席なし」。二つ以上なら並べる。
仮説（Claude、未確認）に合う件：選ばれた定義のシールの席の名前が sig_e（場面は通常の日なので sig_n）。合わない件：それ以外（sig_n・U・席なし）。"""
import glob
import gzip
import json
import os
from collections import Counter

H = os.path.expanduser("~")
ARM = "n3l_w2_A_lam0.0187"
D = f"{H}/n3sel_out/selcands_n/{ARM}"
KEY = lambda c: (-c["N3"], -c["分母"], -c["生まれた試行"], c["R"])  # noqa: E731


def seal(c):
    out = []
    for s in c["ドア・シール・link の席"]:
        if s["種類"] != "シール":
            continue
        if s["状態"] == "F":
            nm = s["述語"]
        elif s["状態"] == "H":
            h = s["履歴"] or {}
            nm = sorted(h.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if h else None
        else:
            nm = None
        out.append((s["状態"], nm, s["写り先は見えている"]))
    return out


def seal_str(c):
    ss = seal(c)
    return "席なし" if not ss else "／".join(f"{st}{'・' + nm if nm else ''}" for st, nm, _v in ss)


selog = {}
for p in glob.glob(f"{H}/n3lgrid/{ARM}/side/*/seed*.select.jsonl.gz"):
    seed = int(os.path.basename(p)[4:7])
    for l in gzip.open(p, "rt", encoding="utf-8"):
        r = json.loads(l)
        s = [c for c in r["cands"] if c["selected"]]
        if s:
            selog[(seed, r["t"])] = s[0]

cases = {}
for p in sorted(glob.glob(f"{D}/seed*.cands.jsonl.gz")):
    for l in gzip.open(p, "rt", encoding="utf-8"):
        c = json.loads(l)
        cases.setdefault((c["seed"], c["trial"]), []).append(c)

T = Counter()
rows = []
hyp = Counter()
for (seed, t), v in sorted(cases.items()):
    if v[0]["本物の当たり"]:
        continue
    v = sorted(v, key=KEY)
    ch = v[0]
    good = [c for c in v if c["その定義での答え"]["当たり"] and c["その定義での答え"]["門を通る"]]
    g = good[0] if good else None
    lg = selog.get((seed, t))
    T["外れ"] += 1
    T["select.jsonl の選ばれた定義と N3 が一致"] += bool(lg) and lg["R"] == ch["R"] and abs(lg["N3"] - ch["N3"]) < 1e-9
    names = [nm for _st, nm, _v in seal(ch)]
    if "sig_e" in names:
        k = "合う：選ばれた定義のシールの名前が sig_e"
    elif "sig_n" in names:
        k = "合わない：選ばれた定義のシールの名前が sig_n"
    elif seal(ch):
        k = "合わない：選ばれた定義のシールの席が U"
    else:
        k = "合わない：選ばれた定義にシールの席が無い"
    hyp[k] += 1
    rows.append((seed, t, ch, g, k))

print(f"## 段 2：{ARM} の通常の日のドアの外れ（{T['外れ']} 件。作り直しで本物と全件一致。select.jsonl の選ばれた定義と N3 が一致：{T['select.jsonl の選ばれた定義と N3 が一致']} 件）\n")
print("### 仮説に合う件・合わない件\n")
print("| 分け方 | 件数 |\n|---|---:|")
for k, n in sorted(hyp.items()):
    print(f"| {k} | {n} |")
print("\n### 選ばれた定義のシールの席の状態と、その定義のドアの答え\n")
st = Counter((seal_str(ch), ch["その定義での答え"]["答え"] or "黙り") for _s, _t, ch, _g, _k in rows)
print("| シールの席（状態・名前） | ドアの答え | 件数 |\n|---|---|---:|")
for (a, b), n in st.most_common():
    print(f"| {a} | {b} | {n} |")
print("\n### 正しく答える定義の有無と、N3 の比べ\n")
ng = [r for r in rows if r[3] is not None]
print(f"- 正しく答える定義があった外れ（選び間違い）：{len(ng)} 件、無かった外れ（区別の喪失）：{len(rows) - len(ng)} 件。")
if ng:
    import statistics
    d = [r[2]["N3"] - r[3]["N3"] for r in ng]
    print(f"- 選び間違いで、選ばれた定義の N3 − 正しく答える定義の N3：中央値 {statistics.median(d):.4f}、最小 {min(d):.4f}、最大 {max(d):.4f}、同点 {sum(abs(x) < 1e-12 for x in d)} 件。")
    sg = Counter(seal_str(r[3]) for r in ng)
    print("- 正しく答える定義のシールの席（状態・名前）：" + "、".join(f"{k} {v}" for k, v in sg.most_common()))
print("\n### 外れの一覧（N3 の三項：名前・引数・つながり。S(d,x)／S(d,d)／S(x,x)）\n")
print("| 種 | 試行 | 選ばれた定義 | シール | ドアの答え | N3 | 三項 | S(d,x)／S(d,d)／S(x,x) | 正しく答える定義 | そのシール | その N3 | 三項 | S(d,x)／S(d,d)／S(x,x) | 仮説 |")
print("|---:|---:|---|---|---|---:|---|---|---|---|---:|---|---|---|")
for seed, t, ch, g, k in rows:
    def tri(c):
        b = c["N3 の分子の内訳"]
        return f"{b['名前']}・{b['引数']}・{b['つながり']}", f"{c['N3 の分子 S(d,x)']}／{c['自己の点 S(d,d)']}／{c['自己の点 S(x,x)']}"
    a1, a2 = tri(ch)
    gc = ("—",) * 5 if g is None else (g["R"], seal_str(g), f"{g['N3']:.4f}", *tri(g))
    print(f"| {seed} | {t} | {ch['R']} | {seal_str(ch)} | {ch['その定義での答え']['答え'] or '黙り'} | {ch['N3']:.4f} | {a1} | {a2} | " + " | ".join(gc) + f" | {k.split('：')[0]} |")
print("\n### 代表の 3 試行の候補ごとの量（N3 の順）\n")
reps = []
for kk in ("合う", "合わない"):
    reps += [r for r in rows if r[4].startswith(kk)][:2 if kk == "合う" else 1]
for seed, t, _ch, _g, k in reps[:3]:
    print(f"\n#### 種 {seed}・試行 {t}（{k}）\n")
    print("| N3 の順位 | 定義 | F/H/U | 支持 | N3 | 三項 | S(d,x)／S(d,d)／S(x,x) | シール | ドアの答え | 門 | 当たり |")
    print("|---:|---|---|---|---:|---|---|---|---|---|---|")
    for i, c in enumerate(sorted(cases[(seed, t)], key=KEY)):
        b = c["N3 の分子の内訳"]
        a = c["その定義での答え"]
        print(f"| {i + 1} | {c['R']} | {c['F']}/{c['H']}/{c['U']} | {c['分子']}／{c['分母']} | {c['N3']:.4f} | {b['名前']}・{b['引数']}・{b['つながり']} | "
              f"{c['N3 の分子 S(d,x)']}／{c['自己の点 S(d,d)']}／{c['自己の点 S(x,x)']} | {seal_str(c)} | {a['答え'] or '黙り'} | {'通る' if a['門を通る'] else '通らない'} | {'○' if a['当たり'] else '×'} |")
