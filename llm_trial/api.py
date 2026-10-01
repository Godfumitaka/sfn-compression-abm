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


def _post(url, body, headers, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={**headers, "User-Agent": UA, "Content-Type": "application/json"})
    for k in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=timeout))
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503, 529) and k < 3:
                time.sleep(5 * (k + 1))
                continue
            raise RuntimeError(f"HTTP {e.code}：{msg}") from None


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


def together_chat(model, messages, *, max_tokens, what, logprobs=None, temperature=0.0, response_format=None):
    _guard(0.01)
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if response_format:
        body["response_format"] = response_format
    if "qwen" in model.lower():
        body.update(NO_REASONING)
    if logprobs:
        body["logprobs"] = logprobs
    r = _post("https://api.together.xyz/v1/chat/completions", body, {"Authorization": "Bearer " + os.environ["TOGETHER_API_KEY"]})
    u = r.get("usage") or {}
    pr = together_prices().get(model) or {}
    cost = _book(model, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), {"input": pr.get("input", 0), "output": pr.get("output", 0)}, what)
    return r, u, cost


def haiku_chat(messages, *, max_tokens, what, system=None, temperature=0.0, output_format=None):
    _guard(0.01)
    body = {"model": HAIKU, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
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
