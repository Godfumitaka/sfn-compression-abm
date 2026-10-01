"""段 4：課題の理解の小さな確かめ（全履歴の条件、8 場面だけ。委任書「LLM の小さな試し・第一段」）。
場面：組 1・世界 2 の学習の系列のうち、ドアを伏せた場面から、四つの場合ごとに系列の中の最後の 2 つ（計 8。仮の決定）。
  履歴：その場面より前の系列の場面すべてと、その正解（全履歴の条件）。
模型：Llama 3.3 70B（Together）、Qwen 二つ（Together、従量課金で使える Qwen3.5-9B と Qwen3.8-2.4T-A95B。推論の過程を出さない指定）、
  Claude Haiku 4.5（Anthropic）。温度 0。出力の上限 80 トークン。Together では logprobs＝1 を頼む（返れば控える）。
指示（英語。仮の決定）：記号の読み方（行の形、r と o、「?」の意味）と、答え方（JSON）だけ。研究者用の説明語は入れない。
返させる形：{"answer": "<述語の記号>", "confidence": <0〜1>, "respond": <true＝答える／false＝黙る>}。黙る場合も答えと確率を返させる。
形が崩れたとき（仮の決定。報告に案として書く）：同じ問いに「Return only the JSON object, nothing else.」を足して 2 回まで問い直す。
  3 回とも崩れたら「形の崩れ」として数え、正解・誤答・黙りのどれにも入れない（別に数える）。
使い方（鍵のある環境で）  zsh -ic 'python3.12 llm_trial/stage4.py <出力の場所>'"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api  # noqa: E402
import world as w  # noqa: E402

MODELS = ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "Qwen/Qwen3.5-9B", "Qwen/Qwen3.8-2.4T-A95B", api.HAIKU]

INTRO = ("Each scene is a list of lines. Each line has the form `rN: word(arg, arg)` or `rN: word(arg)`. "
         "`rN` names a relation, `word` is its predicate, and each argument is either an object (`oN`) or another relation (`rN`). "
         "In each scene exactly one relation has been removed; where it appeared as an argument, it is written as `?`. "
         "Your task is to predict the predicate (the word) of the removed relation.")
ASK = ('Respond with only a JSON object of the form {"answer": "<word>", "confidence": <probability from 0 to 1 that your answer is correct>, '
       '"respond": <true to give this answer, false to abstain>}. Even if you abstain, give your best answer and its confidence.')
STRICT = "Return only the JSON object, nothing else."


def prompt(history, scene):
    parts = [INTRO, "", "Past scenes, each followed by the correct predicate of its removed relation:"]
    for k, s in enumerate(history, 1):
        parts += ["", f"Scene {k}:", s["text"], f"Answer: {s['answer']}"]
    parts += ["", "Current scene:", scene["text"], "", ASK]
    return "\n".join(parts)


def parse(text):
    m = re.search(r"\{[^{}]*\}", text or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    a, c, r = d.get("answer"), d.get("confidence"), d.get("respond")
    if not isinstance(a, str) or not re.fullmatch(r"[a-z]+", a.strip()) or not isinstance(c, (int, float)) or not 0 <= c <= 1 or not isinstance(r, bool):
        return None
    return {"answer": a.strip(), "confidence": float(c), "respond": r, "前後に余計な文字": text.strip() != m.group(0).strip()}


def call(model, content, what):
    t0 = time.time()
    if model == api.HAIKU:
        r, u, cost = api.haiku_chat([{"role": "user", "content": content}], max_tokens=80, what=what)
        text = "".join(b.get("text", "") for b in r.get("content", []))
        lp = None
    else:
        try:
            r, u, cost = api.together_chat(model, [{"role": "user", "content": content}], max_tokens=80, what=what, logprobs=1)
        except RuntimeError as e:
            if "expected a boolean" not in str(e):
                raise
            # ★ logprobs を真偽で受け取る模型（Qwen3.8-2.4T-A95B）：真偽の形で送り直す（費用は掛からなかった問い合わせ）
            r, u, cost = api.together_chat(model, [{"role": "user", "content": content}], max_tokens=80, what=what, logprobs=True)
        ch = r["choices"][0]
        text = ch["message"].get("content")
        lp = ch.get("logprobs")
    return text, u, cost, time.time() - t0, lp


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    api.set_ledger(os.path.join(os.path.dirname(out.rstrip("/")), "費用.jsonl"))
    st = w.make_set(1, 2)
    picks = []
    for typ, cue in w.CASES:
        idx = [s["i"] for s in st["series"] if s["research"]["door_hidden"] and s["research"]["type"] == typ and s["research"]["cue"] == cue]
        picks += [(i, typ, cue) for i in idx[-2:]]
    picks.sort()
    rows = []
    log = os.path.join(out, "段4の確かめ.jsonl")
    done = {}
    if os.path.exists(log):
        for l in open(log, encoding="utf-8"):
            d = json.loads(l)
            done[(d["模型"], d["場面"])] = d
    for model in MODELS:
        for i, typ, cue in picks:
            if (model, i) in done:
                rows.append(done[(model, i)])
                continue
            scene = st["series"][i]
            content = prompt(st["series"][:i], scene)
            tries = []
            got = None
            for k in range(3):
                text, u, cost, sec, lp = call(model, content if k == 0 else content + "\n" + STRICT, f"段4 {model} 場面 {i} 試み {k + 1}")
                got = parse(text)
                tries.append({"出力": text, "使用量": u, "費用": cost, "秒": round(sec, 2), "logprobs あり": lp is not None})
                if got:
                    break
            row = {"模型": model, "場面": i, "場合": f"{typ}・{cue}", "履歴の場面": i, "正解": scene["answer"], "試み": tries}
            if got:
                row.update(got)
                row["判定"] = ("黙り" if not got["respond"] else "正解" if got["answer"] == scene["answer"] else "誤答")
                row["答えは正しい（黙りも含め、最もありそうな答え）"] = got["answer"] == scene["answer"]
            else:
                row["判定"] = "形の崩れ"
            rows.append(row)
            with open(log, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(model.split("/")[-1], i, typ, cue, row["判定"], row.get("answer"), scene["answer"], row.get("confidence"), len(tries), round(api.spent(), 4), flush=True)
    json.dump({"場面": picks, "一つずつ": rows, "費用（これまでの合計）": round(api.spent(), 4), "指示": {"INTRO": INTRO, "ASK": ASK, "STRICT": STRICT}},
              open(os.path.join(out, "段4の確かめ.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
