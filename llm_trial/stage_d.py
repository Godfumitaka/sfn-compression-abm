"""理解検査（委任書「LLM の小さな試し・理解検査」の段 C・D）。全履歴の条件。★ 研究者用の説明語は渡さない。
見せ方（段 C、llm_trial/world.py render_v2）：親の行の下に子の行を字下げして置く決まった順。番号は場面ごとにでたらめ。r／o で区別。
  指示（INTRO）：記号の読み方を、本番に出ない記号の小さな例で説明し、「?」は一つだけと明示し、
  「同じに見える場面には一貫した答えがある。過去の場面と答えから予測する課題」と明示する。
段 D：四つの場合を二例ずつ、計 8 例を、正解つきの過去の場面として与えて固定する（例はどれもドアを伏せた場面。順はでたらめ。仮の決定）。
  四つの場合それぞれ 4 問、計 16 問を、新しい番号で、一問ずつ別々の問い合わせで出す（ドアを伏せた場面）。試験の間に正解は足さない。
  通過の目安（事前の基準）：最もありそうな答えが 16 問中 15 問以上正しく、どの場合も 4 問中 3 問以上正しい。黙ったかは別に記録。
答えの形：提供元の形の指定（Haiku：output_config.format の json_schema、Together：response_format の json_schema）。言葉での指示は補助。
推論：既定は切る（Qwen は reasoning: {enabled: false}）。推論ありの条件では、Haiku は拡張思考、Qwen は reasoning: {enabled: true}
  （出力の上限は 推論の予算＋100 にそろえる）。Llama 3.3 70B には推論の機能が無いので、推論なしだけ。推論に使った量と、上限で切れたかを記録する。
形が崩れたとき：今まで（stage4.py）と同じく 2 回まで問い直し、それでも読めなければ「形の崩れ」。上限で切れたもの（finish_reason／stop_reason が長さ）は別に数える。
使い方（鍵のある環境で）  zsh -ic 'python3.12 llm_trial/stage_d.py <出力の場所> <模型> <世界> <組の種> [各場合の例の数（既定 2）] [推論の予算（Haiku の拡張思考、既定なし）]'
追記（2026-10-01 夕方の返事の 3）：例の数（各場合 2 又は 4）と推論の有無を変えられる。例は各場合の 1・2 番目が 2 例のときと同じ場面（4 例は
  その 2 つに 3・4 番目を足したもの）、順は組の種と例の数からでたらめ。推論ありのとき出力の上限は 推論の予算 ＋ 100。
  推論の中身は記録に残すだけで、ほかの問い合わせには渡さない。推論に使った量（推論の文字数と、出力のトークン数 − 答えの部分のトークン数の見積もり）と、
  上限で切れたか（stop_reason が max_tokens）を記録する。"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api  # noqa: E402
import stage4 as s4  # noqa: E402
import world as w  # noqa: E402

INTRO = """How to read a scene. A scene is a list of lines. Each line has the form `rN: word(arg, arg)` or `rN: word(arg)`.
`rN` is a relation and `word` is its predicate. Each argument is either an object (`oN`, starting with the letter o) or another relation (`rN`, starting with the letter r).
Indentation shows structure: the lines indented below a line are the relations that appear as its arguments.
Relation numbers and object numbers are arbitrary labels; they change from scene to scene and carry no meaning.

Example (the words in this example are not used in the task):
r12: wug(r7, r3)
  r7: dax(o1, o2)
  r3: fep(o1, o2)
r30: zib(o2)
Here r12 has two arguments, the relations r7 and r3; r7 and r3 each relate the objects o1 and o2; r30 has one argument, the object o2.

