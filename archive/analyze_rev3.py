#!/usr/bin/env python3
"""
analyze.py — 本走行の一次解析（rev2・2026-08-29）

出所（確定行）
  M-001  主測定対象は「通過率 = P(E3（薄化の停留）| 段階2到達)」
  M-002  神話は「段階2 × 薄化の停留」
  M-003  段階2 ＝ R と def(R) が生存・使用される一方、
         そのパターンの最後の verbatim が θ′ で落ちた時点
  M-048  終端は E2（R の忘却）と E3（R 生存下の停留）の競合
  M-067  R の同定は NSIM(def, 場面) ≥ T
  T-026  禁止条項 D20：分類と分母を run 前に固定し、台帳から事後判定する

事前登録（主結果1_事前登録_2026-08-30.md）
  段階2 の「そのパターン」  主 b（NSIM 同定された場面の枚）／ 副 a1・a2
  E3 の推定量               主 C（吸収化）／ 副 A・B
  窓幅                      τ_settle（D20(c)。固定 n を置かない）
  → 3 × 3 = 9 通りを併記する

────────────────────────────────────────────────────────────
rev1（2026-08-29）からの修正

1  ★ 固定窓 SETTLE_WINDOWS = (100, 200, 400) を撤去した
   D20(c)「τ_settle は …（d と θ にのみ依存）、固定の n 試行を置かない」に反していた

2  ★ A_first_reach は名前と実装が食い違っていた
   「初到達」と名乗りながら「走行末で W 試行静かか」を計算していた
   → 名前を A_quiet_at_end に改め、事象時刻を返す C を主に置いた

3  ★「試行行に試行番号の欄が無い」は誤り
   prediction_order が全行にある（2026-08-30 実測。行順との一致も確認）

4  ★「verbatim の削除が台帳に記録されていない」は誤り（2026-08-29 撤回17）
   reg_del_events の kind に verbatim_deletion がある
   ただし枚の寿命は floor(θ′⁻²)+1 の定数なので、台帳を読む必要すらない

5  ★ is_myth が arg_kinds を slot_index だけで引いていた
   T-045 の三つ組キー (R, slot_index, registered_at) に直した
   U-033 実測のとおり、同一 slot_index に生存行が複数立つ

6  段階2 の判定を実装した（rev1 では未完成だった）
────────────────────────────────────────────────────────────

使い方
  python3 analyze.py --runs runs/main_2026-08-31 --out analysis
  python3 analyze.py --runs runs/main_2026-08-31 --out analysis --limit 40
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import statistics
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from abm.loop import _apply                      # スナップショットの差分適用
from abm.world import generate_world             # a2 の逆引き表と、モチーフ層別に使う

PATTERNS = ("b", "a1", "a2")                     # 段階2 の「そのパターン」。主は b
ESTIMATORS = ("C", "A", "B")                     # E3 の推定量。主は C
PRIMARY = ("b", "C")
HORIZONS = (300, 100)                            # U-016：報告地平 主 300 ／ 副 100


# ══════════════════════════════════════════════════════════════
# 台帳の読み出し
# ══════════════════════════════════════════════════════════════
def read_ledger(path: Path):
    """(run ヘッダ, 試行行の列) を返す。"""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    if not rows:
        return None, []
    return rows[0], rows[1:]


def trial_index(row, fallback):
    """★ prediction_order を使う。無い行だけ行順に落とす。"""
    value = row.get("prediction_order")
    return int(value) if value is not None else fallback


def rebuild_final_snapshot(trials):
    """state_snapshot の連鎖をたどって、走行末の状態を復元する。

    kind は full / delta / skipped の三種。skipped は変化なしを意味しない
    （撮っていないだけ）ので、直前の値をそのまま持ち越す。
    """
    current = None
    for row in trials:
        snapshot = row.get("state_snapshot")
        if not snapshot:
            continue
        kind = snapshot.get("kind")
        if kind == "full":
            current = snapshot.get("value")
        elif kind == "delta" and current is not None:
            current = _apply(current, snapshot.get("changes") or {})
    return current


# ══════════════════════════════════════════════════════════════
# 世界の再生成（a2 の逆引きと、モチーフ層別）
# ══════════════════════════════════════════════════════════════
_WORLD_CACHE: dict[tuple, tuple[dict, list]] = {}


def world_tables(run_seed, trial_count):
    """(ID → 試行番号, 試行ごとのモチーフ, 試行ごとの G* 述語集合) を返す。

    40 seed で 8 秒ほど。エージェントの再走行はしない。
    """
    key = (str(run_seed), int(trial_count))
    if key not in _WORLD_CACHE:
        world = generate_world(run_seed, trial_count, ("agent",))
        inverse, motifs, predicates = {}, [], []
        for index, trial in enumerate(world.trials):
            motifs.append(trial.motif)
            predicates.append({r.predicate for r in trial.G_star.relations})
            for entity in trial.G_star.entities:
                inverse[entity.entity_id] = index
            for relation in trial.G_star.relations:
                inverse[relation.relation_id] = index
        _WORLD_CACHE[key] = (inverse, motifs, predicates)
    return _WORLD_CACHE[key]


# ══════════════════════════════════════════════════════════════
# 段階2（M-003）
# ══════════════════════════════════════════════════════════════
def verbatim_lifetime(theta_prime):
    """枚は書込から floor(θ′⁻²)+1 試行目に落ちる。

    σ(t) = 経過^(-1/2) を θ′ と比べる（SPEC_B1_impl §C.5.6）。
    f にも seed にも射程にも依らない定数である。
    """
    return math.floor(theta_prime ** -2)


def supply_trials(events, inverse):
    """登録イベントから、三つの読みそれぞれの「供給試行」を集める。

    登録イベント一件は (枚 w, 場面 e) → R の三つ組を作る。
      b   場面 e の試行             = event["trial"]
      a1  base に選ばれた枚の書込   = event["base_written_at"]
      a2  構成素の出所になった枚    = 引数 ID を逆引き
    """
    out = {name: defaultdict(set) for name in PATTERNS}
    for event in events:
        name = event.get("R")
        if name is None:
            continue
        out["b"][name].add(int(event["trial"]))
        base = event.get("base_written_at")
        if base is not None:
            out["a1"][name].add(int(base))
        if inverse is not None:
            for constituent in event.get("constituents") or ():
                for argument in constituent.get("arguments") or ():
                    if argument in inverse:
                        out["a2"][name].add(inverse[argument])
    return out


def stage2_time(supplies, lifetime, horizon):
    """R に属する枚がすべて落ちた最初の試行。届かなければ None。"""
    if not supplies:
        return None
    ordered = sorted(supplies)
    for current, following in zip(ordered, ordered[1:]):
        death = current + lifetime + 1
        if following >= death:                    # 次の供給が来る前に落ちきる
            return death if death <= horizon else None
    death = ordered[-1] + lifetime + 1
    return death if death <= horizon else None


# ══════════════════════════════════════════════════════════════
# τ_settle（D20(c)）
# ══════════════════════════════════════════════════════════════
def decay_ladder(horizon):
    """U-001 の 16 本の時定数。abm.accounting と同じ式を独立に持つ。"""
    return tuple(
        math.exp(-1.0 / (0.3 * ((max(horizon * 3, 0.3) / 0.3) ** (index / 15))))
        for index in range(16)
    )


def tau_settle(snapshot, name, theta_prime, horizon, cap=4000):
    """生存構成素のうち V 最大のものが、いま参加を止めたとして θ′ を割るまでの試行数。

    D20(c)：固定の n 試行を置かない。d（減衰）と θ′ にだけ依存させる。
    参加を止める ＝ merit の増分 0。R 自体は適用され続けるので機会だけ増える。
    掃引の設定は w = 0 なので embed 項は落ちる（w > 0 なら別途 embed を渡すこと）。
    """
    if not snapshot:
        return None
    definitions = snapshot.get("definitions") or {}
    merit_table = snapshot.get("merit") or {}
    definition = definitions.get(name)
    if not definition:
        return None
    ladder = decay_ladder(horizon)
    best = None
    for row in definition.get("constituents") or ():
        if not row.get("alive"):
            continue
        key = str((name, row.get("slot_index"), row.get("registered_at")))
        merit = merit_table.get(key)
        price = row.get("frozen_price") or {}
        ell = price.get("ell_frozen")
        if not merit or not ell:
            continue
        basis = list(merit.get("basis") or ())
        opportunity = list(merit.get("opportunity_basis") or ())
        if len(basis) != 16 or len(opportunity) != 16:
            continue
        saving = float(ell) + float(price.get("c", 0))
        steps = 0
        while steps < cap:
            denominator = sum(opportunity)
            value = (sum(basis) / denominator if denominator > 0 else 0.0) * (saving / float(ell))
            if value < theta_prime:
                break
            basis = [b * f for b, f in zip(basis, ladder)]              # 増分 0
            opportunity = [o * f + 1.0 for o, f in zip(opportunity, ladder)]
            steps += 1
        best = steps if best is None else max(best, steps)
    return best


# ══════════════════════════════════════════════════════════════
# E3（U-089 の三候補。主は C）
# ══════════════════════════════════════════════════════════════
def m_live_series(trials):
    """def ごとの (試行番号, m_live) の列。"""
    out = defaultdict(list)
    for order, row in enumerate(trials):
        index = trial_index(row, order)
        alive = Counter()
        for constituent in row.get("constituent_states") or ():
            if constituent.get("alive"):
                alive[constituent.get("R")] += 1
        for name, count in alive.items():
            out[name].append((index, count))
    return out


def e2_time(series, horizon):
    """E2 ＝ R の忘却。生存構成素が尽きた最初の試行。尽きなければ None。

    m_live_series は生存が 1 本以上ある試行だけを持つので、
    列が走行末より前で切れていれば、その次の試行で尽きたと読む。
    """
    if not series:
        return None
    last = max(t for t, _ in series)
    return last + 1 if last < horizon else None


def e3_estimators(series, window, horizon):
    """A / B / C を同じ τ_settle で計算する。C だけが事象時刻を返す。"""
    if not series or not window:
        return {}
    ordered = sorted(series)
    born = ordered[0][0]
    changes = [b for (_, x), (b, y) in zip(ordered, ordered[1:]) if x != y]
    last_change = changes[-1] if changes else born

    absorbed = None                                   # C：吸収化
    marks = [born] + changes + [horizon]
    for start, end in zip(marks, marks[1:]):
        if end - start >= window:
            absorbed = start + window
            break

    tail = [t for t in changes if t > horizon - window]
    return {
        "C": absorbed,                                            # 事象時刻 or None
        "A": bool(horizon - last_change >= window),               # 走行末で静かか
        "B": 1.0 - min(len(tail) / window, 1.0),                  # 末尾の無変化割合
        "last_change": last_change,
        "n_changes": len(changes),
        "window": window,
    }


# ══════════════════════════════════════════════════════════════
# 神話（M-002）
# ══════════════════════════════════════════════════════════════
def is_structurally_thin(states, registration):
    """★ 構造的に薄い ＝ 生存構成素がすべて高階（一階の内容を一つも持たない）def。

    ★ これは M-002 の「神話」ではない。
      M-002（確定）神話 ＝ 段階2 × 薄化の停留（E3）
      本関数は 2026-08-28 の実測（台帳 3-12(c)「神話は実在する」）で使った
      構造的な特徴づけであり、M-002 とは別の量である。
      → 走行後は両方を出して突き合わせる。rev1・rev2 は両者を混同していた。

    ★ 三つ組キー (slot_index, registered_at) で引く（T-045 / U-033）。
      slot_index だけだと、同一位置に立つ複数の生存行が潰れる。
    """
    if not registration:
        return False
    kinds = {
        (c.get("slot_index"), c.get("registered_at")): (c.get("arg_kinds") or [])
        for c in (registration.get("constituents") or ())
    }
    alive = [c for c in states if c.get("alive")]
    if not alive:
        return False
    return all(
        "relation" in kinds.get((c.get("slot_index"), c.get("registered_at")), [])
        for c in alive
    )


# ══════════════════════════════════════════════════════════════
# OA（過剰適用率）
# ══════════════════════════════════════════════════════════════
def over_application(applied, supply, motifs, predicates, alive_predicates):
    """OA を三つの対応づけで出す。★ どれを採るかは未決なので併記する。

    M-069（確定）：「R の適用」＝ その試行で採択・使用された def(R) 一本。
    tau_acc を満たしたが選ばれなかった行は分子・分母とも数えない。

    ★ 残る問い（台帳 3-9 / 3-13。Pro の「創発 R 問題」）
      エージェントの R を、世界のどのモチーフの担当と見るか。
      M-067 は 1 モチーフに def を 5〜10 本作るので「M2 の def」が一意に決まらない。
      → 対応づけを三通り置いて、走行後に選べるようにする。

      supply    その def を作った場面の最頻モチーフを担当とする
      applied   その def が使われた場面の最頻モチーフを担当とする
      gstar     ★ 対応づけない。適用場面の G* に生存構成素の述語が
                ★ 一本でも欠けていた割合（「一本も無い」だと適用の条件から常に 0 になる）だけを出す
    """
    out = {"n_applications": len(applied)}
    if not applied or motifs is None:
        return out
    applied_motifs = [motifs[t] for t in applied if t < len(motifs)]
    if not applied_motifs:
        return out
    for tag, source in (("supply", [motifs[t] for t in sorted(supply) if t < len(motifs)]),
                        ("applied", applied_motifs)):
        if not source:
            continue
        home = Counter(source).most_common(1)[0][0]
        out["OA_" + tag] = sum(1 for m in applied_motifs if m != home) / len(applied_motifs)
        out["home_" + tag] = home
    if predicates is not None and alive_predicates:
        unbacked = sum(1 for t in applied
                       if t < len(predicates) and not (alive_predicates <= predicates[t]))
        out["OA_gstar"] = unbacked / len(applied)
    return out


# ══════════════════════════════════════════════════════════════
# 一走行の解析
# ══════════════════════════════════════════════════════════════
def analyse_run(path, use_world=True):
    header, trials = read_ledger(path)
    if header is None or not trials:
        return None, []
    horizon = len(trials) - 1
    theta = float(header.get("theta_prime"))
    lifetime = verbatim_lifetime(theta)

    inverse = motifs = predicates = None
    if use_world:
        try:
            inverse, motifs, predicates = world_tables(
                header.get("run_seed"), header.get("trial_count"))
        except Exception:                              # 世界が作れなければ a2・モチーフ・OA を諦める
            inverse = motifs = predicates = None

    events, registrations = [], {}
    for row in trials:
        for event in row.get("reg_del_events") or ():
            if event.get("kind") == "registration":
                events.append(event)
                registrations[event["R"]] = event
    supplies = supply_trials(events, inverse)

    series = m_live_series(trials)
    used = Counter(r.get("R_used") for r in trials if r.get("R_used"))
    snapshot = rebuild_final_snapshot(trials)

    last_states = defaultdict(list)
    for constituent in trials[-1].get("constituent_states") or ():
        last_states[constituent.get("R")].append(constituent)

    # def ごとの適用試行（M-069：R_used 一本だけ数える）
    applications = defaultdict(list)
    for order, row in enumerate(trials):
        name = row.get("R_used")
        if name:
            applications[name].append(trial_index(row, order))

    # def ごとの行（★ 主結果はここから作る）
    per_def = []
    for name in series:
        window = tau_settle(snapshot, name, theta, header.get("trial_count") or len(trials))
        estimators = e3_estimators(series[name], window, horizon)
        record = {
            "cell": path.parent.name, "seed": header.get("run_seed"),
            "f": header.get("f_setting"), "theta_prime": theta,
            "repair_scope": header.get("arm_repair_scope"),
            "R": name, "adoptions": used.get(name, 0),
            "tau_settle": window,
            "thin": is_structurally_thin(last_states.get(name, []), registrations.get(name)),
            "m_live_final": series[name][-1][1] if series[name] else 0,
            "n_changes": estimators.get("n_changes"),
            "E2_time": e2_time(series[name], horizon),
            "horizon": horizon,
        }
        if motifs:
            counts = Counter(motifs[t] for t in supplies["b"].get(name, ()) if t < len(motifs))
            record["motif"] = counts.most_common(1)[0][0] if counts else None
            registration = registrations.get(name) or {}
            alive_predicates = {
                c.get("predicate") for c in (registration.get("constituents") or ())
                if c.get("alive")
            }
            record.update(over_application(
                applications.get(name, []), supplies["b"].get(name, set()),
                motifs, predicates, alive_predicates))
        for pattern in PATTERNS:
            record["stage2_" + pattern] = stage2_time(
                supplies[pattern].get(name, set()), lifetime, horizon)
        for estimator in ESTIMATORS:
            record["E3_" + estimator] = estimators.get(estimator)
        per_def.append(record)

    # 走行ごとの補助量
    charges = Counter()
    bits = 0.0
    for row in trials:
        source = row.get("charge_source") or {}
        for tag in ("①", "②", "③"):
            charges[tag] += len(source.get(tag) or ())
        bits += row.get("exception_bits_charged") or 0.0
    outcomes = Counter(r.get("outcome_category") for r in trials if r.get("outcome_category"))

    def count(*names):
        return sum(outcomes.get(n, 0) for n in names)

    hits, misses = count("的中", "hit"), count("失敗", "miss")

    # ★ 逐語ベースライン（T-039）。水位の命題(i) の直接の材料
    #   「反証材料は手元にあったが、誤りとして記帳されなかった」を数値で出す
    spoke = [r for r in trials if r.get("predicted_edge") is not None]
    verbatim_available = [r for r in trials if r.get("verbatim_baseline_prediction") is not None]
    rescued = sum(1 for r in trials
                  if r.get("verbatim_baseline_hit") and not r.get("hit"))
    wasted = sum(1 for r in trials
                 if r.get("hit") and not r.get("verbatim_baseline_hit"))
    total_used = sum(used.values())
    thin_names = {r["R"] for r in per_def if r["thin"]}
    # ★ M-002 の神話 ＝ 段階2 × E3。主 (b, C)・地平 300 で判定する
    myth_names = set()
    for record in per_def:
        stage2 = record.get("stage2_b")
        e3 = record.get("E3_C")
        if stage2 is not None and e3 is not None and e3 <= stage2 + HORIZONS[0]:
            myth_names.add(record["R"])
    run = {
        "cell": path.parent.name, "seed": header.get("run_seed"),
        "f": header.get("f_setting"), "theta_prime": theta,
        "repair_scope": header.get("arm_repair_scope"),
        "code_commit": (header.get("code_commit") or "")[:12],
        "T": len(trials), "verbatim_lifetime": lifetime + 1,
        "n_defs": len(series), "adoptions": total_used,
        "n_thin_defs": len(thin_names),
        "n_myth_defs_M002": len(myth_names),
        "myth_rate_M002": (sum(used.get(n, 0) for n in myth_names) / total_used)
                          if total_used else 0.0,
        "thin_rate": (sum(used.get(n, 0) for n in thin_names) / total_used) if total_used else 0.0,
        "n_1": charges["①"], "n_2": charges["②"], "n_3": charges["③"],
        "exception_bits": round(bits, 3),
        "hits": hits, "misses": misses,
        "pending": count("保留", "pending"), "unresolved": count("未解決", "unresolved"),
        "h_subjective": hits / (hits + misses) if (hits + misses) else None,
        "pending_rate": count("保留", "pending") / len(trials),
        # ── 逐語ベースライン（T-039）──
        "coverage": len(spoke) / len(trials),
        "accuracy_def": (sum(r.get("hit") or 0 for r in spoke) / len(spoke)) if spoke else None,
        "accuracy_verbatim": (sum(r.get("verbatim_baseline_hit") or 0
                                  for r in verbatim_available) / len(verbatim_available))
                             if verbatim_available else None,
        "verbatim_rescues": rescued,          # ★ 枚なら当たっていたのに def が外した試行
        "verbatim_rescue_rate": rescued / len(trials),
        "def_beats_verbatim": wasted,
    }
    return run, per_def


# ══════════════════════════════════════════════════════════════
# 通過率（D20(a) の分母規則）
# ══════════════════════════════════════════════════════════════
def pass_rate(defs, pattern, estimator, report_horizon=None):
    """P(E3 | 段階2到達)。

    ★ 主（推定量 C）は U-016 の報告地平で読む。
      段階2 到達時刻 s から report_horizon 試行ぶん追跡できた def だけを分母に入れ、
      その窓の内側で E3 が起きたかを分子にする。
      追跡が足りない def は打ち切りとして分母から外し、件数を別に報告する（D20(a)）。
      ★ E2（R の忘却）は分母に入る。E3 していなければ分子に入らないだけ。

    A・B は事象時刻を返さないので地平で読めない。走行末の状態として数える。
    """
    reached = numerator = censored = not_reached = e2_in = 0
    for record in defs:
        stage2 = record.get("stage2_" + pattern)
        if stage2 is None:
            not_reached += 1
            continue
        value = record.get("E3_" + estimator)
        if estimator == "C" and report_horizon is not None:
            deadline = stage2 + report_horizon
            if deadline > record.get("horizon", 0):
                censored += 1                      # 追跡が地平に届かない
                continue
            reached += 1
            if record.get("E2_time") is not None:
                e2_in += 1                         # E2 も分母に入る（D20(a)）
            if value is not None and value <= deadline:
                numerator += 1
        else:
            reached += 1
            if record.get("E2_time") is not None:
                e2_in += 1
            if estimator == "C":
                numerator += int(value is not None)
            elif estimator == "A":
                numerator += int(bool(value))
            else:
                numerator += int((value or 0.0) >= 0.5)
    return {
        "rate": numerator / reached if reached else None,
        "denominator": reached, "numerator": numerator,
        "censored": censored, "not_reached": not_reached,
        "e2_in_denominator": e2_in, "n_defs": len(defs),
    }


def surface(rows, scope, metric, label):
    subset = [r for r in rows if r["repair_scope"] == scope]
    if not subset:
        return
    thetas = sorted({r["theta_prime"] for r in subset})
    print("\n### %s   射程 = %s" % (label, scope))
    print("            θ′ → " + "".join("%12.4f" % t for t in thetas))
    for value in sorted({r["f"] for r in subset}):
        cells, counts = [], []
        for theta in thetas:
            picked = [r[metric] for r in subset
                      if r["f"] == value and r["theta_prime"] == theta
                      and r.get(metric) is not None]
            cells.append(statistics.fmean(picked) if picked else float("nan"))
            counts.append(len(picked))
        line = "".join(("%12.4f" % c) if c == c else "%12s" % "—" for c in cells)
        print("  f=%-9.4f%s   (n=%d)" % (value, line, max(counts) if counts else 0))


def _worker(task):
    """並列用。★ 例外を握って返す（一本の失敗で全体を止めない）。"""
    path, use_world = task
    try:
        run, per_def = analyse_run(Path(path), use_world=use_world)
        return path, run, per_def, None
    except Exception as exc:
        return path, None, [], repr(exc)


# ══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", required=True)
    parser.add_argument("--out", default="analysis")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-world", action="store_true",
                        help="世界を再生成しない（a2 とモチーフ層別を諦める）")
    parser.add_argument("--workers", type=int, default=None,
                        help="並列数（既定 cpu_count-2）。★ 読み込みが律速なので効く")
    args = parser.parse_args()

    root = Path(args.runs)
    files = sorted(p for p in (root / "cells").rglob("seed*") if p.suffix in (".gz", ".jsonl"))
    if args.limit:
        files = files[:args.limit]
    if not files:
        raise SystemExit("★ 台帳が見つかりません: %s" % (root / "cells"))

    workers = args.workers or max(1, (os.cpu_count() or 2) - 2)
    print("台帳 %d 本を読みます（%d 並列）\n" % (len(files), workers))
    runs, defs, failed = [], [], []

    def collect(index, result):
        path, run, per_def, error = result
        if error:
            failed.append((path, error))
        elif run:
            runs.append(run)
            defs.extend(per_def)
        if index % 100 == 0 or index == len(files):
            print("  %d/%d" % (index, len(files)), flush=True)

    if workers > 1:
        # ★ 台帳の読み込み（gzip + JSON）が所要の 9 割を占めるので、そこを並列化する
        #   世界の再生成はプロセスごとにやり直しになるが、1 走行 0.2 秒なので割に合う
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for index, result in enumerate(
                    pool.map(_worker, [(str(p), not args.no_world) for p in files],
                             chunksize=4), 1):
                collect(index, result)
    else:
        for index, path in enumerate(files, 1):
            collect(index, _worker((str(path), not args.no_world)))
    if failed:
        print("\n★ 読めなかった台帳 %d 本" % len(failed))
        for path, error in failed[:5]:
            print("   %s: %s" % (path, error))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("per_run.jsonl", runs), ("per_def.jsonl", defs)):
        (out / name).write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    # ── 主結果1 ─────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("★ 主結果1  通過率 P(E3 | 段階2到達)")
    print("   事前登録：主は (パターン b, 推定量 C)。9 通りを併記する")
    print("=" * 100)
    for horizon in HORIZONS:
        tag = "★ 主" if horizon == HORIZONS[0] else "副"
        print("\n--- 報告地平 %d 試行（U-016 %s）--- 推定量 C は地平で読む" % (horizon, tag))
        print("%-10s%-10s%10s%10s%10s%10s%10s%10s"
              % ("パターン", "推定量", "通過率", "分子", "分母", "うちE2", "打ち切り", "到達せず"))
        for pattern in PATTERNS:
            result = pass_rate(defs, pattern, "C", report_horizon=horizon)
            mark = " ★主" if pattern == PRIMARY[0] else ""
            rate = "%10.4f" % result["rate"] if result["rate"] is not None else "%10s" % "—"
            print("%-10s%-10s%s%10d%10d%10d%10d%10d%s"
                  % (pattern, "C", rate, result["numerator"], result["denominator"],
                     result["e2_in_denominator"], result["censored"],
                     result["not_reached"], mark))

    print("\n--- 走行末で読む（推定量 A・B。★ 事象時刻を返さないので地平で読めない）---")
    print("%-10s%-10s%10s%10s%10s%10s%10s"
          % ("パターン", "推定量", "通過率", "分子", "分母", "うちE2", "到達せず"))
    for pattern in PATTERNS:
        for estimator in ("A", "B"):
            result = pass_rate(defs, pattern, estimator)
            rate = "%10.4f" % result["rate"] if result["rate"] is not None else "%10s" % "—"
            print("%-10s%-10s%s%10d%10d%10d%10d"
                  % (pattern, estimator, rate, result["numerator"], result["denominator"],
                     result["e2_in_denominator"], result["not_reached"]))

    # ── モチーフ層別（D21(a)：プールした線を主図に描かない）──
    strata = sorted({r.get("motif") for r in defs if r.get("motif")})
    if strata:
        print("\n★ モチーフ層別（D21(a)）  主 (b, C)")
        print("%-10s%10s%12s%12s%12s" % ("モチーフ", "通過率", "分子", "分母", "打ち切り"))
        for motif in strata:
            result = pass_rate([r for r in defs if r.get("motif") == motif],
                               *PRIMARY, report_horizon=HORIZONS[0])
            rate = "%10.4f" % result["rate"] if result["rate"] is not None else "%10s" % "—"
            print("%-10s%s%12d%12d%12d"
                  % (motif, rate, result["numerator"], result["denominator"], result["censored"]))

    # ── 面 ────────────────────────────────────────────────
    print("\n" + "=" * 100 + "\n面の集約（f × θ′）\n" + "=" * 100)
    for scope in sorted({r["repair_scope"] for r in runs}):
        for metric, label in (("thin_rate", "★ 構造的に薄い def の率（使用加重）"),
                              ("myth_rate_M002", "★ 神話率 M-002（段階2 × E3・使用加重）"),
                              ("h_subjective", "主観水位 的中/(的中+失敗)"),
                              ("pending_rate", "保留率"),
                              ("n_defs", "def の本数"),
                              ("adoptions", "採択回数"),
                              ("n_1", "① の件数"),
                              ("n_2", "② の件数"),
                              ("exception_bits", "例外費用の総和"),
                              ("accuracy_def", "★ 的中率（def から予測）"),
                              ("accuracy_verbatim", "★ 的中率（枚から予測していたら）"),
                              ("verbatim_rescue_rate", "★ 枚なら当たった率（水位の材料）"),
                              ("coverage", "予測を出した割合")):
            surface(runs, scope, metric, label)

    # ── OA（★ 対応づけ三通りを併記。台帳 3-9 の創発 R 問題が未解決）──
    print("\n" + "=" * 100 + "\n★ OA（過剰適用率）  対応づけ三通り\n" + "=" * 100)
    print("""
  supply  その def を作った場面の最頻モチーフを担当とする
  applied その def が使われた場面の最頻モチーフを担当とする
  gstar   ★ 対応づけない。適用場面の G* に生存構成素の述語が一本も無かった割合
  ★ どれを採るかは未決（M-069 は「適用」の数え方だけを定め、担当の決め方は未定）
