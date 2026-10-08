"""表層の解析の表を作る（読むだけ。模型は走らせない）。

使い方：
  nice -n 15 ionice -c3 python3.12 ~/surface/surface.py [--jobs 4] [--redo] [--only 構成名,...]
    configs.json の出力先の、完了の印（ledgers/cells/*/seedNNN.done）がある本を読み、
    一本ごとの結果を ~/surface/cache/ に置き（.done・候補の記録・side の記憶の記録の時刻と大きさが変わらなければ読み直さない）、
    ~/surface/out/ に次の表を書き直す。
      per_run.csv               構成・世界・種・範囲（全課題／ドア課題）・日（例外／通常／全日）ごとの数と率、記憶のビット、F/H/U、選ばれた定義のシールの状態
      pairs.csv                 pairs.json の組ごと（同じ世界・同じ種どうし）：合計の比、種ごとに多い・少ないの数、種の選び直し 4,000 回の比の 95% の範囲
      memory_bits_vs_errors.csv 構成・世界ごとの種の平均：記憶のビット（横軸）と、選び間違いの率・不在の率（縦軸）
      seal_states.csv           外れた試行で選ばれた定義のシールの席の区分（選び間違い／区別の喪失ごとの件数）
      meta.json                 定義・本数・使えなかった欄の理由・確かめの数
  種 21〜40 の出力は開かない（seed021〜seed040 のディレクトリは名前だけで飛ばす）。

定義（~/sme_analysis/tables.py と control/2026-10-05_SME版でlogPの試し_Codex.md と同じ）：
  正解＝台帳の hit、棄権（黙り）＝答えなし（predicted_edge が null）、誤答（外れ）＝それ以外。
  例外の日＝台帳の shop_cue が e、通常の日＝n。ドア課題＝台帳の held_out_is_door。
  候補の記録（tools/selcands_sme.py の sme.candidates.jsonl.gz）を使う欄：
    選び間違い＝誤答のうち、門を通って正しく答える定義があった件（correct_gate_passed）。
    区別の喪失＝誤答のうち、そのような定義が無かった件。
    正答できる定義の不在＝課題（棄権・誤答・正解のすべてを分母とする）のうち、門を通って正しく答える定義が無かった件。
      control/2026-10-06_GPTの返事_記憶の値段と注意の腕.md の「正答可能な定義の不在率。ここには棄権した課題も含める」
      「実際に発話できる点予測・対応の基準で測る」に合わせた。よって 不在＝区別の喪失＋不在の棄権（absent_silent）。
      configs.json の absent_basis を "any" にすると、門を見ずに「正しく答える候補が一つも無い」（any_correct）で数える。
    選ばれた定義のシール：外れた試行で selected の候補の、シールの席（side の shop.jsonl の which が sig の (R, reg, slot)）の
      状態[名]（F は固定の名、H は回数 1 以上の履歴の名、U は名なし）を + でつなぐ。席が無い定義は「席が無い」。
  記憶のビット：side の jsonl の kind=v39 の記録の bits_after（試行ごとの記憶の総ビット。tools/v39.py の total_bits の和で、
    side の C_end と一致することが control/2026-10-02_誤りの印と記憶の量_マック.md で確かめられている）。
    mem_bits_mean＝全試行の平均、mem_bits_last＝最後の試行。F/H/U・定義の数も同じ記録の F・H・U・defs。
  候補の記録が無い本（新しい版で再生がまだ・できない）は、それを使う欄を NA にする（推測で埋めない）。
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

import math
import random
import statistics

SCHEMA = 5
BASE = Path(__file__).resolve().parent
OUT = BASE / "out"
CACHE = BASE / "cache"
FORBIDDEN = set(range(21, 41))       # 確認用の種。開かない
DAY = {"e": "例外", "n": "通常"}
SCOPES = ("全課題", "ドア課題")
DAYS = ("例外", "通常", "全日")
OUTCOMES = ("correct", "wrong", "silent")
CAND_KEYS = ("selection_error", "distinction_loss", "absent", "absent_silent", "silent_capable")
COUNT_KEYS = ("tasks",) + OUTCOMES + CAND_KEYS
RATE_KEYS = OUTCOMES + ("selection_error", "distinction_loss", "absent")
MEM_KEYS = ("mem_bits_mean", "mem_bits_last", "defs_mean", "defs_last", "F_mean", "H_mean", "U_mean", "F_last", "H_last", "U_last")
NA = "NA"

MEM_DEF = ("全部の構成で同じ定義：一本の全試行（試行 0〜最後）の、試行の後の記憶の総ビット（side の jsonl の kind=v39 の bits_after。"
           "その試行の学習・忘却の後の値で、tools/v39.py の total_bits の和。v310be の C_end と同じ値）を試行で平均したものが mem_bits_mean。"
           "構成ごとの値（memory_bits_vs_errors.csv の mem_bits_mean）は、それを種で平均したもの。世界 1・2 は別々に出す。"
           "mem_bits_last は最後の試行の値（参考）")
EFFORT_DEF = ("開示のあった試行（台帳の f_fired）あたりの、席を仮に薄くして照合し直した回数（反実仮想の評価の回数）と、一本の実時間"
              "（manifest.jsonl の elapsed_sec）。回数の記録があればそれを使う（古い版の C＝--cf-learn は side の cflearn.jsonl の行"
              "＝開示の試行で選ばれた定義の U でない席ごとに一行）。記録が無ければ予測の時点の記憶（候補の記録 selcands_sme の各候補の席の状態）から数える："
              "第二段・誤り駆動（effort=gate_FH）は門を通った全候補の F・H の席の数、C（selected_FH）は選ばれた定義（台帳の R_used）の F・H の席の数、"
              "D・D＋注意と、反実仮想の無い構成（古い版の A・A_zero・D_tau04）（none）は 0。"
              "cf_reruns_per_disclosed は C の、選択から答えまでのやり直しの回数（F の席は H と U の二回、H の席は U の一回）。"
              "cand_count_per_disclosed は候補の記録から規則で数えた値（記録がある構成では突き合わせ用）")
PROB_DEF = ("実際の答えは一位のまま、(i) 選ばれた定義の答える席が分布から名前を引いた場合の正答の確率 P_{d*}(y)、"
            "(ii) 定義も温度 1 の確率 π で引いた場合の Σ_d π_d P_d(y) を課題で平均する欄（p_selected_mean・p_mixture_mean）。"
            "記録（候補の記録を含む）に P・π が無い構成は空欄にし、prob_status に理由を書く。D・D＋注意・基準は prob_approx に「近似」"
            "（答えが変われば記憶の数え方も変わるため）")
COLUMNS = [
    ("per_run.csv", "config・lambda・world・seed・arm", "構成名・λ の札・世界・種・出力先のディレクトリ名（configs.json）"),
    ("per_run.csv", "run_commit", "本番の版（flag.json の commit の先頭 7 桁）"),
    ("per_run.csv", "scope", "全課題、又はドア課題（台帳の held_out_is_door）"),
    ("per_run.csv", "day", "例外（shop_cue＝e）・通常（n）・全日（両方の和）"),
    ("per_run.csv", "tasks", "課題の数（率の分母）"),
    ("per_run.csv", "correct・wrong・silent", "正解（hit）・誤答（答えあり・外れ）・棄権（答えなし）"),
    ("per_run.csv", "selection_error", "選び間違い：誤答のうち、門を通って正しく答える定義があった件（候補の記録の correct_gate_passed）"),
    ("per_run.csv", "distinction_loss", "区別の喪失：誤答のうち、そのような定義が無かった件"),
    ("per_run.csv", "absent", "正答できる定義の不在：課題のうち、門を通って正しく答える定義が無かった件（棄権を含む）＝distinction_loss＋absent_silent"),
    ("per_run.csv", "absent_silent・silent_capable", "棄権のうち、正答できる定義が無かった件・あった件"),
    ("per_run.csv", "rate_*", "その範囲・日の tasks を分母にした率"),
    ("per_run.csv", "mem_bits_mean・mem_bits_last", MEM_DEF),
    ("per_run.csv", "defs_*・F_*・H_*・U_*", "同じ v39 の記録の定義の数・F/H/U の席の数。_mean は全試行の平均、_last は最後の試行"),
    ("per_run.csv", "selerr_selected_seal_states・distloss_selected_seal_states",
     "誤答で選ばれた定義のシールの席の区分（状態[名]、+ でつなぐ）と件数。席が無い定義は「席が無い」"),
    ("per_run.csv", "p_selected_mean・p_mixture_mean・prob_approx・prob_status", PROB_DEF),
    ("per_run.csv", "candidates_status・candidates_source", "候補の記録の有無と出どころ。NA なら候補の記録を使う欄は NA"),
    ("per_run.csv", "memory_status", "記憶の記録が読めたか（ok 以外は記憶の欄が NA）"),
    ("pairs.csv", "num_config・den_config・world・scope・day・metric", "比べる組（num÷den）・世界・範囲・日・比べる数（rate_* 又は mem_bits_mean）"),
    ("pairs.csv", "n_seeds・seeds", "両方にある種（同じ種どうしで比べる）"),
    ("pairs.csv", "num_total・den_total・num_tasks・den_tasks", "種の合計の数と課題の数（mem_bits_mean では種ごとの値の合計）"),
    ("pairs.csv", "ratio", "合計の比＝(Σnum/Σnum_tasks)÷(Σden/Σden_tasks)"),
    ("pairs.csv", "seeds_num_more・seeds_num_less・seeds_equal", "種ごとに num の率が多い・少ない・同じ種の数"),
    ("pairs.csv", "ci95_lo・ci95_hi・ci_contains_1",
     "種を重複ありで選び直した 4,000 回の比の 2.5%・97.5% の順位の値、その範囲が 1 を含むか"),
    ("pairs.csv", "boot_resamples・boot_undefined・rng_seed", "選び直しの回数・0/0 で除いた回数・乱数の種"),
    ("memory_bits_vs_errors.csv", "mem_bits_mean・mem_bits_mean_sd", "一本の mem_bits_mean の、種の平均と標準偏差（横軸）"),
    ("memory_bits_vs_errors.csv", "rate_selection_error_mean・rate_absent_mean（_sd）", "一本の率の、種の平均（と標準偏差）（縦軸）"),
    ("memory_bits_vs_errors.csv", "n_seeds_with_candidates", "候補の記録がある種の数（選び間違い・不在の平均はこの種だけ）"),
    ("effort.csv", "effort_rule", "数え方：none（0）・gate_FH・selected_FH（configs.json の effort）"),
    ("effort.csv", "disclosed_trials", "開示のあった試行の数（台帳の f_fired）"),
    ("effort.csv", "cf_evals_total・cf_evals_per_disclosed・cf_evals_source", EFFORT_DEF),
    ("effort.csv", "cf_reruns_per_disclosed", "C の、選択から答えまでのやり直しの回数（開示の試行あたり）"),
    ("effort.csv", "cand_count_per_disclosed", "候補の記録から規則で数えた値（記録と突き合わせる）"),
    ("effort.csv", "elapsed_sec", "一本の実時間（manifest.jsonl の elapsed_sec、秒）。「種の平均」の行は種の平均"),
    ("seal_states.csv", "error_kind・selected_seal_class・selected_seal_state・trials", "誤答の型ごとの、選ばれた定義のシールの区分と件数"),
    ("mechanism_<構成>.csv", "complete・trials_read・results_hold", "完了の印があるか・読めた試行の数・成績の表を保留した群か（mechanism.py。数え方は mechanism_meta.json）"),
    ("mechanism_<構成>.csv", "m1_defs_le1_frac_from200（_trials・m1_defs0_trials_from200・m1_trials_from200）・m1_defs_last",
     "M1：side の kind=v39 の defs（試行の後の定義の数）。試行番号 200 以降（0 始まり）で 1 以下の試行の割合と数、0 の試行の数、最後の試行の値"),
    ("mechanism_<構成>.csv", "m2_*", "M2：stage2 の本流の開示の試行（f_fired）の rows の各席の delta（照合し直した Δr）が 0・負・正の数と割合（分母は測った席）。"
     "m2_disclosed_no_seats は測る席が無かった開示の試行の数"),
    ("mechanism_<構成>.csv", "m3_births・m3_assim・m3_retire・m3_check_…", "M3：side の kind=birth の数（誕生）、kind=assim の数（同化）、kind=v39 の retire の数（退役）。誕生−退役＝最後の定義の数か"),
    ("mechanism_<構成>.csv", "m4_cases・m4_seats_in_cases", "M4：kind=v39 の conv（実行された F→H・H→U）を (試行, 定義) でまとめ、違う席が二つ以上の組の数とその席の数"),
    ("mechanism_<構成>.csv", "m5_elapsed_sec・m5_peak_rss_gib（_source）", "M5：manifest.jsonl の elapsed_sec。最大常駐は time -v の記録、無ければ manifest の peak_rss_mb（KiB÷1e6 の値を GiB に直した）"),
    ("mechanism_<構成>.csv", "m6_*", "M6：researcher の calibration の candidates の V（第二段の価値）の符号。m6_pos_frac は本番の候補（reference が偽の FH・HU）の正の割合。"
     "m6_ref_HU_pos_frac は参照の H→U。記録が無い本は NA"),
    ("mechanism_<構成>.csv", "birth_init_*", "参考：stage2 の .initial.jsonl.gz（出生の仮の問い）の delta_by_slot（席ごとの出生の初期値）の符号の数"),
    ("mechanism_trajectory_<構成>.csv", "block_first_trial・block_last_trial・defs_after・F・H・U・bits_after",
     "M1 の推移：100 試行ごとの区間の最後の試行の後の定義の数・席の数・記憶のビット（side の kind=v39）"),
    ("mechanism_trajectory_<構成>.csv", "births_in_block・assim_in_block・retire_in_block", "M3 の区間ごとの数"),
]


def expand(p):
    return Path(os.path.expanduser(str(p)))


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 本の一覧

def seed_dirs(arm_dir):
    if not arm_dir.is_dir():
        return
    for d in sorted(arm_dir.iterdir()):
        m = re.fullmatch(r"seed(\d{3})", d.name)
        if not m:
            continue
        s = int(m.group(1))
        if s in FORBIDDEN:
            continue          # 種 21〜40 は名前だけ見て飛ばす
        yield s, d


def done_file(run_dir, seed):
    p = sorted(run_dir.glob(f"ledgers/cells/*/seed{seed:03d}.done"))
    return p[0] if len(p) == 1 else None


def discover(cfg, include_held=False):
    """configs.json から、完了した本の一覧を返す。results_hold の群（成績の表を保留）は include_held のときだけ入れる。"""
    runs, notes, todo, held = [], [], [], 0
    for g in cfg["groups"]:
        if g.get("todo"):
            todo.append(g.get("name", ""))
            continue
        root = expand(g["root"])
        if not root.is_dir():
            notes.append(f"群「{g.get('name')}」の出力先 {root} が無い")
            continue
        for arm, spec in g["arms"].items():
            for seed, d in seed_dirs(root / arm):
                if spec.get("seeds") and seed not in spec["seeds"]:
                    continue
                df = done_file(d, seed)
                if df is None:
                    continue
                if g.get("results_hold") and not include_held:
                    held += 1
                    continue
                runs.append({"group": g.get("name", ""), "arm": arm, "seed": seed, "run_dir": str(d), "done": str(df),
                             "config": spec["config"], "world": spec["world"], "lambda": spec.get("lambda", ""),
                             "family": spec.get("family", g.get("family", "")),
                             "effort": spec.get("effort", g.get("effort", "TODO")),
                             "prob": spec.get("prob", g.get("prob")),
                             "prob_approx": bool(spec.get("prob_approx", False)),
                             "results_hold": bool(g.get("results_hold", False)),
                             "time_log": g.get("time_log"),
                             "replay_dir": str(expand(g.get("replay_dir", BASE / "replay"))),
                             "memory": {**cfg.get("memory", {}), **g.get("memory", {})}})
    if todo:
        notes.append(f"TODO（雛形）の群 {len(todo)} を飛ばした：" + "・".join(todo))
    if held:
        notes.append(f"成績の表を保留した群（results_hold）の本 {held} を成績の表から外した（仕組みの表 mechanism.py には出す）")
    return runs, notes


# ---------------------------------------------------------------- 一本の計算

def one(path_glob):
    p = sorted(Path(path_glob[0]).glob(path_glob[1]))
    return p[0] if len(p) == 1 else None


def stat_key(p):
    if p is None or not Path(p).exists():
        return None
    st = Path(p).stat()
    return [str(p), st.st_mtime_ns, st.st_size]


def candidate_file(run):
    """候補の記録を探す。(1) 再生の置き場 <replay_dir>/<arm>/seedNNN/ で replay.json の status が ok のもの、
    (2) 本番の side に sme.candidates.jsonl.gz があればそれ。無ければ None と理由。"""
    rd = Path(run["replay_dir"]) / run["arm"] / f"seed{run['seed']:03d}"
    rj = rd / "replay.json"
    if rj.exists():
        rep = load_json(rj)
        if rep.get("status") == "ok" and (rd / "sme.candidates.jsonl.gz").exists():
            return rd / "sme.candidates.jsonl.gz", f"再生 {rep.get('replay_code_commit', '')}（{rd}）", rj
        reason = f"再生が ok でない（{rj}：{rep.get('status')}）"
    else:
        reason = "再生の記録なし"
    side = one((run["run_dir"], f"side/*/seed{run['seed']:03d}.sme.candidates.jsonl.gz"))
    if side is not None:
        return side, "本番の side", None
    return None, reason, rj if rj.exists() else None


def cache_key(run, absent_basis):
    cf, _, rj = candidate_file(run)
    mem = one((run["run_dir"], f"side/*/seed{run['seed']:03d}.jsonl"))
    cfl = one((run["run_dir"], f"side/*/seed{run['seed']:03d}.cflearn.jsonl"))
    man = Path(run["run_dir"]) / "manifest.jsonl"
    return {"schema": SCHEMA, "absent_basis": absent_basis, "done": stat_key(run["done"]), "cand": stat_key(cf),
            "cflearn": stat_key(cfl), "manifest": stat_key(man if man.exists() else None),
            "replay_json": stat_key(rj), "mem": stat_key(mem), "memory_cfg": run["memory"]}


def seat_names(s):
    if s["state"] == "F":
        return [s["fixed_name"]]
    if s["state"] == "H":
        h = s["history"] or {}
        return sorted(k for k, v in h.items() if v >= 1) if isinstance(h, dict) else sorted(h)
    return []


def seal_seats(c, sealkeys):
    return [{"slot": s["slot"], "state": s["state"], "names": seat_names(s)}
            for s in sorted(c["slots"], key=lambda s: s["slot"]) if (c["R"], c["born_trial"], s["slot"]) in sealkeys]


def seal_label(seats):
    if not seats:
        return "席が無い"
    return "+".join(x["state"] + ("[" + "|".join(x["names"]) + "]" if x["names"] else "") for x in seats)


def memory_stats(run):
    m = run["memory"]
    p = one((run["run_dir"], f"side/*/seed{run['seed']:03d}.jsonl"))
    if p is None:
        return None, "side の jsonl なし"
    kind = m.get("kind", "v39")
    f = m.get("fields", {"bits": "bits_after", "defs": "defs", "F": "F", "H": "H", "U": "U"})
    tag = f'"kind": "{kind}"'
    rows = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            if tag not in line[:40]:
                continue
            r = json.loads(line)
            if r.get("kind") == kind:
                rows.append(r)
    if not rows:
        return None, f"side の jsonl に kind={kind} の記録なし"
    rows.sort(key=lambda r: r["trial"])
    out = {"mem_trials": len(rows)}
    for k, name in (("mem_bits", "bits"), ("defs", "defs"), ("F", "F"), ("H", "H"), ("U", "U")):
        vals = [r.get(f[name]) for r in rows]
        if any(v is None for v in vals):
            return None, f"kind={kind} の記録に {f[name]} が無い試行がある"
        out[k + "_mean"] = float(statistics.fmean(vals))
        out[k + "_last"] = vals[-1]
    return out, "ok"


def ledger_rows(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def compute(run, absent_basis):
    t0 = time.monotonic()
    rd, seed = Path(run["run_dir"]), run["seed"]
    flag = load_json(rd / "flag.json") if (rd / "flag.json").exists() else {}
    led = one((rd, f"ledgers/cells/*/seed{seed:03d}.jsonl.gz"))
    cf, csrc, _ = candidate_file(run)
    shop = one((rd, f"side/*/seed{seed:03d}.shop.jsonl"))
    checks = Counter()
    sealkeys, by_time = set(), defaultdict(list)
    if cf is not None and shop is not None:
        for line in open(shop, encoding="utf-8"):
            e = json.loads(line)
            if e.get("which") == "sig":
                sealkeys.add((e["R"], e["reg"], e["slot"]))
                by_time[e["trial"]].append(e)
    elif cf is not None:
        checks["shop.jsonl が無い（シールの席は数えない）"] += 1
    expected = {}
    cands = gzip.open(cf, "rt", encoding="utf-8") if cf is not None else None
    counts = Counter()
    seals = Counter()
    eff = Counter()            # 開示のあった試行での、候補の記録からの数（手間の列）
    disclosed = 0
    no_fired = 0
    n = 0
    for row in ledger_rows(led):
        if row.get("record_type", "trial") != "trial":
            continue
        n += 1
        t = row["prediction_order"]
        hit = bool(row["hit"])
        edge = row["predicted_edge"]
        outcome = "correct" if hit else "silent" if edge is None else "wrong"
        d = DAY.get(row.get("shop_cue"), "なし")
        door = bool(row.get("held_out_is_door"))
        ff = row.get("f_fired")
        if ff is None:
            no_fired += 1
        disclosed += bool(ff)
        extra = []
        sel_label = None
        kind = None
        if cands is not None:
            cr = json.loads(next(cands))
            if cr["trial"] != t:
                raise RuntimeError(f"候補の記録の試行 {cr['trial']} と台帳の試行 {t} が違う：{rd}")
            if cr["original_hit"] != hit:
                checks["候補の記録と台帳の当たりが違う"] += 1
            if (edge is None) != ("abstain_reason" in cr["prediction"]):
                checks["候補の記録と台帳の答えの有無が違う"] += 1
            capable = cr["correct_gate_passed"] if absent_basis == "gate" else cr["any_correct"]
            if ff:
                for c in cr["candidates"]:
                    if c["gate_passed"]:
                        eff["gate_FH"] += sum(x["state"] in ("F", "H") for x in c["slots"])
                R = row.get("R_used")
                su = [c for c in cr["candidates"] if c["R"] == R] if R is not None else []
                if su:
                    nf = sum(x["state"] == "F" for x in su[0]["slots"])
                    nh = sum(x["state"] == "H" for x in su[0]["slots"])
                    eff["selected_FH"] += nf + nh
                    eff["selected_reruns"] += 2 * nf + nh
                elif R is not None:
                    checks["開示の試行の R_used が候補の記録に無い"] += 1
            if outcome == "wrong":
                kind = "selection_error" if cr["correct_gate_passed"] else "distinction_loss"
                extra.append(kind)
                sel = [c for c in cr["candidates"] if c["selected"]]
                if len(sel) == 1:
                    if sel[0]["R"] != row.get("R_used"):
                        checks["選ばれた定義が台帳の R_used と違う"] += 1
                    seats = seal_seats(sel[0], sealkeys)
                    for x in seats:
                        checks["シールの席の状態の突き合わせ"] += 1
                        if expected.get((sel[0]["R"], sel[0]["born_trial"], x["slot"])) != x["state"]:
                            checks["シールの席の状態が shop.jsonl の出来事と違う"] += 1
                    sel_label = seal_label(seats)
                else:
                    sel_label = "選択なし" if not sel else "選択が二つ以上"
            if not capable:
                extra.append("absent")
                if outcome == "silent":
                    extra.append("absent_silent")
                if outcome == "correct":
                    checks["正解なのに正答できる定義が無い"] += 1
            elif outcome == "silent":
                extra.append("silent_capable")
            for e in by_time.get(t, []):
                key = (e["R"], e["reg"], e["slot"])
                if e["to"] == "定義ごと消えた":
                    expected.pop(key, None)
                else:
                    expected[key] = e["to"]
        for scope in ("全課題",) + (("ドア課題",) if door else ()):
            for dd in (d, "全日"):
                counts[(scope, dd, "tasks")] += 1
                counts[(scope, dd, outcome)] += 1
                for k in extra:
                    counts[(scope, dd, k)] += 1
                if sel_label is not None:
                    seals[(scope, dd, kind, sel_label)] += 1
    if cands is not None and next(cands, None) is not None:
        raise RuntimeError(f"候補の記録が台帳より長い：{rd}")
    mem, mem_status = memory_stats(run)
    # 記録の反実仮想の回数（古い版の C＝--cf-learn の side の cflearn.jsonl：開示の試行で薄くした席ごとに一行）
    cfl = one((rd, f"side/*/seed{seed:03d}.cflearn.jsonl"))
    record = None
    if cfl is not None:
        record = {"rows": 0, "reruns": 0, "trials": 0}
        tr = set()
        for line in open(cfl, encoding="utf-8"):
            x = json.loads(line)
            record["rows"] += 1
            record["reruns"] += 2 if x["state"] == "F" else 1
            tr.add(x["trial"])
        record["trials"] = len(tr)
    elapsed = None
    man = rd / "manifest.jsonl"
    if man.exists():
        for line in open(man, encoding="utf-8"):
            if line.strip():
                x = json.loads(line)
                if x.get("seed") in (None, seed) and x.get("elapsed_sec") is not None:
                    elapsed = x["elapsed_sec"]
                    break
    effort = {"disclosed": disclosed if not no_fired else None, "cand": cands is not None, **dict(eff),
              "record": record, "elapsed_sec": elapsed, "elapsed_source": "manifest.jsonl の elapsed_sec" if elapsed is not None else "manifest なし"}
    return {"run_dir": str(rd), "seed": seed, "run_commit": str(flag.get("commit", ""))[:7],
            "flag_shop_world": flag.get("shop_world"), "trials": n,
            "candidates_status": "ok" if cf is not None else NA, "candidates_source": csrc,
            "counts": [[*k, v] for k, v in sorted(counts.items())],
            "seals": [[*k, v] for k, v in sorted(seals.items(), key=str)],
            "memory": mem, "memory_status": mem_status, "effort": effort, "checks": dict(checks),
            "computed_at": datetime.now().isoformat(timespec="seconds"), "wall_seconds": round(time.monotonic() - t0, 2)}


def cached_or_compute(args):
    run, absent_basis, redo, cache_dir = args
    key = cache_key(run, absent_basis)
    cp = Path(cache_dir) / (hashlib.sha1(run["run_dir"].encode()).hexdigest()[:16] + ".json")
    if cp.exists() and not redo:
        c = load_json(cp)
        if c.get("key") == key:
            return c["result"], False
    res = compute(run, absent_basis)
    cp.parent.mkdir(parents=True, exist_ok=True)
    tmp = cp.with_suffix(".tmp")
    tmp.write_text(json.dumps({"key": key, "result": res}, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, cp)
    return res, True


# ---------------------------------------------------------------- 表

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    os.replace(tmp, path)


def fmt(x, nd=6):
    if x is None or x == NA:
        return NA
    if isinstance(x, float):
        if math.isinf(x):
            return "inf"
        if math.isnan(x):
            return NA
        return f"{x:.{nd}f}".rstrip("0").rstrip(".") if abs(x) < 1e12 else str(x)
    return x


def compact(counter):
    return ";".join(f"{k}:{v}" for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))


def build_cells(runs, results):
    """(config, world, seed) → 一本の表（cells[(scope, day)] の数、記憶、候補の有無）"""
    table = {}
    for run, res in zip(runs, results):
        c = defaultdict(int)
        for s, d, k, v in res["counts"]:
            c[(s, d, k)] = v
        seals = defaultdict(Counter)
        for s, d, kind, lab, v in res["seals"]:
            seals[(s, d, kind)][lab] += v
        key = (run["config"], run["world"], run["seed"])
        if key in table:
            raise SystemExit(f"★ 同じ構成・世界・種が二本ある：{key}：{table[key]['run']['run_dir']} と {run['run_dir']}")
        table[key] = {"run": run, "res": res, "c": c, "seals": seals, "cand": res["candidates_status"] == "ok"}
    return table


PER_RUN_FIELDS = (["config", "lambda", "world", "seed", "arm", "run_commit", "scope", "day", *COUNT_KEYS]
                  + [f"rate_{k}" for k in RATE_KEYS] + list(MEM_KEYS)
                  + ["selerr_selected_seal_states", "distloss_selected_seal_states",
                     "p_selected_mean", "p_mixture_mean", "prob_approx", "prob_status",
                     "candidates_status", "candidates_source", "memory_status", "run_dir"])


def per_run_rows(table, order):
    rows = []
    for key in sorted(table, key=lambda k: (order.get(k[0], 999), k[0], k[1], k[2])):
        t = table[key]
        run, res, c = t["run"], t["res"], t["c"]
        mem = res["memory"] or {}
        for scope in SCOPES:
            for day in DAYS:
                tasks = c[(scope, day, "tasks")]
                r = {"config": run["config"], "lambda": run["lambda"], "world": run["world"], "seed": run["seed"],
                     "arm": run["arm"], "run_commit": res["run_commit"], "scope": scope, "day": day, "tasks": tasks,
                     "candidates_status": res["candidates_status"], "candidates_source": res["candidates_source"],
                     "memory_status": res["memory_status"], "run_dir": run["run_dir"]}
                for k in OUTCOMES + CAND_KEYS:
                    r[k] = c[(scope, day, k)] if (k in OUTCOMES or t["cand"]) else NA
                for k in RATE_KEYS:
                    r[f"rate_{k}"] = fmt(r[k] / tasks) if tasks and r[k] != NA else NA
                for k in MEM_KEYS:
                    r[k] = fmt(mem.get(k)) if mem else NA
                if t["cand"]:
                    r["selerr_selected_seal_states"] = compact(t["seals"][(scope, day, "selection_error")])
                    r["distloss_selected_seal_states"] = compact(t["seals"][(scope, day, "distinction_loss")])
                else:
                    r["selerr_selected_seal_states"] = r["distloss_selected_seal_states"] = NA
                # 確率で答えた場合の正答率：記録に P・π があるときだけ。今は計算する記録の形が無いので空欄と理由
                r["p_selected_mean"] = r["p_mixture_mean"] = ""
                r["prob_approx"] = "近似" if run["prob_approx"] else ""
                r["prob_status"] = (run["prob"] or {}).get("short", "空欄：記録に P・π の欄が無い（configs.json の prob が未設定）")
                rows.append(r)
    return rows


EFFORT_FIELDS = ["config", "lambda", "world", "seed", "run_commit", "effort_rule", "disclosed_trials", "cf_evals_total",
                 "cf_evals_per_disclosed", "cf_evals_source", "cf_reruns_per_disclosed", "cand_count_per_disclosed",
                 "elapsed_sec", "elapsed_source"]
EFFORT_SOURCE = {"none": "反実仮想の評価が無い構成（規則で 0）",
                 "gate_FH": "候補の記録から：開示の試行で、門を通った全候補の F・H の席の数",
                 "selected_FH": "候補の記録から：開示の試行で、選ばれた定義（台帳の R_used）の F・H の席の数"}


def effort_one(t):
    """一本の手間の列。規則は configs.json の effort（none・gate_FH・selected_FH）。"""
    run, res = t["run"], t["res"]
    e = res.get("effort") or {}
    rule = run["effort"]
    r = {"config": run["config"], "lambda": run["lambda"], "world": run["world"], "seed": run["seed"],
         "run_commit": res["run_commit"], "effort_rule": rule, "elapsed_sec": e.get("elapsed_sec", NA),
         "elapsed_source": e.get("elapsed_source", "")}
    dis = e.get("disclosed")
    r["disclosed_trials"] = NA if dis is None else dis
    total, src, reruns, cand = NA, "", "", ""
    if rule == "none":
        total, src = 0, EFFORT_SOURCE["none"]
    elif rule in ("gate_FH", "selected_FH"):
        if e.get("cand"):
            cand = e.get(rule, 0)
        rec = e.get("record")
        if rule == "selected_FH" and rec is not None:
            total, src = rec["rows"], "記録から：side の cflearn.jsonl の行（開示の試行で薄くした席ごとに一行）"
            reruns = rec["reruns"]
        elif e.get("cand"):
            total, src = cand, EFFORT_SOURCE[rule]
            if rule == "selected_FH":
                reruns = e.get("selected_reruns", 0)
        else:
            src = "候補の記録が無い（NA）"
    else:
        src = "configs.json の effort が未設定（NA）"
    r["cf_evals_total"] = total
    r["cf_evals_source"] = src
    ok = dis not in (None, 0)
    r["cf_evals_per_disclosed"] = fmt(total / dis) if ok and total != NA else (NA if total == NA or dis is None else 0)
    r["cf_reruns_per_disclosed"] = fmt(reruns / dis) if ok and reruns != "" else ""
    r["cand_count_per_disclosed"] = fmt(cand / dis) if ok and cand != "" else ""
    return r


def effort_rows(table, order):
    rows = []
    groups = defaultdict(list)
    for k in sorted(table, key=lambda k: (order.get(k[0], 999), k[0], k[1], k[2])):
        r = effort_one(table[k])
        rows.append(r)
        groups[(k[0], k[1])].append(r)
    for (cfg, w), rs in groups.items():
        def mean(key):
            v = [float(x[key]) for x in rs if x[key] not in (NA, "", None)]
            return fmt(statistics.fmean(v)) if v and len(v) == len(rs) else NA
        rows.append({"config": cfg, "lambda": rs[0]["lambda"], "world": w, "seed": "種の平均", "run_commit": "",
                     "effort_rule": rs[0]["effort_rule"], "disclosed_trials": mean("disclosed_trials"),
                     "cf_evals_total": mean("cf_evals_total"), "cf_evals_per_disclosed": mean("cf_evals_per_disclosed"),
                     "cf_evals_source": f"{len(rs)} 本の平均", "cf_reruns_per_disclosed": mean("cf_reruns_per_disclosed") if rs[0]["cf_reruns_per_disclosed"] != "" else "",
                     "cand_count_per_disclosed": mean("cand_count_per_disclosed") if rs[0]["cand_count_per_disclosed"] != "" else "",
                     "elapsed_sec": mean("elapsed_sec"), "elapsed_source": ""})
    return rows


def seal_rows(table, order):
    rows = []
    for key in sorted(table, key=lambda k: (order.get(k[0], 999), k[0], k[1], k[2])):
        t = table[key]
        if not t["cand"]:
            continue
        for (scope, day, kind), cnt in sorted(t["seals"].items()):
            for lab, v in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0])):
                rows.append({"config": key[0], "lambda": t["run"]["lambda"], "world": key[1], "seed": key[2], "scope": scope,
                             "day": day, "error_kind": {"selection_error": "選び間違い", "distinction_loss": "区別の喪失"}[kind],
                             "selected_seal_class": lab, "selected_seal_state": "+".join(re.findall(r"[FHU](?=\[|\+|$)", lab)) or lab,
                             "trials": v})
    return rows


def resample_idx(rng_seed, n, B):
    """種の選び直し（重複あり）の番号。B 回 × n。固定の乱数の種（random.Random）。"""
    rng = random.Random(rng_seed)
    return [[rng.randrange(n) for _ in range(n)] for _ in range(B)]


def boot_ratio(num, den, num_t, den_t, idx):
    """種の選び直しで、(Σnum/Σnum_t)/(Σden/Σden_t) を計算する。"""
    out = []
    for ix in idx:
        out.append(ratio_of(sum(num[i] for i in ix), sum(num_t[i] for i in ix),
                            sum(den[i] for i in ix), sum(den_t[i] for i in ix)))
    return out


def ratio_of(a, at, b, bt):
    if at == 0 or bt == 0:
        return float("nan")
    ra, rb = a / at, b / bt
    if rb == 0:
        return float("inf") if ra > 0 else float("nan")
    return ra / rb


PAIR_FIELDS = ["pair_group", "num_config", "den_config", "world", "scope", "day", "metric", "n_seeds", "seeds",
               "num_total", "den_total", "num_tasks", "den_tasks", "ratio", "seeds_num_more", "seeds_num_less", "seeds_equal",
               "ci95_lo", "ci95_hi", "ci_contains_1", "boot_resamples", "boot_undefined", "rng_seed", "note"]


def expand_pairs(pairs_cfg, configs_present, family):
    """"*" は、相手と同じ family（configs.json の群の family。版の違う構成を混ぜないため）の、相手以外の全部の構成。"""
    out = []
    for p in pairs_cfg["pairs"]:
        nums = ([c for c in configs_present if c != p["den"] and family.get(c) == family.get(p["den"])]
                if p["num"] == "*" else [p["num"]])
        dens = ([c for c in configs_present if c != p["num"] and family.get(c) == family.get(p["num"])]
                if p["den"] == "*" else [p["den"]])
        for a in nums:
            for b in dens:
                if a != b:
                    out.append((p.get("group", ""), a, b))
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def pair_rows(table, pairs_cfg, metrics_main):
    B = int(pairs_cfg.get("resamples", 4000))
    rng_seed = int(pairs_cfg.get("rng_seed", 20261007))
    configs_present = sorted({k[0] for k in table})
    family = {k[0]: t["run"]["family"] for k, t in table.items()}
    worlds = sorted({k[1] for k in table})
    rows, skipped = [], []
    for group, a, b in expand_pairs(pairs_cfg, configs_present, family):
        for w in worlds:
            sa = {k[2] for k in table if k[0] == a and k[1] == w}
            sb = {k[2] for k in table if k[0] == b and k[1] == w}
            seeds = sorted(sa & sb)
            if not seeds:
                if sa and sb:
                    skipped.append(f"{a} / {b} 世界{w}：同じ種が無い（{a} {sorted(sa)}、{b} {sorted(sb)}）")
                continue
            # 同じ組・世界では、全部の欄で同じ選び直しを使う（固定の乱数の種）
            idx_all = resample_idx(rng_seed, len(seeds), B)
            for scope in SCOPES:
                for day in DAYS:
                    for m in metrics_main:
                        need_cand = m in CAND_KEYS
                        sd = [s for s in seeds if not need_cand or (table[(a, w, s)]["cand"] and table[(b, w, s)]["cand"])]
                        r = {"pair_group": group, "num_config": a, "den_config": b, "world": w, "scope": scope, "day": day,
                             "metric": f"rate_{m}", "rng_seed": rng_seed}
                        if not sd:
                            rows.append({**r, "n_seeds": 0, "note": "候補の記録が両方にある種が無い（NA）"})
                            continue
                        if len(sd) != len(seeds):
                            idx = resample_idx(rng_seed, len(sd), B)
                            r["note"] = f"候補の記録が無い種を除いた（{len(seeds) - len(sd)} 本）"
                        else:
                            idx = idx_all
                        ca = [table[(a, w, s)]["c"] for s in sd]
                        cb = [table[(b, w, s)]["c"] for s in sd]
                        num = [c[(scope, day, m)] for c in ca]
                        den = [c[(scope, day, m)] for c in cb]
                        nt = [c[(scope, day, "tasks")] for c in ca]
                        dt = [c[(scope, day, "tasks")] for c in cb]
                        more = sum(1 for i in range(len(sd)) if num[i] * dt[i] > den[i] * nt[i])
                        less = sum(1 for i in range(len(sd)) if num[i] * dt[i] < den[i] * nt[i])
                        rows.append({**r, **pair_stats(num, den, nt, dt, idx, sd, more, less, B)})
            # 記憶のビット（一本ごとの全試行の平均）の比
            sd = [s for s in seeds if table[(a, w, s)]["res"]["memory"] and table[(b, w, s)]["res"]["memory"]]
            r = {"pair_group": group, "num_config": a, "den_config": b, "world": w, "scope": "", "day": "",
                 "metric": "mem_bits_mean", "rng_seed": rng_seed}
            if not sd:
                rows.append({**r, "n_seeds": 0, "note": "記憶の記録が両方にある種が無い（NA）"})
                continue
            idx = idx_all if len(sd) == len(seeds) else resample_idx(rng_seed, len(sd), B)
            num = [table[(a, w, s)]["res"]["memory"]["mem_bits_mean"] for s in sd]
            den = [table[(b, w, s)]["res"]["memory"]["mem_bits_mean"] for s in sd]
            one_ = [1] * len(sd)
            more = sum(x > y for x, y in zip(num, den))
            less = sum(x < y for x, y in zip(num, den))
            st = pair_stats(num, den, one_, one_, idx, sd, more, less, B)
            st["num_tasks"] = st["den_tasks"] = ""
            rows.append({**r, **st})
    return rows, skipped


def pair_stats(num, den, nt, dt, idx, sd, more, less, B):
    ratio = ratio_of(sum(num), sum(nt), sum(den), sum(dt))
    bs = boot_ratio(num, den, nt, dt, idx)
    defined = [x for x in bs if not math.isnan(x)]
    und = len(bs) - len(defined)
    if defined:
        v = sorted(defined)          # inf は後ろに並ぶ
        lo = float(v[int(math.floor(0.025 * len(v)))])
        hi = float(v[int(math.ceil(0.975 * len(v))) - 1])
        contains = "yes" if lo <= 1 <= hi else "no"
    else:
        lo = hi = float("nan")
        contains = NA
    return {"n_seeds": len(sd), "seeds": ",".join(map(str, sd)), "num_total": fmt(float(sum(num))),
            "den_total": fmt(float(sum(den))), "num_tasks": int(sum(nt)), "den_tasks": int(sum(dt)),
            "ratio": fmt(ratio), "seeds_num_more": more, "seeds_num_less": less, "seeds_equal": len(sd) - more - less,
            "ci95_lo": fmt(lo), "ci95_hi": fmt(hi), "ci_contains_1": contains, "boot_resamples": B, "boot_undefined": und}


MB_FIELDS = ["config", "lambda", "world", "scope", "day", "n_seeds", "seeds", "mem_bits_mean", "mem_bits_mean_sd",
             "mem_bits_last_mean", "defs_mean", "F_mean", "H_mean", "U_mean",
             "n_seeds_with_candidates", "rate_selection_error_mean", "rate_selection_error_sd",
             "rate_absent_mean", "rate_absent_sd", "rate_distinction_loss_mean", "rate_wrong_mean", "rate_silent_mean"]


def memory_rows(table, order):
    rows = []
    groups = defaultdict(list)
    for k, t in table.items():
        groups[(k[0], k[1])].append(t)
    for (cfg, w), ts in sorted(groups.items(), key=lambda kv: (kv[0][1], order.get(kv[0][0], 999), kv[0][0])):
        ts = sorted(ts, key=lambda t: t["run"]["seed"])
        mems = [t["res"]["memory"] for t in ts if t["res"]["memory"]]
        for scope in SCOPES:
            for day in DAYS:
                r = {"config": cfg, "lambda": ts[0]["run"]["lambda"], "world": w, "scope": scope, "day": day,
                     "n_seeds": len(ts), "seeds": ",".join(str(t["run"]["seed"]) for t in ts)}
                for k, src in (("mem_bits_mean", "mem_bits_mean"), ("mem_bits_last_mean", "mem_bits_last"),
                               ("defs_mean", "defs_mean"), ("F_mean", "F_mean"), ("H_mean", "H_mean"), ("U_mean", "U_mean")):
                    r[k] = fmt(float(statistics.fmean([m[src] for m in mems]))) if mems else NA
                r["mem_bits_mean_sd"] = fmt(float(statistics.stdev([m["mem_bits_mean"] for m in mems]))) if len(mems) > 1 else NA

                def rate(t, m):
                    tasks = t["c"][(scope, day, "tasks")]
                    return t["c"][(scope, day, m)] / tasks if tasks else None
                withc = [t for t in ts if t["cand"]]
                r["n_seeds_with_candidates"] = len(withc)
                for m in ("selection_error", "absent", "distinction_loss"):
                    v = [rate(t, m) for t in withc]
                    v = [x for x in v if x is not None]
                    r[f"rate_{m}_mean"] = fmt(float(statistics.fmean(v))) if v else NA
                    if m != "distinction_loss":
                        r[f"rate_{m}_sd"] = fmt(float(statistics.stdev(v))) if len(v) > 1 else NA
                for m in ("wrong", "silent"):
                    v = [x for x in (rate(t, m) for t in ts) if x is not None]
                    r[f"rate_{m}_mean"] = fmt(float(statistics.fmean(v))) if v else NA
                rows.append(r)
    return rows


# ---------------------------------------------------------------- 本体

def main():
    global OUT, CACHE
    ap = argparse.ArgumentParser(description="表層の解析の表を作る（読むだけ）")
    ap.add_argument("--configs", default=str(BASE / "configs.json"))
    ap.add_argument("--pairs", default=str(BASE / "pairs.json"))
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--redo", action="store_true", help="キャッシュを使わず全部を読み直す")
    ap.add_argument("--only", default="", help="構成名をカンマで（表もその構成だけになる）")
    ap.add_argument("--out", default=str(BASE / "out"), help="表の置き場（試し用）")
    ap.add_argument("--cache", default=str(BASE / "cache"), help="一本ごとの結果の置き場（試し用）")
    a = ap.parse_args()
    OUT, CACHE = Path(a.out), Path(a.cache)
    jobs = max(1, min(4, a.jobs))          # 4 過程まで
    t0 = time.monotonic()
    cfg = load_json(a.configs)
    pairs_cfg = load_json(a.pairs)
    absent_basis = cfg.get("absent_basis", "gate")
    assert absent_basis in ("gate", "any"), absent_basis
    runs, notes = discover(cfg)
    if a.only:
        keep = set(a.only.split(","))
        runs = [r for r in runs if r["config"] in keep]
    order = {c: i for i, c in enumerate(cfg.get("order", []))}
    results, fresh = [], 0
    if runs:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            for res, new in ex.map(cached_or_compute, [(r, absent_basis, a.redo, str(CACHE)) for r in runs]):
                results.append(res)
                fresh += new
    checks = Counter()
    for run, res in zip(runs, results):
        checks.update(res["checks"])
        if res["flag_shop_world"] is not None and res["flag_shop_world"] != run["world"]:
            checks["configs.json の世界と flag.json の shop_world が違う"] += 1
    table = build_cells(runs, results)
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "per_run.csv", per_run_rows(table, order), PER_RUN_FIELDS)
    write_csv(OUT / "seal_states.csv", seal_rows(table, order),
              ["config", "lambda", "world", "seed", "scope", "day", "error_kind", "selected_seal_class", "selected_seal_state", "trials"])
    prow, skipped = pair_rows(table, pairs_cfg, pairs_cfg.get("metrics", list(RATE_KEYS)))
    write_csv(OUT / "pairs.csv", prow, PAIR_FIELDS)
    write_csv(OUT / "memory_bits_vs_errors.csv", memory_rows(table, order), MB_FIELDS)
    erows = effort_rows(table, order)
    write_csv(OUT / "effort.csv", erows, EFFORT_FIELDS)
    for r in erows:
        if r["seed"] != "種の平均" and r["cand_count_per_disclosed"] not in ("", NA) and r["cf_evals_source"].startswith("記録から") \
                and r["cand_count_per_disclosed"] != r["cf_evals_per_disclosed"]:
            checks["手間：記録の回数と候補の記録からの数が違う本"] += 1
        elif r["seed"] != "種の平均" and r["cf_evals_source"].startswith("記録から") and r["cand_count_per_disclosed"] not in ("", NA):
            checks["手間：記録の回数と候補の記録からの数の突き合わせ（本）"] += 1
    write_csv(OUT / "columns.csv", [{"table": tb, "column": c, "説明": d} for tb, c, d in COLUMNS], ["table", "column", "説明"])
    per_cfg = Counter((r["config"], r["world"]) for r in runs)
    na_cand = Counter((r["config"], r["world"]) for r, res in zip(runs, results) if res["candidates_status"] != "ok")
    na_mem = Counter((r["config"], r["world"]) for r, res in zip(runs, results) if not res["memory"])
    meta = {
        "作った時刻": datetime.now().isoformat(timespec="seconds"),
        "本数": len(runs), "今回読み直した本": fresh, "時間_秒": round(time.monotonic() - t0, 1),
        "構成・世界ごとの本数": {f"{c} 世界{w}": n for (c, w), n in sorted(per_cfg.items())},
        "候補の記録が無い本（選び間違い・区別の喪失・不在・シールは NA）": {f"{c} 世界{w}": n for (c, w), n in sorted(na_cand.items())},
        "記憶の記録が無い本（記憶のビット・F/H/U は NA）": {f"{c} 世界{w}": n for (c, w), n in sorted(na_mem.items())},
        "確かめ": dict(checks), "飛ばした群": notes, "比べられなかった組": skipped,
        "absent_basis": absent_basis,
        "定義": {
            "正解・誤答・棄権": "台帳の hit、答えあり・外れ、答えなし（predicted_edge が null）",
            "例外の日・通常の日・ドア課題": "台帳の shop_cue（e・n）、held_out_is_door。全日＝例外＋通常",
            "選び間違い": "誤答のうち、門を通って正しく答える定義があった件（候補の記録の correct_gate_passed）",
            "区別の喪失": "誤答のうち、門を通って正しく答える定義が無かった件",
            "正答できる定義の不在": ("課題のうち、門を通って正しく答える定義が無かった件（棄権を含む。正解では起きない）。"
                              "absent＝distinction_loss＋absent_silent" if absent_basis == "gate" else
                              "課題のうち、正しく答える候補が一つも無かった件（門を見ない、any_correct）"),
            "silent_capable": "棄権のうち、門を通って正しく答える定義があった件",
            "記憶のビット": MEM_DEF,
            "F/H/U・定義の数": "同じ v39 の記録の F・H・U（席の数）・defs。_mean は全試行の平均、_last は最後",
            "選ばれた定義のシール": "誤答で selected の候補の、シールの席（shop.jsonl の which=sig）の 状態[名] を + でつなぐ",
            "率": "その範囲・日の課題の数を分母（全課題を分母とする率は scope=全課題）",
            "対の比": ("ratio＝(Σ分子の構成の数/Σその課題の数)÷(Σ分母の構成の数/Σその課題の数)。同じ世界の、両方にある種だけ。"
                     "seeds_num_more/less は種ごとの率の大小。95% の範囲は種を重複ありで選び直した 4,000 回の比の"
                     "2.5%・97.5% の順位の値（比が 0/0 の回は除いて boot_undefined に数え、分母だけ 0 の回は inf）。"
                     "同じ組・世界では全部の欄に同じ選び直しを使う（Python の random.Random(rng_seed)）"),
            "手間の列（effort.csv）": EFFORT_DEF,
            "確率で答えた場合の正答率": PROB_DEF,
        },
        "表の欄の説明": "columns.csv",
        "確率で答えた場合の正答率が空欄の理由": {f"{r['config']} 世界{r['world']}": (r["prob"] or {}).get("status", "configs.json の prob が未設定")
                                       for r in runs},
    }
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{datetime.now():%F %T} 本 {len(runs)}（読み直し {fresh}）、{meta['時間_秒']} 秒、確かめ {dict(checks)}", flush=True)
    for n in notes + skipped:
        print("  " + n)
    return fresh


if __name__ == "__main__":
    sys.exit(0 if main() is not None else 1)
