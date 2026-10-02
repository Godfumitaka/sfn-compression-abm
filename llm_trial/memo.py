"""メモの試し・一組（委任書「LLM のメモの試し・一組（Haiku 4.5・推論あり）」2026-10-01 夜。仕様 v2 の 3〜5 節）。
★ LLM に渡すのは場面の文字列・正解の記号・メモだけ。研究者用の説明語（店・ドア・通常・例外など）は渡さない。
模型：Claude Haiku 4.5。拡張思考の予算 2,048（予測とメモの書き直しの両方）。推論の中身は記録に残すだけで、次の問い合わせにもメモにも持ち越さない。
  答えは本文（text）だけから読む。形の指定は output_config.format の json_schema。
見せ方：理解検査の段 C（world.render_v2、stage_d.INTRO の読み方・記号の例・「?」の明示・一貫性の明示）。系列と試験は world.make_set(1, 世界, "v2")。
条件：full＝全履歴（過去の場面と正解を全部渡す。メモなし）、long＝L_long 1,000、short＝L_short 150（Haiku のトークン数）。
一試行（仕様 3 節）：
  1. 予測：前のメモと今の場面だけを渡す（全履歴の条件は過去の場面と正解の全部と今の場面）。出力の上限は 推論の予算＋100（理解検査と同じ）。
  2. 正解を知らせる（毎回）。予測の問い合わせとは別に、次の書き直しに渡す。
  3. メモの書き直し：前のメモと、今回の場面・正解だけを渡す。指示は「今後の予測に使う記録を、上限以内に更新する」だけ。自分の予測は渡さない。
- メモの長さ：Haiku のトークン数を数える API（count_tokens）で、メモの文字列を利用者の一つの発言として数え、「正味＝値 − 一文字 a の値 ＋ 1」
  （段 2 の測り方と同じ。仮の決定）。初めのメモは空（"(empty)" と見せる。仮の決定）。
- 上限を超えたメモ：黙って切らない。超過を記録し、超えた長さと上限を知らせて 2 回まで書き直させる（仮の決定：書き直しの問いには、元の問いに
  超えたメモと長さを足す）。それでも超えたら、その系列を「超過」として記録し、その系列を止める（その後の扱いは仕様に無いので、決めずに止まる）。
- 形が崩れたとき（実装の前に決めて記録する。仕様 3 節）：
  - 予測：理解検査（stage_d.py）と同じ。読めなければ「Return only the JSON object, nothing else.」を足して 2 回まで問い直し、
    それでも読めなければ「形の崩れ」。出力の上限で切れたもの（stop_reason が max_tokens）は問い直さず「上限で切れた」として別に数える。
    どちらも正解・誤答・黙りに入れない。
  - 書き直し：読めない・上限で切れた・空のメモは、上の超過と合わせて 3 回まで（初回＋2 回）。それでも得られなければ、その系列を
    「形の崩れ」として止める（仕様に無いので、決めずに止まる）。書き直しの出力の上限は 推論の予算 ＋ 2×L ＋ 200（仮の決定）。
- 試験（仕様 5 節）：10・20・30・40 場面のあと（その場面のメモの書き直しの後）、固定のメモから一問ずつ別々に：ドア 4 問・共有部分 2 問。
  短いメモの条件だけ、書き戻しと対照（writeback.examples。書き戻す店は組 1 の乙）を、メモの末尾に空行を挟んで足し、ドア 4 問ずつ。
  全履歴の条件の試験は、その時点までの場面と正解の全部を渡す。試験の正解は知らせず、メモにも履歴にも足さない。
記録：系列ごとに <出力>/<世界>_<条件>.jsonl に一行ずつ足す（途中から続けられる）。費用は <出力の親>/費用.jsonl。
使い方（鍵のある環境で）  zsh -ic 'python3.12 llm_trial/memo.py <出力の場所> <世界> <条件 full|long|short> [学習の場面をここまでで止める]'"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api  # noqa: E402
import stage4 as s4  # noqa: E402
import stage_d as sd  # noqa: E402
import world as w  # noqa: E402
import writeback as wb  # noqa: E402

SET_SEED = 1
THINK = 2048
LIMITS = {"long": 1000, "short": 150}
TEST_AT = (10, 20, 30, 40)
EMPTY = "(empty)"

READ = sd.INTRO.rsplit("\n", 1)[0]   # 記号の読み方・例・「?」の明示（最後の一文＝課題の言い方は条件ごとに書く）
TASK_MEMO = ("Scenes that look the same have a consistent answer. This is a prediction task: use your memo, which is your own record "
             "of past scenes and their answers, to predict the answer for the current scene.")
UPDATE = "Update your memo, the record you will use for future predictions. The updated memo must be at most {L} tokens long."
MEMO_SCHEMA = {"type": "object", "properties": {"memo": {"type": "string"}}, "required": ["memo"], "additionalProperties": False}


def show_memo(memo):
    return "Your memo:\n----- memo start -----\n" + (memo if memo else EMPTY) + "\n----- memo end -----"


def predict_prompt(memo, scene_text):
    return "\n".join([READ, TASK_MEMO, "", show_memo(memo), "", "Current scene:", scene_text, "", sd.ASK])


def update_prompt(memo, scene, L):
    return "\n".join([READ, "", show_memo(memo), "", "New scene:", scene["text"], f"Correct answer: {scene['answer']}", "",
                      UPDATE.format(L=L), 'Respond with only a JSON object of the form {"memo": "<the updated memo>"}.'])


BASE = [None]


def memo_tokens(memo):
    if BASE[0] is None:
        BASE[0] = api.haiku_count("a")
    return api.haiku_count(memo if memo else EMPTY) - BASE[0] + 1


MODEL = [None]          # None なら Haiku（拡張思考の予算 THINK）。"claude-sonnet-5-5" などなら adaptive の推論 ＋ effort（2026-10-02 夕方）
EFFORT = [None]
DISPLAY = [None]
SONNET_MAXTOK = 32000   # Sonnet・Opus の出力の上限（理解検査の段 D4 と同じ仮の決定）


def haiku(content, max_tokens, schema, what):
    t0 = time.time()
    if MODEL[0] is not None:
        r, u, cost = api.claude_chat(MODEL[0], [{"role": "user", "content": content}], max_tokens=SONNET_MAXTOK, what=what,
                                     output_format={"type": "json_schema", "schema": schema}, effort=EFFORT[0], display=DISPLAY[0])
    else:
        r, u, cost = api.haiku_chat([{"role": "user", "content": content}], max_tokens=max_tokens, what=what,
                                    output_format={"type": "json_schema", "schema": schema}, thinking_budget=THINK)
    text = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
    th = "".join(b.get("thinking", "") for b in r.get("content", []) if b.get("type") == "thinking")
    return {"出力": text, "使用量": u, "費用": cost, "秒": round(time.time() - t0, 2), "上限で切れた": r.get("stop_reason") == "max_tokens",
            "推論の文字数": len(th), "推論の中身": th, **api.response_meta(r, u)}


def predict(content, answer, what):
    tries, got = [], None
    for k in range(3):
        t = haiku(content if k == 0 else content + "\n" + s4.STRICT, sd.MAXTOK + (THINK or 0), sd.SCHEMA, f"{what} 試み {k + 1}")
        got = s4.parse(t["出力"])
        tries.append(t)
        if got or t["上限で切れた"]:
            break
    row = {"正解": answer, "試み": tries}
    if got:
        row.update(got)
        row["判定"] = "黙り" if not got["respond"] else ("正解" if got["answer"] == answer else "誤答")
        row["最もありそうな答えが正しい"] = got["answer"] == answer
    else:
        row["判定"] = "上限で切れた" if tries[-1]["上限で切れた"] else "形の崩れ"
    return row


def update(memo, scene, L, what):
    base = update_prompt(memo, scene, L)
    tries, content = [], base
    for k in range(3):
        t = haiku(content, THINK + 2 * L + 200, MEMO_SCHEMA, f"{what} 試み {k + 1}")
        new = None
        if not t["上限で切れた"]:
            try:
                new = json.loads(t["出力"]).get("memo")
            except (json.JSONDecodeError, AttributeError):
                new = None
        if not isinstance(new, str) or not new.strip():
            t["結果"] = "上限で切れた" if t["上限で切れた"] else "形の崩れ"
            tries.append(t)
            content = base + "\n" + s4.STRICT
            continue
        n = memo_tokens(new)
        t.update({"メモ": new, "メモのトークン数": n})
        tries.append(t)
        if n <= L:
            t["結果"] = "上限以内"
            return new, n, tries, None
        t["結果"] = "超過"
        content = (base + f"\n\nYour previous memo was {n} tokens long, which exceeds the limit of {L} tokens:\n----- previous memo start -----\n"
                   + new + f"\n----- previous memo end -----\nRewrite the memo so that it is at most {L} tokens long.")
    return None, None, tries, ("超過" if tries[-1]["結果"] == "超過" else "形の崩れ")


def main():
    out, world, cond = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    stop_at = int(sys.argv[4]) if len(sys.argv) > 4 else 40
    os.makedirs(out, exist_ok=True)
    api.set_ledger(os.path.join(os.path.dirname(out.rstrip("/")), "費用.jsonl"))
    st = w.make_set(SET_SEED, world, "v2")
    L = LIMITS.get(cond)
    log = os.path.join(out, f"w{world}_{cond}.jsonl")
    rows = [json.loads(l) for l in open(log, encoding="utf-8")] if os.path.exists(log) else []
    if any(r["段"] == "止まった" for r in rows):
        print("この系列は止まっている：", [r for r in rows if r["段"] == "止まった"][0]["理由"])
        return
    learned = {r["i"]: r for r in rows if r["段"] == "学習"}
    done_test = {(r["t"], r["種類"], r["k"]) for r in rows if r["段"] == "試験"}
    memo = ""

    def put(row):
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def tests(t):
        sets = [("元", memo)]
        wbx = None
        if cond == "short":
            wbx = wb.examples(st, t)
            if wbx["実施"]:
                sets += [("書き戻し", memo + "\n\n" + wbx["書き戻し"]), ("対照", memo + "\n\n" + wbx["対照"])]
            elif (t, "書き戻し", -1) not in done_test:
                put({"段": "試験", "t": t, "種類": "書き戻し", "k": -1, "実施": False, "理由": wbx["理由"]})
        for kind, m in sets:
            for k, q in enumerate(st["tests"]):
                if kind != "元" and q["kind"] != "ドア":
                    continue
                if (t, kind, k) in done_test:
                    continue
                if cond == "full":
                    content = sd.prompt(st["series"][:t], q)
                else:
                    content = predict_prompt(m, q["text"])
                row = predict(content, q["answer"], f"メモ w{world} {cond} 試験 {t} {kind} 問 {k}")
                row.update({"段": "試験", "t": t, "種類": kind, "k": k, "問の種類": q["kind"], "場合": f"{q['research']['type']}・{q['research']['cue']}"})
                if kind != "元":
                    row.update({"足した場面": wbx["書き戻しの場面" if kind == "書き戻し" else "対照の場面"], "足した文字列": m[len(memo):]})
                    row["メモ＋足したもののトークン数"] = memo_tokens(m)
                put(row)
                print(world, cond, "試験", t, kind, k, row["判定"], round(api.spent(), 4), flush=True)

    for s in st["series"]:
        i = s["i"]
        if i >= stop_at:
            break
        if i in learned:
            memo = learned[i].get("メモ（後）", memo)
            if i + 1 in TEST_AT:
                tests(i + 1)
            continue
        res = s["research"]
        content = sd.prompt(st["series"][:i], s) if cond == "full" else predict_prompt(memo, s["text"])
        row = predict(content, s["answer"], f"メモ w{world} {cond} 学習 {i}")
        row.update({"段": "学習", "i": i, "場合": f"{res['type']}・{res['cue']}", "ドアを伏せた": res["door_hidden"], "経験の数（この場面まで）": res["seen_after"]})
        if cond != "full":
            row["メモ（前）"] = memo
            new, n, tries, fail = update(memo, s, L, f"メモ w{world} {cond} 書き直し {i}")
            row["書き直し"] = tries
            if fail:
                put(row)
                put({"段": "止まった", "i": i, "理由": fail, "上限": L})
                print(world, cond, "止まった", i, fail, flush=True)
                return
            memo = new
            row.update({"メモ（後）": memo, "メモのトークン数": n})
        put(row)
        print(world, cond, "学習", i, row["判定"], row.get("メモのトークン数"), round(api.spent(), 4), flush=True)
        if i + 1 in TEST_AT:
            tests(i + 1)


if __name__ == "__main__":
    main()
