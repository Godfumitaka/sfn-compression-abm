"""LLM の小さな試し：お店の世界の場面を文字列にする道具（仕様 v2 の 1・2 節、委任書「LLM の小さな試し・第一段」の段 1）。
★ LLM に渡すのは文字列だけ。研究者の側の記録（型・シール・世界・伏せた関係・正解）は別に返し、LLM には渡さない。

世界（仕様 v2 の 1 節）：骨組み 甲＝型 M1・乙＝型 M2（種 tools/shop/U-011_seed_shop.json の motif_structure と subtrees を abm/world.py _expand_motif で展開）。
  シール：物 a に付く一引数の関係（通常 sig_n／例外 sig_e）。link：attach(シール, 一番上の関係)。
  ドア：T1 の最初の一階の葉（経路 0.0.0）。述語は世界の表（X＝hold、Y＝hold_b）。
  役割の一引数の関係（role_unary：甲 supported・乙 carried、引数は物 b）：仕様 v2 の 2 節が外す付け足しの関係は「仲立ち・周縁・つなぎ」の三つで、
  これは挙がっていないので入れる（読み。報告に書く）。
場面の文字列（2 節）：一行に一本「rN: 述語(引数, 引数)」。関係は r＋数字、物は o＋数字。番号と行の順は場面ごとにでたらめ。
  関係の番号は 10〜99 から重ならずに、物の番号は 1〜9 から重ならずに引く（仮の決定）。述語は組ごとの固定の無意味語（同じ長さ）。
伏せ方：一本だけ伏せ、その行を消し、親の引数のその番号を「?」にする。「?」は一つだけ。
  そのため伏せられるのは親を持つ関係だけ（link と role_unary は親が無いので伏せない。仮の決定）。
学習の系列（1 節）：40 場面（甲・通常 16、甲・例外 4、乙・通常 16、乙・例外 4）。順番は組ごとにでたらめ。
  半分（20 場面、どの場面かは組ごとにでたらめ）でドアを伏せ、残りは、ドア以外の伏せられる関係から一様に一本。世界 1・2 で同じ順番と伏せ方。
試験（5 節）：ドア 4 問（四つの場合）と共有部分 2 問（甲乙で共通の、ドア以外の伏せられる関係から組ごとに二つ）。
  試験の場面は組ごとに一度作って固定し、4 回の時点で同じものを使う（仮の決定）。
"""
from __future__ import annotations

import json
import os
import random
import re
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, W)

SEED_FILE = os.path.join(W, "tools/shop/U-011_seed_shop.json")
TYPES = {"甲": "M1", "乙": "M2"}
DOOR_PATH = "0.0.0"
X, Y = "hold", "hold_b"
CASES = [("甲", "n"), ("甲", "e"), ("乙", "n"), ("乙", "e")]
COUNTS = {("甲", "n"): 16, ("甲", "e"): 4, ("乙", "n"): 16, ("乙", "e"): 4}


def door_pred(world, typ, cue):
    if world == 1:
        return X if typ == "甲" else Y
    return X if (typ == "甲") == (cue == "n") else Y


def skeleton(typ):
    """[(経路, 述語, 子の経路の並び or None)]。abm/world.py _expand_motif と同じ展開。"""
    import abm.world as w
    from abm.seed import load_seed
    sd = load_seed(SEED_FILE)
    return [(path, pred, children) for _i, (_lvl, path, pred, children) in w._expand_motif(sd.data, TYPES[typ])]


def all_predicates():
    from abm.seed import load_seed
    sd = load_seed(SEED_FILE)
    ps = set()
    for typ in TYPES:
        for _p, pred, _c in skeleton(typ):
            ps.add(pred)
        ps.add(sd.data["role_unary"][TYPES[typ]])
    return sorted(ps | {Y, "sig_n", "sig_e", "attach"})


