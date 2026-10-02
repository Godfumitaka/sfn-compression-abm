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
追記（2026-10-02 朝）：段階を組み直した（STAGES の 新2・新4・新5。新1＝"1"、新3＝"2"）。新2 は過去の場面を、伏せた関係に正解を戻した
  完全な場面（world.complete_text）として、同じ書式で並べる（INTRO_OBS・prompt_obs）。組の種を引数で変えられる（確かめは調整に使っていない組で）。
使い方（鍵のある環境で）  zsh -ic 'python3.12 llm_trial/fullhist_stages.py <出力の場所> <世界> <段階> [組の種（既定 1）]'"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api  # noqa: E402
import memo as mm  # noqa: E402
import stage_d as sd  # noqa: E402
import world as w  # noqa: E402

STAGES = {"1": dict(mult=1, door_all=False, think=8000), "2": dict(mult=1, door_all=True, think=2048),
          "3": dict(mult=2, door_all=False, think=2048), "4": dict(mult=2, door_all=True, think=8000),
          # 追記（2026-10-02 朝、ChatGPT の推薦）の組み直し：元の条件（40 場面・ドアは半分・予算 2,048・場面と正解）から一項目だけ変える。
          # 新1＝上の "1"（予算 8,000）、新3＝上の "2"（全部の場面でドア）。新2・新4・新5 をここに足す。
          "新2": dict(mult=1, door_all=False, think=2048, observed=True),
          "新4": dict(mult=2, door_all=False, think=2048),
          "新5": dict(mult=2, door_all=True, think=8000, observed=True),
          # 委任書「例外を増やす・大きな模型」（2026-10-02 昼）の 1：新5 の条件で、例外の割合だけを 0.4・0.5 に
          "例外04": dict(mult=2, door_all=True, think=8000, observed=True, exc=0.4),
          "例外05": dict(mult=2, door_all=True, think=8000, observed=True, exc=0.5),
          # 委任書「LLM 大きな模型の本番（Sonnet 5.5・effort medium）」（2026-10-02 夕方）：Sonnet 5.5、adaptive の推論。
          # 基準＝元の条件（40 場面・ドアは半分・場面と正解・effort medium）。各段階は基準から一項目だけ変える。
          # 「推論を増やす」は、Sonnet では予算を指定できないので effort high に置き換えた。全部合わせるは 完全な場面＋全部ドア＋80 場面＋effort high
          "S基準": dict(mult=1, door_all=False, think=None, model="claude-sonnet-5-5", effort="medium"),
          "S完全": dict(mult=1, door_all=False, think=None, observed=True, model="claude-sonnet-5-5", effort="medium"),
          "S全部ドア": dict(mult=1, door_all=True, think=None, model="claude-sonnet-5-5", effort="medium"),
          "S80": dict(mult=2, door_all=False, think=None, model="claude-sonnet-5-5", effort="medium"),
          "S全部": dict(mult=2, door_all=True, think=None, observed=True, model="claude-sonnet-5-5", effort="high"),
          "S推論": dict(mult=1, door_all=False, think=None, model="claude-sonnet-5-5", effort="high")}
DISPLAY = "summarized"   # Sonnet の推論の中身は要約で返させる（見え方だけ。使ったことを要約の記録に書く）

# 新2（完全な観察済みの場面）の指示：記号の読み方は stage_d.INTRO と同じ。「?」の説明を今の場面だけにし、過去の場面は完全に見せると書く。
# 過去の問いの文（Answer: の行）は省く。新しい規則は教えない（仮の決定。文面はこのとおり）
OBS_FROM = ("In every scene exactly one relation has been removed. Its line is missing, and where it appeared as an argument it is written as `?`. "
            "There is exactly one `?` in each scene.")
OBS_TO = ("In the current scene exactly one relation has been removed. Its line is missing, and where it appeared as an argument it is written as `?`. "
          "There is exactly one `?` in the current scene. The past scenes are shown complete, with nothing removed.")
