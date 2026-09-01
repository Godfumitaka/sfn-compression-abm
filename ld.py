#!/usr/bin/env python3
"""
ld.py — L 切り離し実験を θ′ × verbatim_theta の 4×4 面で読む

作成 2026-08-30 夜

★ なぜ要るか
  mlive.py / checks3.py は θ′ でしか集約しない。
  analysis_ld の 16 セルは θ′ 4 水準 × vt 4 水準なので、
  ★ それらの表の各 θ′ 列は vt 4 水準を混ぜた平均 になっている。
  → 本実験の問い（θ′ の効きは削除機構か枚の時計か）に答えられない。

★ 再解析は不要
  per_def.jsonl の "cell" 欄がセル名を持っており、
  非対角セルは f0.0000_th0.0410_vt0.1432_all の形で vt を含む。
  対角セル（vt = θ′）は vt を含まない旧形式なので、θ′ を vt とみなす。

★ 読み方（結果を見る前に置く）
  行方向（vt を固定して θ′ を動かす）に効きが残る
    → 削除機構が効いている。機構主張は「削除閾値」で書ける
  列方向（θ′ を固定して vt を動かす）にだけ効きが出る
    → ★ θ′ は枚の寿命として効いていた。機構主張を全面的に書き直す
  両方に出る  → 二つの経路が併存する。両方書く

使い方
  python3 ld.py --per-def analysis_ld/per_def.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

KEEP = ("cell", "f", "theta_prime", "adoptions", "m_live_final", "m_alloc",
        "born", "horizon", "n_changes", "stage2_b", "E3_C", "change_times",
        "OA_applied", "OA_gstar", "OA_gstar_frac", "thin")

CELL_RE = re.compile(r"^f(?P<f>[\d.]+)_th(?P<th>[\d.]+)(?:_vt(?P<vt>[\d.]+))?_(?P<scope>.+)$")
MYTH_M = 2          # U-071（確定 2026-08-21）


def load(path: Path):
    rows = []
    with open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            row = {k: record.get(k) for k in KEEP}
            match = CELL_RE.fullmatch(row.get("cell") or "")
            if match is None:
                row["vt"] = None
            else:
                raw = match.group("vt")
                # ★ 対角セルは vt を名前に持たない（cell_name の後方互換規則）
                row["vt"] = float(raw) if raw is not None else float(match.group("th"))
            rows.append(row)
    return rows


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.fmean(values) if values else None


def fmt(value, width=12, digits=4):
    return "%*s" % (width, "—") if value is None else "%*.*f" % (width, digits, value)


def face(rows, thetas, vts, metric, title, note=""):
    """行 = vt（枚の寿命を決める閾値）／ 列 = θ′（構成素の削除閾値）"""
    print("\n### %s" % title)
    if note:
        print("    %s" % note)
    print("  %-14s%s%14s" % ("vt ＼ θ′", "".join("%12.4f" % t for t in thetas), "行の幅"))
    row_ranges = []
    grid = {}
    for vt in vts:
        cells = []
        for theta in thetas:
            picked = [r for r in rows if r["vt"] == vt and r["theta_prime"] == theta]
            value = metric(picked)
            grid[(vt, theta)] = value
            cells.append(value)
        valid = [c for c in cells if c is not None]
        span = (max(valid) - min(valid)) if len(valid) > 1 else None
        if span is not None:
            row_ranges.append(span)
        print("  vt=%-11.4f%s%s" % (vt, "".join(fmt(c) for c in cells), fmt(span, 14)))

    col_ranges = []
    cells = []
    for theta in thetas:
        column = [grid[(vt, theta)] for vt in vts if grid.get((vt, theta)) is not None]
        span = (max(column) - min(column)) if len(column) > 1 else None
        if span is not None:
            col_ranges.append(span)
        cells.append(span)
    print("  %-14s%s" % ("列の幅", "".join(fmt(c) for c in cells)))
    print("  %-14s★ θ′ 方向（行内）の幅の平均 %.4f   ／   ★ vt 方向（列内）の幅の平均 %.4f"
          % ("", statistics.fmean(row_ranges) if row_ranges else 0.0,
             statistics.fmean(col_ranges) if col_ranges else 0.0))

    diagonal = [grid.get((t, t)) for t in thetas]
    print("  %-14s%s   ★ 本走行に対応する線" % ("対角（vt=θ′）", "".join(fmt(c) for c in diagonal)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-def", required=True)
    args = parser.parse_args()

    rows = load(Path(args.per_def))
    thetas = sorted({r["theta_prime"] for r in rows if r["theta_prime"] is not None})
    vts = sorted({r["vt"] for r in rows if r["vt"] is not None})

    print("読み込み  %s（def %d 行）" % (args.per_def, len(rows)))
    print("θ′ の水準 %s" % thetas)
    print("vt の水準 %s" % vts)
    counts = defaultdict(int)
    for r in rows:
        counts[(r["vt"], r["theta_prime"])] += 1
    print("セルあたりの def 数  最小 %d ／ 最大 %d ／ セル数 %d"
          % (min(counts.values()), max(counts.values()), len(counts)))
    print("★ θ′ ＝ 構成素の削除閾値 ／ vt ＝ 逐語痕跡の削除閾値（枚の寿命 floor(vt⁻²)+1 を決める）")

    print("\n" + "=" * 100)
    print("★ L 切り離し — θ′ × verbatim_theta の面")
    print("=" * 100)

    face(rows, thetas, vts,
         lambda p: mean([r["m_live_final"] for r in p]),
         "m_live 平均（★ 主指標。E3・τ_settle・段階2 に非依存）",
         "本走行（vt=θ′ に固定）では 4.038 → 3.402、幅 0.636 だった")

    face(rows, thetas, vts,
         lambda p: (sum(1 for r in p if r["m_live_final"] is not None
                        and r["m_live_final"] <= MYTH_M) / len(p)) if p else None,
         "★ 神話率（m_live ≤ %d・def 数）" % MYTH_M,
         "本走行では 0.0649 → 0.1936、3.0 倍だった")

    def myth_weighted(picked):
        used = [r for r in picked if r.get("adoptions")]
        total = sum(r["adoptions"] for r in used)
        if not total:
            return None
        return sum(r["adoptions"] for r in used
                   if r["m_live_final"] is not None and r["m_live_final"] <= MYTH_M) / total

    face(rows, thetas, vts, myth_weighted,
         "神話率（m_live ≤ %d・採択加重）" % MYTH_M)

    face(rows, thetas, vts,
         lambda p: mean([r["m_alloc"] for r in p]),
         "m_alloc 平均（★ 積まれた構成素の総数。出生側）",
         "本走行では 5.714 → 5.184 だった")

    face(rows, thetas, vts,
         lambda p: mean([(r["m_alloc"] - r["m_live_final"])
                         for r in p if r.get("m_alloc") is not None
                         and r.get("m_live_final") is not None]),
         "削除本数（m_alloc − m_live）",
         "本走行では 1.50〜1.99 で θ′ に応答しなかった")

    face(rows, thetas, vts,
         lambda p: mean([r["OA_applied"] for r in p]),
         "OA_applied（適用の広がり）")

    face(rows, thetas, vts,
         lambda p: mean([r["adoptions"] for r in p]),
         "def あたりの採択回数")

    print("""

★ 判定（2026-08-30 夜、結果を見る前に置いた基準）

  m_live 平均の面で
    ★ θ′ 方向の幅の平均が vt 方向の 2 倍以上   → 削除機構が主。機構主張はそのまま
    ★ vt 方向の幅の平均が θ′ 方向の 2 倍以上   → ★ 枚の時計が主。機構主張を書き直す
    どちらも 2 倍に届かない                     → 二経路の併存として両方書く

  ★ 対角線の行は本走行と一致するはずである（実データで照合済み：4 組とも sha256 一致）
    ここがずれていれば集約の誤りを疑う
""")


if __name__ == "__main__":
    main()
