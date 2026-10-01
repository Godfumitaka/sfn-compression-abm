"""段 2：長さの測定（委任書「LLM の小さな試し・第一段」）。
測るもの：場面一つ（世界 1・2 × 四つの場合 × 5 個＝40 個。伏せ方は学習と同じく半分ドア）、甲と乙の骨組みの中身全体（研究者が書いた参考の記述）、
  四つの場合の表、短い規則。述語の記号は組 1 の無意味語。
数え方：
  Anthropic（Claude Haiku 4.5）：トークン数を数える API（count_tokens）。
  Together（Llama 3.3 70B、Qwen 二つ）：max_tokens＝1 の短い問い合わせの使用量（usage.prompt_tokens）。
  どちらも、利用者の一つの発言として渡す。会話の書式の分を除くため、一文字 "a" の値（基準）を測り、「正味＝値 − 基準 ＋ 1」も並べる。
使い方（鍵のある環境で）  zsh -ic 'python3.12 llm_trial/stage2.py <出力の場所>'"""
import json
import os
import random
import sys
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api  # noqa: E402
import world as w  # noqa: E402

MODELS_T = ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "Qwen/Qwen3.5-9B", "Qwen/Qwen3.8-2.4T-A95B"]   # Qwen は従量課金で使える二つ（仮の決定）


def texts():
    voc = w.vocab(1)
    out = []
    rng = random.Random("stage2")
    for world in (1, 2):
        for typ, cue in w.CASES:
            for k in range(5):
                rels = w.relations(typ, cue, world)
                hidden = w.DOOR_PATH if k % 2 == 0 else rng.choice(sorted(n for n in w.hideable(rels) if n != w.DOOR_PATH))
                text, _rec = w.render(rels, hidden, random.Random(f"s2|{world}|{typ}|{cue}|{k}"), voc)
                out.append({"種類": "場面", "世界": world, "場合": f"{typ}・{cue}", "text": text})
    # 研究者が書いた参考の記述（LLM には渡さない。長さを測るだけ）
    def full(typ):
        rels = w.relations(typ, "n", 2)
        rid = {n: f"r{k + 1}" for k, (n, _p, _a) in enumerate(rels)}
        oid = {"a": "o1", "b": "o2"}
        return "\n".join(f"{rid[n]}: {voc[p]}({', '.join(rid.get(a, oid.get(a, a)) for a in args)})" for n, p, args in rels)
    out.append({"種類": "甲と乙の骨組みの中身全体", "text": "A:\n" + full("甲") + "\nB:\n" + full("乙")})
    ra, rb = voc["supported"], voc["carried"]
    sn, se, xx, yy = voc["sig_n"], voc["sig_e"], voc[w.X], voc[w.Y]
    door_parent = voc["cause"]
    out.append({"種類": "四つの場合の表", "text": f"{door_parent} first argument:\n{ra} + {sn} -> {xx}\n{ra} + {se} -> {yy}\n{rb} + {sn} -> {yy}\n{rb} + {se} -> {xx}"})
    out.append({"種類": "短い規則", "text": f"{door_parent}.1: {ra}->{xx}, {rb}->{yy}; {se} swaps"})
    return out


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    api.set_ledger(os.path.join(os.path.dirname(out.rstrip("/")), "費用.jsonl"))
    ts = texts()
    base = {"haiku": api.haiku_count("a")}
    for m in MODELS_T:
        _r, u, _c = api.together_chat(m, [{"role": "user", "content": "a"}], max_tokens=1, what="段2 基準")
        base[m] = u["prompt_tokens"]
    rows = []
    for t in ts:
        row = {k: v for k, v in t.items() if k != "text"}
        row["文字数"] = len(t["text"])
        row["行数"] = t["text"].count("\n") + 1
        row["haiku"] = api.haiku_count(t["text"])
        for m in MODELS_T:
            _r, u, _c = api.together_chat(m, [{"role": "user", "content": t["text"]}], max_tokens=1, what="段2 長さ")
            row[m] = u["prompt_tokens"]
        rows.append(row)
    keys = ["haiku"] + MODELS_T
    summ = {}
    for kind in ("場面", "甲と乙の骨組みの中身全体", "四つの場合の表", "短い規則"):
        rs = [r for r in rows if r["種類"] == kind]
        summ[kind] = {k: {"正味の平均": round(mean(r[k] - base[k] + 1 for r in rs), 1), "正味の最小": min(r[k] - base[k] + 1 for r in rs),
                          "正味の最大": max(r[k] - base[k] + 1 for r in rs)} for k in keys}
    for world in (1, 2):
        for typ, cue in w.CASES:
            rs = [r for r in rows if r["種類"] == "場面" and r["世界"] == world and r["場合"] == f"{typ}・{cue}"]
            summ[f"場面（世界 {world}・{typ}・{cue}）"] = {k: round(mean(r[k] - base[k] + 1 for r in rs), 1) for k in keys}
    res = {"基準（一文字 a の値）": base, "要約（正味）": summ, "一つずつ": rows, "費用（これまでの合計）": round(api.spent(), 4),
           "参考の記述": {t["種類"]: t["text"] for t in ts if t["種類"] != "場面"}}
    json.dump(res, open(os.path.join(out, "段2の長さ.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"基準": base, "要約": summ, "費用": res["費用（これまでの合計）"]}, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