def vocab(set_seed, length=4):
    """組ごとの無意味語（子音＋母音を交互に、同じ長さ、重ならない）。"""
    rng = random.Random(f"vocab|{set_seed}")
    cons, vows = "bdfgklmnprstvz", "aeiou"
    words = set()
    out = {}
    for p in all_predicates():
        while True:
            wd = "".join(rng.choice(cons if i % 2 == 0 else vows) for i in range(length))
            if wd not in words:
                words.add(wd)
                out[p] = wd
                break
    return out


def relations(typ, cue, world):
    """研究者の側の場面（番号の前）：[(名, 述語, 引数の名の並び)]。名は経路（骨組み）・"sig"・"link"・"role"。物は "a"・"b"。"""
    from abm.seed import load_seed
    sd = load_seed(SEED_FILE)
    rels = []
    for path, pred, children in skeleton(typ):
        if path == DOOR_PATH:
            pred = door_pred(world, typ, cue)
        rels.append((path, pred, tuple(children) if children else ("a", "b")))
    rels.append(("sig", "sig_e" if cue == "e" else "sig_n", ("a",)))
    rels.append(("link", "attach", ("sig", "root")))
    rels.append(("role", sd.data["role_unary"][TYPES[typ]], ("b",)))
    return rels


def parents_of(rels):
    out = {}
    for name, _p, args in rels:
        for a in args:
            out.setdefault(a, []).append(name)
    return out


def hideable(rels):
    """伏せられる関係（親を持つ関係）の名。"""
    par = parents_of(rels)
    names = {n for n, _p, _a in rels}
    return [n for n, _p, _a in rels if n in par and n in names]


def render(rels, hidden, rng, voc):
    """場面の文字列と、研究者の側の記録（番号の対応・伏せた関係・正解の記号）。"""
    names = [n for n, _p, _a in rels]
    nums = rng.sample(range(10, 100), len(names))
    rid = {n: f"r{k}" for n, k in zip(names, nums)}
    oid = {o: f"o{k}" for o, k in zip(("a", "b"), rng.sample(range(1, 10), 2))}
    lines = []
    for n, p, args in rels:
        if n == hidden:
            continue
        shown = ["?" if a == hidden else (rid[a] if a in rid else oid[a]) for a in args]
        lines.append(f"{rid[n]}: {voc[p]}({', '.join(shown)})")
    rng.shuffle(lines)
    truth = next(p for n, p, _a in rels if n == hidden)
    return "\n".join(lines), {"rid": rid, "oid": oid, "hidden": hidden, "hidden_rid": rid[hidden], "truth_pred": truth,
                              "truth_symbol": voc[truth]}