""")
    for tag in ("OA_supply", "OA_applied", "OA_gstar"):
        values = [r[tag] for r in defs if r.get(tag) is not None]
        if not values:
            continue
        weighted = [r for r in defs if r.get(tag) is not None and r.get("adoptions")]
        total = sum(r["adoptions"] for r in weighted) or 1
        print("  %-12s def 平均 %.4f ／ ★ 採択加重 %.4f ／ n=%d"
              % (tag, statistics.fmean(values),
                 sum(r[tag] * r["adoptions"] for r in weighted) / total, len(values)))

    print("\n  神話 / 真 の別（★ 主 (b, C) で段階2 到達した def のみ）")
    print("  %-10s%12s%12s%12s%10s" % ("", "OA_supply", "OA_applied", "OA_gstar", "n"))
    for label, picked in (("薄い", [r for r in defs if r.get("thin")]),
                          ("厚い", [r for r in defs if not r.get("thin")])):
        picked = [r for r in picked if r.get("stage2_b") is not None]
        cells = []
        for tag in ("OA_supply", "OA_applied", "OA_gstar"):
            values = [r[tag] for r in picked if r.get(tag) is not None]
            cells.append("%12.4f" % statistics.fmean(values) if values else "%12s" % "—")
        print("  %-10s%s%10d" % (label, "".join(cells), len(picked)))

    # ── τ_settle の分布（D20(c) が固定 n を禁じているので実測を出す）──
    windows = [r["tau_settle"] for r in defs if r.get("tau_settle")]
    if windows:
        print("\n★ τ_settle（D20(c)。固定窓は置かない）")
        print("   中央 %d ／ 四分位 %d–%d ／ 最小 %d ／ 最大 %d ／ n=%d"
              % (statistics.median(windows),
                 statistics.quantiles(windows, n=4)[0] if len(windows) > 3 else min(windows),
                 statistics.quantiles(windows, n=4)[2] if len(windows) > 3 else max(windows),
                 min(windows), max(windows), len(windows)))

    print("""
★ 読み方
  段階2 のパターン
    b   R と同定された場面（M-067）の枚        ← ★ 主
    a1  m1 の base に選ばれた枚                   base_written_at（委任D で追加）
    a2  R の構成素の出所になった枚               引数 ID の逆引き
  E3 の推定量
    C   吸収化。★ τ_settle 分の無変化が最初に成立した時刻を返す  ← ★ 主
    A   走行末で τ_settle 以上 静かか（真偽のみ。事象時刻を返さない）
    B   末尾 τ_settle 試行の無変化割合（0.5 で切って件数化）
  分母  D20(a)：段階2 到達。E2 は分母に入る。到達せず・打ち切りは外して別報告
""")
    print("出力  %s（走行 %d 行）／ %s（def %d 行）"
          % (out / "per_run.jsonl", len(runs), out / "per_def.jsonl", len(defs)))


if __name__ == "__main__":
    main()
