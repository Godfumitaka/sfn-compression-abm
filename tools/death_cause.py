"""死因の数え（v3.7、2026-09-28、委任書「v3.7（② の罰をやめる）」の 3）。台帳一本ごと。★ 判断しない。模型は動かさない（台帳と side を読むだけ）。
deletion_event の kind＝deletion の各行（R・slot_index・registered_at・削除の試行）について、その行が生きていたあいだ
（registered_at から削除の試行まで。両端を含む）に受けた罰を、charge_source の (R, slot_index) で突き合わせ、死因を一つに分ける：
  ②（0 のはず）＞ ①（その行が ① の罰を受けていた）＞ 棄権（棄権課金を受けていた）＞ 参加率だけ（罰を一度も受けていない）
  別に数える：寿命 0（生まれた試行のうちに死んだ行）。
  （参考）①_穴埋め は席の履歴を減らす罰で、行の V には入らないので死因に数えない。その席に ①_穴埋め があった行の数だけ出す。
死んだときの V と、その項（参加率 P・a・参加率の項 P·a・埋込の項）は、side の "death_terms"（tools/deathterms.py、旗 --death-terms）から取る。
side に無ければ（旗なしの走行）、V（deletion_event の V）だけを出す。
★ v3.8（2026-09-28 夕）：side に v3.8 の記録（kind＝"v38"、tools/v38.py）があれば、次を足す。
  死因「反証（D-11）」：その行が生きていたあいだに、開示のあとの反証（評価 +1・確認 +0）を受けていた（② ＞ ① ＞ 棄権 ＞ 反証 の順で一つに分ける）。
  罰も反証も無い死を「時間による減衰だけ」と呼ぶ（v3.8 の確認率は未確認を分母に足さないので、残るのは時間による重みの変化だけ）。
  v3.8 の記録が無い台帳では、今までどおり「参加率だけ」と呼ぶ（v3.7 までの参加率は、未確認でも分母が増える）。
  「死んだ試行に自分が伏せ辺だった行」：死んだ試行に使われた定義の行で、選ばれた写しで具体化した関係（述語と引数の組）が、その試行の伏せ辺
  （台帳の held_out_content。研究者用）と同じだった行。使われなかった定義の行は写しが無いので数えない（v3.8 の記録が無ければ出さない）。
使い方  python3.12 tools/death_cause.py <台帳 .jsonl.gz> <side .jsonl> <出力 json>"""
import collections, gzip, json, statistics, sys

led, side, out = sys.argv[1:4]
pen = {k: collections.defaultdict(list) for k in ("①", "②", "棄権", "①_穴埋め")}   # (R, slot) -> 罰を受けた試行
dels = []
held = {}
with gzip.open(led, "rt", encoding="utf-8") as f:
    next(f)
    for line in f:
        r = json.loads(line)
        t = r["prediction_order"]
        ho = r.get("held_out_content") or {}
        held[t] = (ho.get("predicate"), tuple(ho.get("arguments") or ()))
        cs = r.get("charge_source") or {}
        for R, s in cs.get("①") or []:
            pen["①"][(R, s)].append(t)
        for R, s in cs.get("②") or []:
            pen["②"][(R, s)].append(t)
        for e in cs.get("棄権") or []:
            pen["棄権"][(e["R"], e["slot_index"])].append(t)
        for e in cs.get("①_穴埋め") or []:
            pen["①_穴埋め"][(e["R"], e["slot_index"])].append(t)
        for e in r.get("deletion_event") or []:
            if e.get("kind") == "deletion":
                dels.append(e)
terms = {}
refuted = collections.defaultdict(list)   # (R, slot, reg) -> 反証を受けた試行
own_held = set()                          # (R, slot, reg, t)：その試行に使われた定義の行で、具体化した関係が伏せ辺と同じ
has_v38 = False
try:
    for line in open(side, encoding="utf-8"):
        if '"death_terms"' in line:
            d = json.loads(line)
            if d.get("kind") == "death_terms":
                for x in d["rows"]:
                    terms[(x["R"], x["slot_index"], x["registered_at"], d["trial"])] = x
        elif '"v38"' in line:
            d = json.loads(line)
            if d.get("kind") != "v38":
                continue
            has_v38 = True
            R, t = d.get("R_used"), d["trial"]
            for x in d.get("行") or []:
                if x.get("新") == "反証":
                    refuted[(R, x["slot"], x["reg"])].append(t)
                if x.get("pos") is not None and (x["pred"], tuple(x["pos"])) == held.get(t):
                    own_held.add((R, x["slot"], x["reg"], t))
except FileNotFoundError:
    pass
LAST = "時間による減衰だけ" if has_v38 else "参加率だけ"
CAUSES = ("②", "①", "棄権") + (("反証（D-11）",) if has_v38 else ()) + (LAST,)


def during(kind, e):
    return [t for t in pen[kind].get((e["R"], e["slot_index"]), []) if e["registered_at"] <= t <= e["trial"]]


rows = []
for e in dels:
    got = {k: during(k, e) for k in pen}
    got["反証（D-11）"] = [t for t in refuted.get((e["R"], e["slot_index"], e["registered_at"]), [])
                          if e["registered_at"] <= t <= e["trial"]]
    cause = next((k for k in ("②", "①", "棄権", "反証（D-11）") if got[k]), LAST)
    tm = terms.get((e["R"], e["slot_index"], e["registered_at"], e["trial"]))
    rows.append({"R": e["R"], "slot_index": e["slot_index"], "registered_at": e["registered_at"], "trial": e["trial"],
                 "lifetime": e["trial"] - e["registered_at"], "cause": cause, "V": e["V"],
                 "n①": len(got["①"]), "n②": len(got["②"]), "n棄権": len(got["棄権"]), "n①_穴埋め": len(got["①_穴埋め"]),
                 "n反証": len(got["反証（D-11）"]),
                 "own_held_out_at_death": ((e["R"], e["slot_index"], e["registered_at"], e["trial"]) in own_held) if has_v38 else None,
                 "P": tm["P"] if tm else None, "a": tm["a"] if tm else None,
                 "participation_term": tm["participation_term"] if tm else None,
                 "embed_term": tm["embed_term"] if tm else None, "exc_per_apply": tm["exc_per_apply"] if tm else None})


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


summ = {"削除": len(rows), "死因": {c: sum(1 for x in rows if x["cause"] == c) for c in CAUSES},
        "寿命0": sum(1 for x in rows if x["lifetime"] == 0),
        "寿命0の死因": {c: sum(1 for x in rows if x["lifetime"] == 0 and x["cause"] == c) for c in CAUSES},
        "席に①_穴埋めがあった行": sum(1 for x in rows if x["n①_穴埋め"]),
        "v38の記録": has_v38,
        "死んだ試行に自分が伏せ辺だった行": sum(1 for x in rows if x["own_held_out_at_death"]) if has_v38 else None,
        "項がある行": sum(1 for x in rows if x["P"] is not None),
        "中央値": {c: {"V": med(x["V"] for x in rows if x["cause"] == c), "P": med(x["P"] for x in rows if x["cause"] == c),
                     "a": med(x["a"] for x in rows if x["cause"] == c),
                     "参加率の項": med(x["participation_term"] for x in rows if x["cause"] == c)} for c in CAUSES}}
json.dump({"台帳": led, "要約": summ, "行": rows}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
print(json.dumps(summ, ensure_ascii=False))