def make_set(set_seed, world, view="v1", mult=1, door_all=False, exc=None):
    """一組：学習の系列 40 場面と試験の場面。世界 1・2 で順番・伏せ方・番号の引き方は同じ（述語だけ表に従って変わる）。
    view＝"v2" のときは見せ方 v2（render_v2：字下げの決まった順）で書く。順番・伏せ方・番号は v1 と同じ（乱数の引き方が同じ）。
    mult：各場合の場面の数を COUNTS の何倍にするか（2 なら 80 場面）。door_all：全部の場面でドアを伏せる。どちらも乱数の引き方の規則は同じ。
    exc：例外の割合（店ごとに round(20×mult×exc) 場面を例外に。None なら COUNTS のまま＝0.2）。"""
    voc = vocab(set_seed)
    render = globals()["render_v2"] if view == "v2" else globals()["render"]
    rng = random.Random(f"order|{set_seed}")
    counts = {c: COUNTS[c] * mult for c in CASES}
    if exc is not None:
        # 例外の割合を変える（委任書「例外を増やす・大きな模型」2026-10-02 昼）：店ごとの場面の数（20×mult）のうち、例外を round(数×割合)
        per_shop = 20 * mult
        for typ in TYPES:
            counts[(typ, "e")] = round(per_shop * exc)
            counts[(typ, "n")] = per_shop - counts[(typ, "e")]
    seq = [c for c in CASES for _ in range(counts[c])]
    rng.shuffle(seq)
    door_pos = set(rng.sample(range(len(seq)), len(seq) // 2))
    if door_all:
        # 全部の場面でドアを伏せる（委任書「全履歴の段階」2026-10-02 朝の段階 2・4）。乱数の流れを変えないよう、引いたうえで全部にする
        door_pos = set(range(len(seq)))
    series = []
    seen = {c: 0 for c in CASES}
    for i, (typ, cue) in enumerate(seq):
        rels = relations(typ, cue, world)
        hid_rng = random.Random(f"hide|{set_seed}|{i}")
        if i in door_pos:
            hidden = DOOR_PATH
        else:
            cands = [n for n in hideable(rels) if n != DOOR_PATH]
            hidden = hid_rng.choice(sorted(cands))
        text, rec = render(rels, hidden, random.Random(f"num|{set_seed}|{i}"), voc)
        seen[(typ, cue)] += 1
        series.append({"i": i, "text": text, "answer": rec["truth_symbol"],
                       "research": {"type": typ, "cue": cue, "world": world, "door_hidden": hidden == DOOR_PATH, **rec,
                                    "seen_after": {f"{t}・{c}": v for (t, c), v in seen.items()}}})
    # 試験：ドア 4 問・共有部分 2 問（組ごとに固定）
    shared_cands = sorted(set(hideable(relations("甲", "n", world))) & set(hideable(relations("乙", "n", world)))
                          - {DOOR_PATH, "sig"})
    shared_cands = [n for n in shared_cands if n.startswith("0") or n == "root"]
    srng = random.Random(f"shared|{set_seed}")
    shared = srng.sample(shared_cands, 2)
    tests = []
    for k, (typ, cue) in enumerate(CASES):
        text, rec = render(relations(typ, cue, world), DOOR_PATH, random.Random(f"test|{set_seed}|door|{k}"), voc)
        tests.append({"kind": "ドア", "text": text, "answer": rec["truth_symbol"],
                      "research": {"type": typ, "cue": cue, "world": world, **rec}})
    for k, name in enumerate(shared):
        typ, cue = CASES[k * 2 % 4]
        text, rec = render(relations(typ, cue, world), name, random.Random(f"test|{set_seed}|shared|{k}"), voc)
        tests.append({"kind": "共有", "text": text, "answer": rec["truth_symbol"],
                      "research": {"type": typ, "cue": cue, "world": world, **rec}})
    return {"set_seed": set_seed, "world": world, "vocab": voc, "series": series, "tests": tests, "shared_paths": shared}


LINE = re.compile(r"^(r\d+): ([a-z]+)\((.*)\)$")


def parse(text):
    """文字列を読み直す：{関係の番号: (述語, 引数の並び)}。形が崩れていれば ValueError。"""
    rels = {}
    for ln in text.split("\n"):
        m = LINE.match(ln)
        if not m:
            raise ValueError(f"行の形が違う：{ln}")
        args = [a.strip() for a in m.group(3).split(",")]
        if m.group(1) in rels:
            raise ValueError("関係の番号が重なる")
        rels[m.group(1)] = (m.group(2), args)
    return rels


def verify(text, research, voc):
    """読み直した場面を、研究者の側の場面と突き合わせる。返り値：食い違いの並び（空なら一致）。"""
    out = []
    try:
        got = parse(text)
    except ValueError as e:
        return [str(e)]
    rid, oid = research["rid"], research["oid"]
    inv = {v: k for k, v in rid.items()}
    oinv = {v: k for k, v in oid.items()}
    rels = relations(research["type"], research["cue"], research["world"])
    want = {n: (p, args) for n, p, args in rels}
    q = 0
    for r, (sym, args) in got.items():
        for a in args:
            if a == "?":
                q += 1
            elif not (a in got or a in oinv or a == research["hidden_rid"]):
                out.append(f"引数 {a} が関係でも物でもない")
        n = inv.get(r)
        if n is None or n == research["hidden"]:
            out.append(f"{r} が研究者の側に無い／伏せた関係")
            continue
        p, wargs = want[n]
        if voc[p] != sym:
            out.append(f"{r} の述語が違う")
        exp = ["?" if a == research["hidden"] else (rid[a] if a in rid else oid[a]) for a in wargs]
        if exp != args:
            out.append(f"{r} の引数が違う")
    if q != 1:
        out.append(f"「?」が {q} 個")
    if set(inv[r] for r in got) != {n for n in want if n != research["hidden"]}:
        out.append("関係の集まりが違う")
    return out


def save_set(st, out_dir):
    """LLM に渡すもの（文字列と答え）と、研究者の側の記録を別のファイルに書く。"""
    os.makedirs(out_dir, exist_ok=True)
    base = f"set{st['set_seed']}_w{st['world']}"
    llm = {"series": [{"i": s["i"], "text": s["text"], "answer": s["answer"]} for s in st["series"]],
           "tests": [{"k": k, "text": t["text"], "answer": t["answer"]} for k, t in enumerate(st["tests"])]}
    res = {"vocab": st["vocab"], "shared_paths": st["shared_paths"],
           "series": [{"i": s["i"], **s["research"]} for s in st["series"]],
           "tests": [{"k": k, "kind": t["kind"], **t["research"]} for k, t in enumerate(st["tests"])]}
    json.dump(llm, open(os.path.join(out_dir, base + "_llm.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(res, open(os.path.join(out_dir, base + "_研究者.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return base


# ---------------------------------------------------------------- 見せ方 v2（委任書「理解検査」の段 C）：意味は変えず、つながりを追いやすい決まった順にする
def render_v2(rels, hidden, rng, voc):
    """行の順：親を持たない関係から始め（親の関係の引数を持つものが先、その中は関係の並びの順）、親の行のすぐ下に子の行を
    引数の順に、深さごとに二つの空白で字下げして置く（深さ優先）。番号は場面ごとにでたらめ（関係 10〜99、物 1〜9）。
    伏せた関係の行は消し、親の引数のその番号を「?」にする（伏せた関係の子の行は、伏せた関係の位置の深さのまま残す）。"""
    names = [n for n, _p, _a in rels]
    nums = rng.sample(range(10, 100), len(names))
    rid = {n: f"r{k}" for n, k in zip(names, nums)}
    oid = {o: f"o{k}" for o, k in zip(("a", "b"), rng.sample(range(1, 10), 2))}
    by = {n: (p, args) for n, p, args in rels}
    par = parents_of(rels)
    tops = [n for n in names if n not in par]
    tops.sort(key=lambda n: (0 if any(a in by for a in by[n][1]) else 1, names.index(n)))
    lines = []

    def emit(n, depth):
        p, args = by[n]
        if n != hidden:
            shown = ["?" if a == hidden else (rid[a] if a in rid else oid[a]) for a in args]
            lines.append("  " * depth + f"{rid[n]}: {voc[p]}({', '.join(shown)})")
        for a in args:
            if a in by:
                emit(a, depth + 1)

    for t in tops:
        emit(t, 0)
    if hidden is None:
        # 何も伏せない完全な場面（委任書「全履歴の段階」追記の段階 2：過去の場面を完全な観察済みの場面として見せる）
        return "\n".join(lines), {"rid": rid, "oid": oid, "hidden": None}
    truth = by[hidden][0]
    return "\n".join(lines), {"rid": rid, "oid": oid, "hidden": hidden, "hidden_rid": rid[hidden], "truth_pred": truth,
                              "truth_symbol": voc[truth]}


def complete_text(set_seed, world, i, research, voc):
    """学習の系列の場面 i を、伏せた関係に正解を戻した完全な場面として、同じ書式・同じ番号で書く（make_set と同じ乱数 num|<組>|<i>）。"""
    text, _rec = render_v2(relations(research["type"], research["cue"], world), None, random.Random(f"num|{set_seed}|{i}"), voc)
    return text


def parse_v2(text):
    return parse("\n".join(ln.strip() for ln in text.split("\n")))