TASK_FROM = "use the past scenes and their answers to predict the answer for the current scene."
TASK_TO = "use the past scenes to predict the answer for the current scene."
assert OBS_FROM in sd.INTRO and TASK_FROM in sd.INTRO
INTRO_OBS = sd.INTRO.replace(OBS_FROM, OBS_TO).replace(TASK_FROM, TASK_TO)


def prompt_obs(past_full, scene):
    parts = [INTRO_OBS, "", "Past scenes:"]
    for k, t in enumerate(past_full, 1):
        parts += ["", f"Scene {k}:", t]
    parts += ["", "Current scene:", scene["text"], "", sd.ASK]
    return "\n".join(parts)


def text_tokens(t):
    # 本文のトークン数（正味）。Sonnet・Opus はその模型の数え方（2026-10-02 夕方）
    if mm.MODEL[0] is not None:
        return max(api.count_tokens(mm.MODEL[0], t) - BASE[0] + 1, 0) if t else 0
    return max(api.haiku_count(t) - BASE[0] + 1, 0) if t else 0


BASE = [None]


def main():
    out, world, stage = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    set_seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    os.makedirs(out, exist_ok=True)
    api.set_ledger(os.path.join(os.path.dirname(out.rstrip("/")), "費用.jsonl"))
    cfg = STAGES[stage]
    BASE[0] = api.count_tokens(cfg["model"], "a") if cfg.get("model") else api.haiku_count("a")
    mm.THINK = cfg["think"]
    if cfg.get("model"):
        mm.MODEL[0], mm.EFFORT[0], mm.DISPLAY[0] = cfg["model"], cfg.get("effort"), DISPLAY
    st = w.make_set(set_seed, world, "v2", cfg["mult"], cfg["door_all"], cfg.get("exc"))
    _h, tests = sd.build(set_seed, world, 4)
    full = [w.complete_text(set_seed, world, s["i"], s["research"], st["vocab"]) for s in st["series"]] if cfg.get("observed") else None

    def make_prompt(past_n, scene):
        return prompt_obs(full[:past_n], scene) if full is not None else sd.prompt(st["series"][:past_n], scene)

    tag = f"段階{stage}_w{world}" + ("" if set_seed == 1 else f"_組{set_seed}")
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
        row = mm.predict(make_prompt(i, s), s["answer"], f"全履歴 {tag} 学習 {i}")
        row.update({"段": "学習", "i": i, "場合": f"{res['type']}・{res['cue']}", "ドアを伏せた": res["door_hidden"]})
        put(row)
        print(tag, "学習", i, row["判定"], round(api.spent(), 4), flush=True)
    for q, t in enumerate(tests):
        if ("最後の試験", q) in done:
            continue
        row = mm.predict(make_prompt(len(st["series"]), t), t["answer"], f"全履歴 {tag} 試験 {q}")
        row.update({"段": "最後の試験", "i": q, "場合": t["case"]})
        put(row)
        print(tag, "試験", q, t["case"], row["判定"], row.get("answer"), round(api.spent(), 4), flush=True)
    fin = [r for r in rows if r["段"] == "最後の試験"]
    by = {c: sum(1 for r in fin if r["場合"] == c and r.get("最もありそうな答えが正しい")) for c in ("甲・n", "甲・e", "乙・n", "乙・e")}
    best = sum(by.values())
    passed = best >= 15 and all(v >= 3 for v in by.values())
    summ = {"段階": stage, "世界": world, "組": set_seed, **cfg, "推論の中身の見え方": (DISPLAY if cfg.get("model") else "拡張思考（中身が返る）"), "学習の場面の数": len(st["series"]), "最もありそうな答えが正しい（16 問）": best, "場合ごと": by, "通過": passed,
            "判定": {k: sum(1 for r in fin if r["判定"] == k) for k in ("正解", "誤答", "黙り", "形の崩れ", "上限で切れた")}}
    json.dump(summ, open(os.path.join(out, f"{tag}_要約.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("PASS" if passed else "FAIL")
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
