"""手順 2 の骨組み：新しい版の仕組みの確認の走行（走行の列 #0）の記録から、無作為の試行（各構成 50 試行以上、
固定した乱数の種）を選び、参照の計算（ref_cstar・ref_delta_r・ref_birth_init・ref_attn_m）でやり直して、
記録値との差の表（CSV）を出す。

いま動くもの：
  --selfcheck-old RUN_DIR   古い版（10cd8bd）の記録 seedNNN.sme.jsonl.gz の sme_result（v39:map_v39 の照合）から、
                            記録された左右の図と選ばれた対応を復元し、ref_cstar.score_fixed（固定した対応の
                            sme2017 の点）が記録の点の和と全バイト近く一致するかを確かめる（記録の読み方と
                            固定対応の採点器の自己点検。C* そのものの点検ではない）。
まだ動かないもの（新しい版の記録の形式が分かってから埋める。TODO の印）：
  --run-dir RUN_DIR --config NAME   C* の S_P・T・Q_P、第二段の Δr、誕生の初期値、注意の m・z・a の照合。

種 21〜40 の出力は読まない（パスに seed021〜seed040 があれば止める）。重い計算は nice -n 15 で走らせる。
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import json
import math
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from refcommon import sme2017, sme2017_blob_sha, SME2017_BLOB  # noqa: E402
from ref_cstar import score_fixed  # noqa: E402

FORBIDDEN = re.compile(r"seed0(2[1-9]|3\d|40)")
SAMPLE_SEED = 20261008
CSV_FIELDS = ["config", "seed", "trial", "item", "R", "seat", "field", "recorded", "reference", "abs_diff",
              "rel_diff", "match", "note"]


def guard(path: str):
    if FORBIDDEN.search(path):
        raise SystemExit(f"種 21〜40 の出力には触れない：{path}")


def iter_jsonl_gz(path):
    guard(path)
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def graph_from_nodes(nodes):
    """記録の left_nodes／right_nodes（smeshared.graph_data の形）から sme2017.Graph をそのまま作る。"""
    out = []
    for n in nodes:
        args = None if n["args"] is None else tuple(n["args"])
        out.append(sme2017.Node(n["key"], n["kind"], frozenset(n["names"]), args if n["kind"] != "entity" else (),
                                n["state"], n.get("ubiquitous", False)))
    return sme2017.Graph(tuple(out))


def row(config, seed, trial, item, R, seat, field, rec, ref, tol=1e-12, note=""):
    if rec is None or ref is None:
        return dict(config=config, seed=seed, trial=trial, item=item, R=R, seat=seat, field=field, recorded=rec,
                    reference=ref, abs_diff="", rel_diff="", match="", note=note or "片方が無い")
    d = abs(rec - ref)
    rel = d / max(abs(rec), abs(ref), 1e-300)
    return dict(config=config, seed=seed, trial=trial, item=item, R=R, seat=seat, field=field, recorded=rec,
                reference=ref, abs_diff=d, rel_diff=rel, match=int(d <= tol or rel <= tol), note=note)


# ---------------------------------------------------------------- 古い版の記録での自己点検
def selfcheck_old(run_dir: str, n: int, out_csv: str):
    files = sorted(glob.glob(os.path.join(run_dir, "**", "seed*.sme.jsonl.gz"), recursive=True))
    files = [f for f in files if not FORBIDDEN.search(f)]
    if not files:
        raise SystemExit("seedNNN.sme.jsonl.gz が無い")
    rng = random.Random(SAMPLE_SEED)
    rows = []
    for path in files:
        seed = int(re.search(r"seed(\d+)\.sme", path).group(1))
        recs = [r for r in iter_jsonl_gz(path) if r.get("kind") == "sme_result" and r.get("caller") == "v39:map_v39"
                and r.get("new_relation_mapping")]
        pick = rng.sample(recs, min(n, len(recs)))
        for r in pick:
            L, R = graph_from_nodes(r["left_nodes"]), graph_from_nodes(r["right_nodes"])
            rec = math.fsum(p[2] + p[3] for p in r["points"])
            try:
                ref, kept = score_fixed(L, R, r["new_relation_mapping"])
                note = "" if len(kept) == len(r["new_relation_mapping"]) else f"残った対 {len(kept)}／{len(r['new_relation_mapping'])}"
            except ValueError as e:
                ref, note = None, f"採点できない：{e}"
            rows.append(row("old-10cd8bd", seed, r.get("trial"), "S_fixed", r["result"][:16], "", "score", rec, ref,
                            tol=1e-9, note=note))
    write_csv(out_csv, rows)
    ok = sum(1 for x in rows if x["match"] == 1)
    print(f"{ok}/{len(rows)} 一致（許容 1e-9）→ {out_csv}")


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ---------------------------------------------------------------- 新しい版の記録（TODO）
class NewRecordAdapter:
    """新しい版の記録を参照の計算の入力へ写す。欄の名前は記録の形式が分かってから埋める。

    必要な欄（spec_notes.md の「記録から要る欄」と同じ）：
    (a) C*：試行・定義 R・照合の呼び出しの種類（予測／E）・左右の図（left_nodes／right_nodes と同じ形）、
        選ばれた対応（関係・物）、各席の照合用の分布 P（又は q_i）、--match-eps・--logp-eps・α、
        記録された S_P・T(d)・T(x)・Q_P、候補の数。                                   TODO(欄の名前)
    (b) 第二段：開示のあった試行の、予測前の全記憶（各定義の席の状態・固定名・履歴の回数・引数・登録の時刻）、
        場面（見えている関係・伏せた位置）、問い（位置・引数・開示された y）、b（席ごとの絞った b）、p̂ の回数、
        注意の a、k2 の鍵、門の τ、損の旗（top1／mixture／alpha）、scope（all／chosen）、
        記録された席ごとの Δr・薄くした後の選んだ定義・門・答え・場合（p̂／複数の席／一つの席）。 TODO
    (c) 誕生：生まれた定義の形、一つ目の材料の席ごとの名前（見えていたか）、二つ目の材料の場面、
        仮の問いの分類（ドア／非ドア）と重み、それまでの問いの回数、記録された初期値（席ごと）。     TODO
    (d) 注意：各候補の m_dj（位置ごと）、z_d、π、p̃、a の更新前後、開示の有無。                 TODO
    """

    def __init__(self, run_dir: str, config: str):
        guard(run_dir)
        self.run_dir, self.config = run_dir, config

    def trials(self):
        """TODO：開示のあった試行の一覧（種, 試行）を返す。"""
        raise NotImplementedError("新しい版の記録の形式を待つ")

    def cstar_items(self, seed, trial):
        """TODO：(Definition, Scene, M, q, recorded) の並び。"""
        raise NotImplementedError

    def stage2_items(self, seed, trial):
        """TODO：(memory, scene, question, Knowledge, Params, scope, recorded_rows)。"""
        raise NotImplementedError

    def birth_items(self, seed, trial):
        """TODO：(memory, shape, names1, material2, Knowledge, Params, asked, is_door, recorded_init)。"""
        raise NotImplementedError

    def attn_items(self, seed, trial):
        """TODO：(z_parts, a_before, dists, y, disclosed, recorded)。"""
        raise NotImplementedError


def compare_new(run_dir: str, config: str, n: int, out_csv: str):
    """各構成 n 試行以上（既定 50）を固定の種で選び、参照でやり直して差の表を書く。"""
    from ref_cstar import cstar_score, T_def, T_scene, Q_P
    from ref_delta_r import delta_r
    from ref_birth_init import birth_init
    from ref_attn_m import grad_mixture, update_a

    ad = NewRecordAdapter(run_dir, config)
    trials = list(ad.trials())
    rng = random.Random(SAMPLE_SEED)
    pick = rng.sample(trials, min(max(n, 50), len(trials)))
    rows = []
    for seed, trial in pick:
        for d, sc, M, q, rec in ad.cstar_items(seed, trial):
            sp = cstar_score(d, sc, M, q)
            rows.append(row(config, seed, trial, "cstar", d.name, "", "S_P", rec.get("S_P"), sp))
            Td, Tx = T_def(d), T_scene(sc)
            rows.append(row(config, seed, trial, "cstar", d.name, "", "T_d", rec.get("T_d"), Td))
            rows.append(row(config, seed, trial, "cstar", d.name, "", "T_x", rec.get("T_x"), Tx))
            rows.append(row(config, seed, trial, "cstar", d.name, "", "Q_P", rec.get("Q_P"), Q_P(sp, Td, Tx)))
        for memory, sc, qn, kn, params, scope, rec_rows in ad.stage2_items(seed, trial):
            res = delta_r(memory, sc, qn, kn, params, scope=scope)
            ref = {(r["R"], r["seat"]): r for r in res["rows"]}
            for key, rr in rec_rows.items():
                rf = ref.get(key)
                rows.append(row(config, seed, trial, "stage2", key[0], key[1], "delta_r", rr.get("delta"),
                                rf["delta"] if rf else None, tol=1e-9,
                                note="" if rf is None else
                                f"選び {rr.get('used_after')}→参照 {rf['used_after']}" if rr.get("used_after") != rf["used_after"] else ""))
                # TODO：符号の違い・保持の判断（ΔR＜λΔC）の逆転を別の欄に
        for args in ad.birth_items(seed, trial):
            *inputs, rec_init = args
            out = birth_init(*inputs[:5], asked=inputs[5], is_door=inputs[6])
            for k, v in rec_init.items():
                rows.append(row(config, seed, trial, "birth", inputs[1].name, k, "init", v, out["init"].get(k), tol=1e-9))
        for z_parts, a0, dists, y, disclosed, rec in ad.attn_items(seed, trial):
            a1 = update_a(a0, grad_mixture(z_parts, a0, dists, y), disclosed=disclosed)
            for k in set(a1) | set(rec.get("a_after", {})):
                rows.append(row(config, seed, trial, "attn", "", k, "a_after", rec.get("a_after", {}).get(k), a1.get(k),
                                tol=1e-9))
    write_csv(out_csv, rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck-old", metavar="RUN_DIR")
    ap.add_argument("--run-dir")
    ap.add_argument("--config", default="")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--out", default=os.path.join(HERE, "diff.csv"))
    a = ap.parse_args()
    if sme2017_blob_sha() != SME2017_BLOB:
        raise SystemExit("sme2017.py の版が違う")
    if a.selfcheck_old:
        guard(a.selfcheck_old)
        selfcheck_old(a.selfcheck_old, a.n, a.out)
    elif a.run_dir:
        compare_new(a.run_dir, a.config, a.n, a.out)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