In every scene exactly one relation has been removed. Its line is missing, and where it appeared as an argument it is written as `?`. There is exactly one `?` in each scene.
Your task: predict the predicate (the word) of the removed relation.
Scenes that look the same have a consistent answer. This is a prediction task: use the past scenes and their answers to predict the answer for the current scene."""
ASK = ('Respond with only a JSON object of the form {"answer": "<word>", "confidence": <probability from 0 to 1 that your answer is correct>, '
       '"respond": <true to give this answer, false to abstain>}. Even if you abstain, give your best answer and its confidence. '
       'Do not explain your reasoning. Output nothing except the JSON object.')
SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}, "confidence": {"type": "number"}, "respond": {"type": "boolean"}},
          "required": ["answer", "confidence", "respond"], "additionalProperties": False}
MAXTOK = 100


def prompt(history, scene):
    parts = [INTRO, "", "Past scenes, each followed by the correct predicate of its removed relation:"]
    for k, s in enumerate(history, 1):
        parts += ["", f"Scene {k}:", s["text"], f"Answer: {s['answer']}"]
    parts += ["", "Current scene:", scene["text"], "", ASK]
    return "\n".join(parts)


THINK = [None]


EFFORT = [None]
SONNET_MAXTOK = 32000   # 仮の決定：adaptive の推論が切れないよう大きめ（切れたら「上限で切れた」として数える）
_BASE = {}


def _net_tokens(model, text):
    if model not in _BASE:
        _BASE[model] = api.count_tokens(model, "a")
    return api.count_tokens(model, text) - _BASE[model] + 1 if text else 0


def call(model, content, what):
    t0 = time.time()
    if model in api.CLAUDE_PRICE:
        # Sonnet 5.5・Opus 5.5：adaptive の推論 ＋ effort。推論に使った量＝出力のトークン数 − 本文のトークン数（同じ模型の数え方、正味）
        r, u, cost = api.claude_chat(model, [{"role": "user", "content": content}], max_tokens=SONNET_MAXTOK, what=what,
                                     output_format={"type": "json_schema", "schema": SCHEMA}, effort=EFFORT[0])
        text = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
        cut = r.get("stop_reason") == "max_tokens"
        th = "".join(b.get("thinking", "") for b in r.get("content", []) if b.get("type") == "thinking")
        reasoning = th or None
        u = dict(u, stop_reason=r.get("stop_reason"), 本文のトークン数=_net_tokens(model, text), 応答の控え=api.response_meta(r, u))
        rt = u.get("output_tokens", 0) - u["本文のトークン数"]
        return text, u, cost, time.time() - t0, cut, reasoning, rt
    if model == api.HAIKU:
        r, u, cost = api.haiku_chat([{"role": "user", "content": content}], max_tokens=MAXTOK + (THINK[0] or 0), what=what,
                                    output_format={"type": "json_schema", "schema": SCHEMA}, thinking_budget=THINK[0])
        u = dict(u, 応答の控え=api.response_meta(r, u))
        text = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
        cut = r.get("stop_reason") == "max_tokens"
        th = "".join(b.get("thinking", "") for b in r.get("content", []) if b.get("type") == "thinking")
        reasoning = th if THINK[0] else None
    else:
        rf = {"type": "json_schema", "json_schema": {"name": "answer", "schema": SCHEMA}}
        # 推論あり（Qwen だけ）：出力の上限は Haiku と同じ 推論の予算＋100。Together の推論には予算の指定が無いので、上限だけをそろえる
        r, u, cost = api.together_chat(model, [{"role": "user", "content": content}], max_tokens=MAXTOK + (THINK[0] or 0), what=what,
                                       response_format=rf, reasoning=bool(THINK[0]))
        ch = r["choices"][0]
        text = ch["message"].get("content")
        cut = ch.get("finish_reason") == "length"
        reasoning = ch["message"].get("reasoning") or None
    rt = (u.get("completion_tokens_details") or {}).get("reasoning_tokens", u.get("reasoning_tokens"))
    return text, u, cost, time.time() - t0, cut, reasoning, rt


def build(set_seed, world, per_case=2):
    voc = w.vocab(set_seed)
    hist = []
    for k, (typ, cue) in enumerate(w.CASES):
        for j in range(per_case):
            text, rec = w.render_v2(w.relations(typ, cue, world), w.DOOR_PATH, random.Random(f"D-hist|{set_seed}|{world}|{k}|{j}"), voc)
            hist.append({"text": text, "answer": rec["truth_symbol"], "case": f"{typ}・{cue}"})
    random.Random(f"D-order|{set_seed}" if per_case == 2 else f"D-order|{set_seed}|{per_case}").shuffle(hist)
    tests = []
    for k, (typ, cue) in enumerate(w.CASES):
        for j in range(4):
            text, rec = w.render_v2(w.relations(typ, cue, world), w.DOOR_PATH, random.Random(f"D-test|{set_seed}|{world}|{k}|{j}"), voc)
            tests.append({"text": text, "answer": rec["truth_symbol"], "case": f"{typ}・{cue}"})
    return hist, tests


def main():
    out, model, world, set_seed = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    per_case = int(sys.argv[5]) if len(sys.argv) > 5 else 2
    if model in api.CLAUDE_PRICE:
        # Sonnet 5.5・Opus 5.5：6 番目の引数は effort（low・medium・high・xhigh・max）
        EFFORT[0] = sys.argv[6] if len(sys.argv) > 6 else None
    else:
        THINK[0] = int(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] not in ("0", "none") else None
    os.makedirs(out, exist_ok=True)
    api.set_ledger(os.path.join(os.path.dirname(out.rstrip("/")), "費用.jsonl"))
    hist, tests = build(set_seed, world, per_case)
    tag = f"{model.split('/')[-1]}_w{world}_set{set_seed}" + ("" if per_case == 2 and not THINK[0] else f"_例{per_case * 4}_推論{THINK[0] or 'なし'}")
    if model in api.CLAUDE_PRICE:
        tag = f"{model}_w{world}_set{set_seed}_例{per_case * 4}_effort{EFFORT[0] or '既定'}"
    log = os.path.join(out, f"{tag}.jsonl")
    done = {}
    if os.path.exists(log):
        for l in open(log, encoding="utf-8"):
            d = json.loads(l)
            done[d["問"]] = d
    for q, t in enumerate(tests):
        if q in done:
            continue
        content = prompt(hist, t)
        tries, got = [], None
        for k in range(3):
            text, u, cost, sec, cut, reasoning, rt = call(model, content if k == 0 else content + "\n" + s4.STRICT, f"段D {tag} 問 {q} 試み {k + 1}")
            got = s4.parse(text)
            tries.append({"出力": text, "使用量": u, "費用": cost, "秒": round(sec, 2), "上限で切れた": cut, "推論の量": rt,
                          "推論の欄あり": reasoning is not None, "推論の文字数": len(reasoning) if reasoning else 0,
                          "推論の中身": reasoning if reasoning else None})
            if got or cut:
                break
        row = {"問": q, "場合": t["case"], "正解": t["answer"], "試み": tries}
        if got:
            row.update(got)
            row["判定"] = "黙り" if not got["respond"] else ("正解" if got["answer"] == t["answer"] else "誤答")
            row["最もありそうな答えが正しい"] = got["answer"] == t["answer"]
        else:
            row["判定"] = "上限で切れた" if tries[-1]["上限で切れた"] else "形の崩れ"
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        done[q] = row
    rows = [done[q] for q in range(len(tests))]
    by = {}
    for c in [f"{a}・{b}" for a, b in w.CASES]:
        rs = [r for r in rows if r["場合"] == c]
        by[c] = {"最もありそうな答えが正しい": sum(1 for r in rs if r.get("最もありそうな答えが正しい")), "黙り": sum(1 for r in rs if r["判定"] == "黙り"),
                 "形の崩れ・上限": sum(1 for r in rs if r["判定"] in ("形の崩れ", "上限で切れた"))}
    best = sum(v["最もありそうな答えが正しい"] for v in by.values())
    passed = best >= 15 and all(v["最もありそうな答えが正しい"] >= 3 for v in by.values())
    summ = {"模型": model, "世界": world, "組の種": set_seed, "各場合の例の数": per_case, "推論の予算": THINK[0],
            "上限で切れた問い": sum(1 for r in rows if any(t["上限で切れた"] for t in r["試み"])),
            "出力のトークン（中央値・最大）": (sorted(t["使用量"].get("output_tokens", t["使用量"].get("completion_tokens", 0)) for r in rows for t in r["試み"])[len(rows) // 2],
                                    max(t["使用量"].get("output_tokens", t["使用量"].get("completion_tokens", 0)) for r in rows for t in r["試み"])), "最もありそうな答えが正しい（16 問）": best, "場合ごと": by, "通過": passed,
            "黙り": sum(1 for r in rows if r["判定"] == "黙り"), "費用（これまでの合計）": round(api.spent(), 4), "effort": EFFORT[0],
            "推論のトークン（見積もり）の平均": round(sum(t["推論の量"] or 0 for r in rows for t in r["試み"]) / max(1, sum(len(r["試み"]) for r in rows)), 1),
            "断られた（refusal）": sum(1 for r in rows for t in r["試み"] if (t["使用量"] or {}).get("stop_reason") == "refusal"),
            "履歴の場合の並び": [h["case"] for h in hist]}
    json.dump(summ, open(os.path.join(out, f"{tag}_要約.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
