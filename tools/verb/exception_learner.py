"""独立した『例外の辞書＋REG』。模型のライブラリや内部状態を使わない。

predictには語名だけを渡す。観察・開示は、回答確定後にobserveで渡す。
試験ではpredictだけを使う。出現の抽選・刺激の生成・忘却は行わない。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExceptionLearner:
    exceptions: dict[str, str] = field(default_factory=dict)

    def predict(self, verb: str) -> str:
        return self.exceptions.get(verb, "REG")

    def observe(self, verb: str, observed_past: str | None) -> None:
        if observed_past is not None and observed_past.startswith("IRR_"):
            self.exceptions.setdefault(verb, observed_past)


def run_sequence(records, probes):
    """公開された観察欄だけを読み、同じ試行・試験時点を再生する。

records: trial, verb, past_asked, observed_past（非観測ならNone）。
probes: t（それより前のt試行が終わった時点）, verb。
正解や動詞のクラスはこの学び手に渡さず、採点は呼び手が行う。
"""
    learner = ExceptionLearner()
    answers, probe_answers, registrations = [], [], []
    by_t: dict[int, list] = {}
    for probe in probes:
        by_t.setdefault(probe["t"], []).append(probe)
    for t, record in enumerate(records):
        if record["trial"] != t:
            raise ValueError("入力の試行が連続していない")
        answer = learner.predict(record["verb"]) if record["past_asked"] else None
        answers.append({"trial": t, "verb": record["verb"], "past_asked": record["past_asked"], "answer": answer})
        was_known = record["verb"] in learner.exceptions
        learner.observe(record["verb"], record["observed_past"])
        if not was_known and record["verb"] in learner.exceptions:
            registrations.append({"trial": t, "verb": record["verb"], "past": learner.exceptions[record["verb"]]})
        for probe in by_t.get(t + 1, ()):
            probe_answers.append({"t": t + 1, "verb": probe["verb"], "answer": learner.predict(probe["verb"])})
    if len(probe_answers) != len(probes):
        raise ValueError("入力の範囲外に試験の時点がある")
    return {"answers": answers, "probes": probe_answers, "registrations": registrations, "dictionary": dict(learner.exceptions)}
