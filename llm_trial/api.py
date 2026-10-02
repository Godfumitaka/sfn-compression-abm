"""LLM の小さな試し：API の呼び出しと費用の控え。★ 鍵は環境変数 TOGETHER_API_KEY・ANTHROPIC_API_KEY から、呼ぶときに読む。
鍵をファイル・記録・画面に出さない（失敗のときも、問い合わせの頭は書かない）。
費用：使用量（usage）× 値段で、呼ぶたびに費用の控え（<出力>/費用.jsonl）に足す。合計が上限（既定 1.8 ドル。委任書の 2 ドルの手前）を超えそうなら、呼ばずに止める。
値段（100 万トークンあたりのドル）：Together は /v1/models の pricing（呼ぶ前に一度読む）。Anthropic の Claude Haiku 4.5 は入力 1・出力 5（仮の決定。料金表の値）。
生成の設定：温度 0（決まった形で答えさせるため。仮の決定）。"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

UA = "sfn-llm-trial/0.1"
HAIKU = "claude-haiku-4-5-20251001"
HAIKU_PRICE = {"input": 1.0, "output": 5.0}
LIMIT = float(os.environ.get("LLM_BUDGET", "1.8"))
STATE = {"prices": None, "ledger": None}


class Budget(Exception):
    pass


def _post(url, body, headers, timeout=600):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={**headers, "User-Agent": UA, "Content-Type": "application/json"})
    # 混み合い（429・5xx・529）と通信の途切れは、待って 8 回まで問い直す（格子の走行で並行を増やすため。2026-10-01 深夜）
    for k in range(8):
        try:
            return json.load(urllib.request.urlopen(req, timeout=timeout))
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503, 529) and k < 7:
                time.sleep(min(60, 10 * (k + 1)))
                continue
            raise RuntimeError(f"HTTP {e.code}：{msg}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if k < 7:
                time.sleep(min(60, 10 * (k + 1)))
                continue
            raise RuntimeError(f"通信の失敗：{type(e).__name__}") from None


def set_ledger(path):
    STATE["ledger"] = path


def spent():
    p = STATE["ledger"]
    if not p or not os.path.exists(p):
        return 0.0
    return sum(json.loads(l)["cost"] for l in open(p, encoding="utf-8"))


def _book(model, usage_in, usage_out, price, what):
    cost = (usage_in * price["input"] + usage_out * price["output"]) / 1e6
    with open(STATE["ledger"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.strftime("%H:%M:%S"), "model": model, "in": usage_in, "out": usage_out, "cost": cost, "what": what},
                           ensure_ascii=False) + "\n")
    return cost


def _guard(extra=0.0):
    if spent() + extra > LIMIT:
        raise Budget(f"費用の上限（{LIMIT} ドル）に届く：これまで {spent():.4f} ドル")


def together_prices():
    if STATE["prices"] is None:
        req = urllib.request.Request("https://api.together.xyz/v1/models",
                                     headers={"Authorization": "Bearer " + os.environ["TOGETHER_API_KEY"], "User-Agent": UA})
        ms = json.load(urllib.request.urlopen(req, timeout=60))
        STATE["prices"] = {m["id"]: m.get("pricing") or {} for m in ms}
    return STATE["prices"]


NO_REASONING = {"reasoning": {"enabled": False}}   # Qwen：推論の過程を出さない指定（仮の決定。二つの候補とも効くことを確かめた）


def together_chat(model, messages, *, max_tokens, what, logprobs=None, temperature=0.0, response_format=None, reasoning=False):
    _guard(0.01)
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if response_format:
        body["response_format"] = response_format
    if "qwen" in model.lower():
        # 推論：既定は切る（NO_REASONING）。reasoning＝真のときだけ入れる（推論の文章は message.reasoning に別に返る）
        body.update({"reasoning": {"enabled": True}} if reasoning else NO_REASONING)
    if logprobs:
        body["logprobs"] = logprobs
    r = _post("https://api.together.xyz/v1/chat/completions", body, {"Authorization": "Bearer " + os.environ["TOGETHER_API_KEY"]})
    u = r.get("usage") or {}
    pr = together_prices().get(model) or {}
    cost = _book(model, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), {"input": pr.get("input", 0), "output": pr.get("output", 0)}, what)
    return r, u, cost


def haiku_chat(messages, *, max_tokens, what, system=None, temperature=0.0, output_format=None, thinking_budget=None):
    _guard(0.01)
    body = {"model": HAIKU, "messages": messages, "max_tokens": max_tokens}
    if thinking_budget:
        # 拡張思考（推論）：温度は指定しない（提供元の決まり）。推論の中身は記録に残すが、次の問い合わせには持ち越さない
        body["thinking"] = {"type": "enabled", "budget_tokens": int(thinking_budget)}
    elif temperature is not None:
        body["temperature"] = temperature
    if output_format:
        body["output_config"] = {"format": output_format}
    if system:
        body["system"] = system
    r = _post("https://api.anthropic.com/v1/messages", body, {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
    u = r.get("usage") or {}
    cost = _book(HAIKU, u.get("input_tokens", 0), u.get("output_tokens", 0), HAIKU_PRICE, what)
    return r, u, cost


def haiku_count(text):
    """Anthropic のトークン数を数える API（count_tokens）。費用はかからない（控えにも 0 で書く）。"""
    r = _post("https://api.anthropic.com/v1/messages/count_tokens", {"model": HAIKU, "messages": [{"role": "user", "content": text}]},
              {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
    return r["input_tokens"]


# ---------------------------------------------------------------- Sonnet 5.5・Opus 5.5（2026-10-02 昼の返事：理解検査を effort で）
# 値段（100 万トークンあたりのドル、入力・出力）：platform.claude.com/docs/en/about-claude/pricing（2026-10-02 12:58 に確かめた）
CLAUDE_PRICE = {"claude-sonnet-5-5": {"input": 2.0, "output": 10.0}, "claude-opus-5-5": {"input": 4.0, "output": 20.0}}


def claude_chat(model, messages, *, max_tokens, what, output_format=None, effort=None):
    """adaptive の推論（この模型では予算の指定 budget_tokens は 400 で断られる）。effort は output_config.effort。温度は指定しない
    （Sonnet 5.5 は既定値以外が 400）。server-side の fallbacks は使わない（ほかの模型で答え直されると比べにならないため）。"""
    _guard(0.05)
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "thinking": {"type": "adaptive"}}
    oc = {}
    if output_format:
        oc["format"] = output_format
    if effort:
        oc["effort"] = effort
    if oc:
        body["output_config"] = oc
    r = _post("https://api.anthropic.com/v1/messages", body, {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
    u = r.get("usage") or {}
    cost = _book(model, u.get("input_tokens", 0), u.get("output_tokens", 0), CLAUDE_PRICE[model], what)
    return r, u, cost


def count_tokens(model, text):
    """その模型のトークン数を数える API（費用はかからない）。正味＝値 − 一文字 a の値 ＋ 1 は呼ぶ側で。"""
    r = _post("https://api.anthropic.com/v1/messages/count_tokens", {"model": model, "messages": [{"role": "user", "content": text}]},
              {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
    return r["input_tokens"]


def response_meta(r, u):
    """問いごとの記録に足す応答の控え（2026-10-02 夕方の委任書の 1）：応答の model の欄・応答の ID・使用量（入力・出力・推論のトークン）・
    止まった理由・推論の中身の返り方。送る文字列は変えない（記録だけ）。"""
    blocks = [b for b in (r.get("content") or []) if b.get("type") == "thinking"]
    shown = "".join(b.get("thinking", "") for b in blocks)
    if not blocks:
        how = "推論の塊なし"
    elif shown:
        how = "中身が返った"
    else:
        how = "塊はあるが中身は空（返らない設定）"
    return {"応答の model": r.get("model"), "応答の ID": r.get("id"), "止まった理由": r.get("stop_reason"),
            "入力のトークン": (u or {}).get("input_tokens"), "出力のトークン": (u or {}).get("output_tokens"),
            "推論のトークン": ((u or {}).get("output_tokens_details") or {}).get("thinking_tokens"), "推論の中身の返り方": how}
