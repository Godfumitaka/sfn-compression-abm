"""死因の数え（v3.7、2026-09-28、委任書「v3.7（② の罰をやめる）」の 3）。台帳一本ごと。★ 判断しない。模型は動かさない（台帳と side を読むだけ）。
deletion_event の kind＝deletion の各行（R・slot_index・registered_at・削除の試行）について、その行が生きていたあいだ
（registered_at から削除の試行まで。両端を含む）に受けた罰を、charge_source の (R, slot_index) で突き合わせ、死因を一つに分ける：
  ②（0 のはず）＞ ①（その行が ① の罰を受けていた）＞ 棄権（棄権課金を受けていた）＞ 参加率だけ（罰を一度も受けていない）
  別に数える：寿命 0（生まれた試行のうちに死んだ行）。
  （参考）①_穴埋め は席の履歴を減らす罰で、行の V には入らないので死因に数えない。その席に ①_穴埋め があった行の数だけ出す。
死んだときの V と、その項（参加率 P・a・参加率の項 P·a・埋込の項）は、side の "death_terms"（tools/deathterms.py、旗 --death-terms）から取る。
side に無ければ（旗なしの走行）、V（deletion_event の V）だけを出す。
使い方  python3.12 tools/death_cause.py <台帳 .jsonl.gz> <side .jsonl> <出力 json>"""
import collections, gzip, json, statistics, sys

led, side, out = sys.argv[1:4]
CAUSES = ("②", "①", "棄権", "参加率だけ")
pen = {k: collections.defaultdict(list) for k in ("①", "②", "棄権", "①_穴埋め")}   # (R, slot) -> 罰を受けた試行
dels = []
with gzip.open(led, "rt", encoding="utf-8") as f:
    next(f)
    for line in f:
        r = json.loads(line)
        t = r["prediction_order"]
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
try:
    for line in open(side, encoding="utf-8"):
        if '"death_terms"' not in line:
            continue
        d = json.loads(line)
        if d.get("kind") != "death_terms":
            continue
        for x in d["rows"]:
            terms[(x["R"], x["slot_index"], x["registered_at"], d["trial"])] = x
except FileNotFoundError:
    pass


def during(kind, e):
    return [t for t in pen[kind].get((e["R"], e["slot_index"]), []) if e["registered_at"] <= t <= e["trial"]]


rows = []
for e in dels:
    got = {k: during(k, e) for k in pen}
    cause = next((k for k in ("②", "①", "棄権") if got[k]), "参加率だけ")
    tm = terms.get((e["R"], e["slot_index"], e["registered_at"], e["trial"]))
    rows.append({"R": e["R"], "slot_index": e["slot_index"], "registered_at": e["registered_at"], "trial": e["trial"],
                 "lifetime": e["trial"] - e["registered_at"], "cause": cause, "V": e["V"],
                 "n①": len(got["①"]), "n②": len(got["②"]), "n棄権": len(got["棄権"]), "n①_穴埋め": len(got["①_穴埋め"]),
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
        "項がある行": sum(1 for x in rows if x["P"] is not None),
        "中央値": {c: {"V": med(x["V"] for x in rows if x["cause"] == c), "P": med(x["P"] for x in rows if x["cause"] == c),
                     "a": med(x["a"] for x in rows if x["cause"] == c),
                     "参加率の項": med(x["participation_term"] for x in rows if x["cause"] == c)} for c in CAUSES}}
json.dump({"台帳": led, "要約": summ, "行": rows}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
print(json.dumps(summ, ensure_ascii=False))
