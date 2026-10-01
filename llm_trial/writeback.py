"""段 3：書き戻しと対照の例（仕様 v2 の 5 節、委任書「LLM の小さな試し・第一段」）。
書き戻す店：結果を見る前に、組ごとに決める（組の種から引く。仮の決定）。
実施できる時点：試験の時点（10・20・30・40 場面のあと）のうち、その店の通常と例外を両方経験した後だけ。まだ無ければ「実施できなかった」。
書き戻し：その店の、通常と例外の各状況で、その時点までに最後に観察した場面を一つずつ、決まった書式（場面と正解）でメモの末尾に足す。
  研究者の解説は付けない。世界 1 でも同じ選び方。
対照：同じ店の、通常の場面で、その時点までに最後と、その一つ前に観察したもの二つを、同じ書式で足す（仮の決定）。
書式（仮の決定）：場面ごとに「Scene:」の行、場面の文字列、「Answer: <記号>」の行。二つを空行で区切る。
確かめ：書き戻しと対照で、書式（行の種類と数）がそろい、長さ（文字数・Haiku のトークン数）が近いこと。"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import world as w  # noqa: E402

TEST_AT = (10, 20, 30, 40)


def block(s):
    return f"Scene:\n{s['text']}\nAnswer: {s['answer']}"


def shop_for(set_seed):
    return random.Random(f"writeback-shop|{set_seed}").choice(["甲", "乙"])


def examples(st, t):
    """時点 t（t 場面のあと）の書き戻しと対照。返り値 dict（実施できなければ理由）。"""
    shop = shop_for(st["set_seed"])
    past = st["series"][:t]
    norm = [s for s in past if s["research"]["type"] == shop and s["research"]["cue"] == "n"]
    exc = [s for s in past if s["research"]["type"] == shop and s["research"]["cue"] == "e"]
    if not norm or not exc:
        return {"時点": t, "店": shop, "実施": False, "理由": "その店の通常と例外を両方は経験していない"}
    if len(norm) < 2:
        return {"時点": t, "店": shop, "実施": False, "理由": "対照に要る通常の場面が二つない"}
    wb = [norm[-1], exc[-1]]
    ctl = [norm[-2], norm[-1]]
    return {"時点": t, "店": shop, "実施": True, "書き戻し": "\n\n".join(block(s) for s in wb), "対照": "\n\n".join(block(s) for s in ctl),
            "書き戻しの場面": [s["i"] for s in wb], "対照の場面": [s["i"] for s in ctl]}


def shape(text):
    return [("Scene" if ln == "Scene:" else "Answer" if ln.startswith("Answer: ") else "" if ln == "" else "関係")
            for ln in text.split("\n")]


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    count = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        import api
        count = api.haiku_count
    res = {}
    for world in (1, 2):
        st = w.make_set(1, world)
        rows = []
        for t in TEST_AT:
            ex = examples(st, t)
            if ex["実施"]:
                ex["書式がそろう"] = shape(ex["書き戻し"]) == shape(ex["対照"])
                ex["文字数"] = [len(ex["書き戻し"]), len(ex["対照"])]
                if count:
                    ex["Haiku のトークン数"] = [count(ex["書き戻し"]), count(ex["対照"])]
            rows.append(ex)
        res[f"組 1・世界 {world}"] = rows
    json.dump(res, open(os.path.join(out, "段3の書き戻しと対照.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k, rows in res.items():
        for r in rows:
            print(k, r["時点"], r["店"], r["実施"], r.get("理由", ""), r.get("書式がそろう"), r.get("文字数"), r.get("Haiku のトークン数"),
                  r.get("書き戻しの場面"), r.get("対照の場面"))


if __name__ == "__main__":
    main()
