"""メモの試し・上限の格子（予約の委任書「LLM のメモの試し・上限の格子（Haiku 4.5・推論あり）」2026-10-01 深夜）。
前の memo.py（一組）との違い（委任書の 1〜3）：
- 書き直しの指示に三文を足す（指示は全メモ条件で同じ。予測の指示と全履歴の条件は変えない）。
- 主の条件：一度だけ書かせる。メモの本文が上限 L を超えたら、上限内に入る最長の先頭だけを保存する。
  切る位置：Python の文字（Unicode の符号位置）の境界。トークン数を数える API で数えながら、文字の数で二分探索する。研究者は意味を補わない。
- 比べの条件（L＝150 だけ、名は c150）：超えたら一度だけ書き直させる（書き直しの問いは memo.py と同じ：元の問いに、超えたメモと長さを足す）。
  それでも超えたら主の条件と同じく切る。
- 形の崩れ（JSON が読めない、出力が上限で切れた、空）：STRICT を足して 2 回まで問い直す。それでも得られなければ、前に保存したメモのままとし、
  「形の崩れ」として記録する。
- 書き直しの一回の出力の上限（推論を含む）は 2,048＋1,000 で全条件同じ。予測の出力の上限は 2,048＋100 のまま（理解検査と同じ。読み）。
- 記録（全部の書き直し）：LLM が書いたメモの全文、保存した文字列、二つのトークン数、切ったか、切った位置が文の途中か・関係式の途中か。
  - 関係式の途中（仮の決定）：保存した先頭の中で「(」が「)」より多い、又は切った位置の前後の文字がどちらも英数字、
    又は切った位置が「rN: 語(…)」か「語(…)」の形の式の内側。
  - 文の途中（仮の決定）：切った位置が行の終わりでなく（保存した先頭の最後の文字も、次の文字も改行でない）、
    保存した先頭の最後の空白でない文字が「. ! ?」のどれでもない。
  - 切った位置の前後 20 文字も残す。
- 費用：問い合わせの名（what）に「格子 w<世界> <条件> 学習／試験／書き直し」を入れ、費用の控えから条件別・種類別に足せるようにする。
メモの長さの数え方・初めのメモ・見せ方・試験・書き戻しと対照は memo.py と同じ（書き戻しと対照は L150・L100・c150 で行う）。
条件の名：full、L1000、L400、L250、L150、L100（主の条件）、c150（比べの条件）。
診断（委任書の 5）：diag A／diag B。研究者が書いたメモ（DIAG_MEMO）を渡し、理解検査の 16 問（stage_d.build(1, 2) の試験。世界 2）に一問ずつ答えさせる。
使い方（鍵のある環境で）  zsh -ic 'python3.12 llm_trial/memo_grid.py <出力の場所> <世界> <条件>'
                          zsh -ic 'python3.12 llm_trial/memo_grid.py <出力の場所> 2 diag'"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api  # noqa: E402
import memo as mm  # noqa: E402
import stage4 as s4  # noqa: E402
import stage_d as sd  # noqa: E402
import world as w  # noqa: E402
import writeback as wb  # noqa: E402

CONDS = {"full": None, "L1000": 1000, "L400": 400, "L250": 250, "L150": 150, "L100": 100, "c150": 150}
WRITEBACK = ("L150", "L100", "c150")
UPDATE_MAXTOK = 2048 + 1000
EXTRA = ("The task instructions will be given to you every time, so you do not need to record them in your memo.\n"
         "Only your saved memo is carried over to the next scene.\n"
         "If your memo is longer than {L} tokens (about {W} words), only its first {L} tokens are saved.")

# 研究者が書いた正しいメモ（委任書の 5。組 1 の記号。研究者の言葉は使わない）。本番のメモとしては使わない
DIAG_MEMO = {
    "A": ("The ? is the first argument of nape.\n"
          "Scenes with vefe and roti: answer puga. Scenes with metu and reso: answer repi.\n"
          "But if the line inside foga is vadi instead of pilu, give the other one (puga <-> repi)."),
    "B": ("The ? is the first argument of nape.\n"
          "Look for vefe (with roti) or metu (with reso), and for pilu or vadi inside foga.\n"
          "vefe + pilu -> puga\n"
          "vefe + vadi -> repi\n"
          "metu + pilu -> repi\n"
          "metu + vadi -> puga"),
}
DIAG_LIMIT = {"A": 100, "B": 150}


def update_prompt(memo, scene, L):
    return "\n".join([mm.READ, "", mm.show_memo(memo), "", "New scene:", scene["text"], f"Correct answer: {scene['answer']}", "",
                      mm.UPDATE.format(L=L), EXTRA.format(L=L, W=round(L * 0.7)),
                      'Respond with only a JSON object of the form {"memo": "<the updated memo>"}.'])


def cut_to(text, L):
    """上限 L 以内に入る最長の先頭（文字の数で二分探索）。返り値：(先頭, トークン数, 数えた回数)。"""
    lo, hi, best, n_best, calls = 0, len(text), 0, None, 0
    while lo <= hi:
        mid = (lo + hi) // 2
        n = mm.memo_tokens(text[:mid]) if mid else 0
        calls += 1
        if n <= L:
            best, n_best, lo = mid, n, mid + 1
        else:
            hi = mid - 1
    return text[:best], n_best, calls


REL = re.compile(r"(?:r\d+:\s*)?[A-Za-z]+\([^()\n]*\)")


def where_cut(full, k):
    head, nxt = full[:k], full[k:k + 1]
    in_rel = (head.count("(") > head.count(")") or (bool(re.match(r"[A-Za-z0-9]", head[-1:] or " ")) and bool(re.match(r"[A-Za-z0-9]", nxt or " ")))
              or any(m.start() < k < m.end() for m in REL.finditer(full)))
    line_end = head.endswith("\n") or nxt == "\n"
    last = head.rstrip()[-1:] if head.rstrip() else ""
    in_sent = (not line_end) and last not in (".", "!", "?")
    return {"関係式の途中": in_rel, "文の途中": in_sent, "行の終わり": line_end, "前の 20 文字": head[-20:], "次の 20 文字": full[k:k + 20]}


def write_once(content, what):
    """形の崩れは 2 回まで問い直す。返り値：(メモの全文 or None, 試みの並び)。"""
    tries = []
    for k in range(3):
        t = mm.haiku(content if k == 0 else content + "\n" + s4.STRICT, UPDATE_MAXTOK, mm.MEMO_SCHEMA, f"{what} 試み {k + 1}")
        new = None
        if not t["上限で切れた"]:
            try:
                new = json.loads(t["出力"]).get("memo")
            except (json.JSONDecodeError, AttributeError):
                new = None
        tries.append(t)
        if isinstance(new, str) and new.strip():
            t["結果"] = "得られた"
            return new, tries
        t["結果"] = "上限で切れた" if t["上限で切れた"] else "形の崩れ"
    return None, tries


def update(memo, scene, L, cond, what):
    base = update_prompt(memo, scene, L)
    rec = {"書き直しの回数": 1}
    full, tries = write_once(base, what)
    if full is None:
        rec.update({"結果": "形の崩れ", "試み": tries, "保存": memo, "保存のトークン数": mm.memo_tokens(memo) if memo else 0, "切った": False})
        return memo, rec
    n_full = mm.memo_tokens(full)
    if n_full > L and cond == "c150":
        rec.update({"一回目の全文": full, "一回目のトークン数": n_full, "書き直しの回数": 2})
        content = (base + f"\n\nYour previous memo was {n_full} tokens long, which exceeds the limit of {L} tokens:\n----- previous memo start -----\n"
                   + full + f"\n----- previous memo end -----\nRewrite the memo so that it is at most {L} tokens long.")
        full2, tries2 = write_once(content, what + " 書き直させた")
        tries += tries2
        if full2 is None:
            rec["二回目"] = "形の崩れ（一回目の全文を切る）"
        else:
            full, n_full = full2, mm.memo_tokens(full2)
    rec.update({"試み": tries, "全文": full, "全文のトークン数": n_full})
    if n_full <= L:
        rec.update({"結果": "上限以内", "保存": full, "保存のトークン数": n_full, "切った": False})
        return full, rec
    saved, n_saved, calls = cut_to(full, L)
    rec.update({"結果": "切った", "保存": saved, "保存のトークン数": n_saved, "切った": True, "切った位置（文字）": len(saved),
                "全文の文字数": len(full), "数えた回数": calls, **where_cut(full, len(saved))})
    return saved, rec


def run_series(out, world, cond):
    st = w.make_set(mm.SET_SEED, world, "v2")
    L = CONDS[cond]
    tag = f"格子 w{world} {cond}"
    log = os.path.join(out, f"w{world}_{cond}.jsonl")
    rows = [json.loads(l) for l in open(log, encoding="utf-8")] if os.path.exists(log) else []
    learned = {r["i"]: r for r in rows if r["段"] == "学習"}
    done_test = {(r["t"], r["種類"], r["k"]) for r in rows if r["段"] == "試験"}
    memo = ""

    def put(row):
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def tests(t):
        sets = [("元", memo)]
        wbx = None
        if cond in WRITEBACK:
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
                content = sd.prompt(st["series"][:t], q) if cond == "full" else mm.predict_prompt(m, q["text"])
                row = mm.predict(content, q["answer"], f"{tag} 試験 {t} {kind} 問 {k}")
                row.update({"段": "試験", "t": t, "種類": kind, "k": k, "問の種類": q["kind"], "場合": f"{q['research']['type']}・{q['research']['cue']}",
                            "メモ": m if cond != "full" else None})
                if kind != "元":
                    row.update({"足した場面": wbx["書き戻しの場面" if kind == "書き戻し" else "対照の場面"], "メモ＋足したもののトークン数": mm.memo_tokens(m)})
                put(row)
                print(world, cond, "試験", t, kind, k, row["判定"], round(api.spent(), 4), flush=True)

    for s in st["series"]:
        i = s["i"]
        if i in learned:
            memo = learned[i].get("メモ（後）", memo)
            if i + 1 in mm.TEST_AT:
                tests(i + 1)
            continue
        res = s["research"]
        content = sd.prompt(st["series"][:i], s) if cond == "full" else mm.predict_prompt(memo, s["text"])
        row = mm.predict(content, s["answer"], f"{tag} 学習 {i}")
        row.update({"段": "学習", "i": i, "場合": f"{res['type']}・{res['cue']}", "ドアを伏せた": res["door_hidden"], "経験の数（この場面まで）": res["seen_after"]})
        if L:
            row["メモ（前）"] = memo
            memo, rec = update(memo, s, L, cond, f"{tag} 書き直し {i}")
            row["書き直し"] = rec
            row["メモ（後）"] = memo
        put(row)
        print(world, cond, "学習", i, row["判定"], (row.get("書き直し") or {}).get("結果"), (row.get("書き直し") or {}).get("保存のトークン数"),
              round(api.spent(), 4), flush=True)
        if i + 1 in mm.TEST_AT:
            tests(i + 1)


def run_diag(out):
    h, tests = sd.build(mm.SET_SEED, 2, 4)
    log = os.path.join(out, "w2_diag.jsonl")
    done = {(r["メモ"], r["問"]) for r in (json.loads(l) for l in open(log, encoding="utf-8"))} if os.path.exists(log) else set()
    info = {}
    for name, memo in DIAG_MEMO.items():
        n = mm.memo_tokens(memo)
        info[name] = {"全文": memo, "トークン数": n, "上限": DIAG_LIMIT[name], "上限以内": n <= DIAG_LIMIT[name]}
        if n > DIAG_LIMIT[name]:
            raise SystemExit(f"診断のメモ {name} が上限を超える：{n}")
        for q, t in enumerate(tests):
            if (name, q) in done:
                continue
            row = mm.predict(mm.predict_prompt(memo, t["text"]), t["answer"], f"格子 w2 diag{name} 試験 問 {q}")
            row.update({"メモ": name, "問": q, "場合": t["case"]})
            with open(log, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print("diag", name, q, t["case"], row["判定"], round(api.spent(), 4), flush=True)
    json.dump(info, open(os.path.join(out, "w2_diag_メモ.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    out, world, cond = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    os.makedirs(out, exist_ok=True)
    api.set_ledger(os.path.join(os.path.dirname(out.rstrip("/")), "費用.jsonl"))
    if cond == "diag":
        run_diag(out)
    else:
        run_series(out, world, cond)


if __name__ == "__main__":
    main()
