"""全履歴の条件で、世界 2 を解けるようになるまでの段階（委任書 2026-10-02 朝）。Haiku 4.5・推論あり。メモは使わない。
段階（世界 2、上から順に。通った段階で止まる）：
  1：40 場面（ドアは半分の場面）、推論の予算 8,000
  2：40 場面（全部の場面でドア）、推論の予算 2,048
  3：80 場面（各場合の数を 2 倍。ドアは半分の場面）、推論の予算 2,048
  4：80 場面（全部の場面でドア）、推論の予算 8,000
系列：world.make_set(1, 世界, "v2", mult, door_all)（組 1 と同じ規則・乱数の流れ。段階 1 は上限の格子と同じ系列）。
学習：上限の格子の全履歴と同じく、各場面を、それより前の場面と正解の全部を渡して予測させる（stage_d.prompt）。学習の予測は最後の試験に影響しない
  （全履歴の条件では、持ち越すのは過去の場面と正解だけ）。系列の中の試験（10 場面ごと）は行わない。
最後の試験：系列の全部の場面と正解を渡し、理解検査と同じ 16 問（stage_d.build(1, 世界, 4) の試験）を一問ずつ別々に。
通過の目安：理解検査と同じ（最もありそうな答えが 16 問中 15 問以上、どの場合も 4 問中 3 問以上）。
予測の一回：memo.predict（形の崩れは 2 回まで問い直す、上限で切れたものは問い直さない）。出力の上限は 推論の予算＋100。
推論に使った量：出力のトークン数から、本文（答えの JSON）のトークン数（数える API、正味）を引いた見積もり。推論の文字数も残す。
使い方（鍵のある環境で）  zsh -ic 'python3.12 llm_trial/fullhist_stages.py <出力の場所> <世界> <段階 1〜4>'   （一行目に PASS／FAIL）"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api  # noqa: E402
import memo as mm  # noqa: E402
import stage_d as sd  # noqa: E402
import world as w  # noqa: E402

STAGES = {1: dict(mult=1, door_all=False, think=8000), 2: dict(mult=1, door_all=True, think=2048),
          3: dict(mult=2, door_all=False, think=2048), 4: dict(mult=2, door_all=True, think=8000)}


def text_tokens(t):
    return max(api.haiku_count(t) - BASE[0] + 1, 0) if t else 0


BASE = [None]


def main():
    out, world, stage = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    os.makedirs(out, exist_ok=True)
    api.set_ledger(os.path.join(os.path.dirname(out.rstrip("/")), "費用.jsonl"))
    BASE[0] = api.haiku_count("a")
    cfg = STAGES[stage]
    mm.THINK = cfg["think"]
    st = w.make_set(1, world, "v2", cfg["mult"], cfg["door_all"])
    _h, tests = sd.build(1, world, 4)
    tag = f"段階{stage}_w{world}"
    log = os.path.join(out, f"{tag}.jsonl")
    rows = [json.loads(l) for l in open(log, encoding="utf-8")] if os.path.exists(log) else []
    done = {(r["段"], r["i"]) for r in rows}

    def put(row):
        for t in row["試み"]:
            t["本文のトークン数"] = text_tokens(t["出力"])
            t["推論のトークン数（見積もり）"] = t["使用量"].get("output_tokens", 0) - t["本文のトークン数"]
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        rows.append(row)

    for s in st["series"]:
        i = s["i"]
        if ("学習", i) in done:
            continue
        res = s["research"]
        row = mm.predict(sd.prompt(st["series"][:i], s), s["answer"], f"全履歴 {tag} 学習 {i}")
        row.update({"段": "学習", "i": i, "場合": f"{res['type']}・{res['cue']}", "ドアを伏せた": res["door_hidden"]})
        put(row)
        print(tag, "学習", i, row["判定"], round(api.spent(), 4), flush=True)
    for q, t in enumerate(tests):
        if ("最後の試験", q) in done:
            continue
        row = mm.predict(sd.prompt(st["series"], t), t["answer"], f"全履歴 {tag} 試験 {q}")
        row.update({"段": "最後の試験", "i": q, "場合": t["case"]})
        put(row)
        print(tag, "試験", q, t["case"], row["判定"], row.get("answer"), round(api.spent(), 4), flush=True)
    fin = [r for r in rows if r["段"] == "最後の試験"]
    by = {c: sum(1 for r in fin if r["場合"] == c and r.get("最もありそうな答えが正しい")) for c in ("甲・n", "甲・e", "乙・n", "乙・e")}
    best = sum(by.values())
    passed = best >= 15 and all(v >= 3 for v in by.values())
    summ = {"段階": stage, "世界": world, **cfg, "学習の場面の数": len(st["series"]), "最もありそうな答えが正しい（16 問）": best, "場合ごと": by, "通過": passed,
            "判定": {k: sum(1 for r in fin if r["判定"] == k) for k in ("正解", "誤答", "黙り", "形の崩れ", "上限で切れた")}}
    json.dump(summ, open(os.path.join(out, f"{tag}_要約.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("PASS" if passed else "FAIL")
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
