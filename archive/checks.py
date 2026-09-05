#!/usr/bin/env python3
"""
checks.py — 走行後の検算 3 件（追加走行なし。per_def.jsonl だけを読む）

作成 2026-08-30 ／ 対象 runs/main_2026-08-31（2,560 走行・def 177,960 本）

★ このスクリプトは新しい判定量を作らない。
  既に per_def.jsonl にある欄を層別・突き合わせるだけである（規範13）。

検算1  U-089 吸収の検査
       推定量 C は「最初に τ_settle 分だけ静かだった時点」で E3 を確定し、以後は
       撤回しない（吸収）。E3 確定の後に構成素が動いた def がどれだけあるかを数える。
       ★ 多ければ「吸収」の仮定が成り立っていない。U-089 の本体がここで閉じる。
       ★ last_change は rev4 で per_def に足した欄。rev3 の出力には無い。

検算2  OA_gstar を m_live で層別する（2026-08-30 宣言の履行）
       gstar は「生存構成素の述語が適用場面の G* に一本でも欠けていたか」なので、
       生存構成素が汎用述語 1 本だけになると構造上ゼロに潰れる。
       ★ m_live=1 の帯で 0 に落ちるかを確認する。

検算3  段階2 到達率を f × θ′ の面で出す（U-093）
       θ′ の上三段で到達率が 100% に近ければ、段階2 による条件づけは判別力を持たない。
       ★ f 軸で動くかは本走行で初めて分かる。

使い方
  python3 checks.py --per-def analysis2/per_def.jsonl
  python3 checks.py --per-def analysis/per_def.jsonl        # rev3 の出力（検算1 は飛ぶ）
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

KEEP = ("f", "theta_prime", "repair_scope", "adoptions", "m_live_final",
        "n_changes", "last_change", "tau_settle", "horizon", "thin",
        "stage2_b", "stage2_a1", "stage2_a2", "E3_C", "E3_A",
        "OA_supply", "OA_applied", "OA_gstar")

HORIZON = 300          # U-016 の報告地平（主）


def load(path: Path):
    rows = []
    with open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            rows.append({k: record.get(k) for k in KEEP})
    return rows


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.fmean(values) if values else None


def fmt(value, width=10, digits=4):
    if value is None:
        return "%*s" % (width, "—")
    return "%*.*f" % (width, digits, value)


# ══════════════════════════════════════════════════════════════
def check1_absorption(rows):
    print("\n" + "=" * 92)
    print("検算1  U-089  吸収の検査 — E3 を確定した後に構成素が動いた def の割合")
    print("=" * 92)

    scored = [r for r in rows
              if r.get("stage2_b") is not None and r.get("E3_C") is not None]
    if not scored:
        print("  ★ 該当なし")
        return
    if all(r.get("last_change") is None for r in scored):
        print("  ★ last_change の欄がありません（rev3 の出力です）")
        print("     rev4 で解析し直すと、この検算ができます")
        return

    def dirty(record):
        last = record.get("last_change")
        return last is not None and last > record["E3_C"]

    print("\n  分母 ＝ 段階2（パターン b）に到達し、E3（推定量 C）が確定した def")
    print("\n  %-10s%12s%12s%14s%12s" % ("θ′", "汚れた割合", "n", "変化の中央値", "τ_settle 中央"))
    for theta in sorted({r["theta_prime"] for r in scored}):
        picked = [r for r in scored if r["theta_prime"] == theta]
        n_dirty = sum(1 for r in picked if dirty(r))
        changes = [r["n_changes"] for r in picked if r.get("n_changes") is not None]
        windows = [r["tau_settle"] for r in picked if r.get("tau_settle")]
        print("  %-10.4f%12.4f%12d%14s%12s"
              % (theta, n_dirty / len(picked), len(picked),
                 "%.1f" % statistics.median(changes) if changes else "—",
                 "%.0f" % statistics.median(windows) if windows else "—"))

    total_dirty = sum(1 for r in scored if dirty(r))
    print("\n  全体  汚れた割合 %.4f（%d / %d）" % (total_dirty / len(scored),
                                                   total_dirty, len(scored)))

    # ★ 事後の感度。主結果を置き換えるものではない
    horizon_ok = [r for r in scored
                  if r.get("horizon") is not None
                  and r["stage2_b"] + HORIZON <= r["horizon"]]
    if horizon_ok:
        clean = sum(1 for r in horizon_ok
                    if r["E3_C"] <= r["stage2_b"] + HORIZON and not dirty(r))
        counted = sum(1 for r in horizon_ok if r["E3_C"] <= r["stage2_b"] + HORIZON)
        print("\n  ★ 事後の感度（主結果を置き換えない）")
        print("     地平 %d で E3 と数えた def のうち、E3 の後に変化が無かったもの" % HORIZON)
        print("     %d / %d = %.4f" % (clean, counted, clean / counted if counted else 0.0))

    print("""
  読み方
    汚れた割合が小さい   吸収の仮定は実質的に成り立っている。U-089 は C のままで閉じる
    汚れた割合が大きい   E3 は「状態述語」であって吸収ではない。★ 主推定量の再考が要る
    ★ 目安を先に置く：0.10 未満なら (C) 続行、0.30 超なら再考、その間は併記して判断
""")


# ══════════════════════════════════════════════════════════════
def check2_oa_by_mlive(rows):
    print("\n" + "=" * 92)
    print("検算2  OA を m_live で層別する（2026-08-30 宣言の履行）")
    print("=" * 92)

    scored = [r for r in rows if r.get("stage2_b") is not None]
    bins = defaultdict(list)
    for record in scored:
        m = record.get("m_live_final")
        if m is None:
            continue
        bins["%d" % m if m <= 4 else "5+"].append(record)

    print("\n  分母 ＝ 段階2（パターン b）に到達した def")
    print("\n  %-8s%12s%12s%12s%14s%10s"
          % ("m_live", "OA_gstar", "OA_supply", "OA_applied", "gstar採択加重", "n"))
    for key in sorted(bins, key=lambda k: (k == "5+", k)):
        picked = bins[key]
        weighted = [r for r in picked
                    if r.get("OA_gstar") is not None and r.get("adoptions")]
        total = sum(r["adoptions"] for r in weighted)
        wmean = (sum(r["OA_gstar"] * r["adoptions"] for r in weighted) / total
                 if total else None)
        print("  %-8s%s%s%s%s%10d"
              % (key,
                 fmt(mean([r.get("OA_gstar") for r in picked]), 12),
                 fmt(mean([r.get("OA_supply") for r in picked]), 12),
                 fmt(mean([r.get("OA_applied") for r in picked]), 12),
                 fmt(wmean, 14),
                 len(picked)))

    print("""
  読み方
    ★ m_live=1 の帯で OA_gstar が 0 に近ければ、朝に予告した退化が起きている
      （生存構成素が汎用述語 1 本だけになると、どこに適用しても裏付けられてしまう）
      → その場合は「m_live=1 の帯で gstar は構造上ゼロになる」と明記して報告する
    ★ m_live が減るほど OA が上がるなら、薄化と過剰適用が単調に結びついている
""")


# ══════════════════════════════════════════════════════════════
def check3_stage2_rate(rows):
    print("\n" + "=" * 92)
    print("検算3  U-093  段階2 到達率の面（f × θ′）")
    print("=" * 92)

    for pattern in ("b", "a1", "a2"):
        key = "stage2_" + pattern
        for scope in sorted({r["repair_scope"] for r in rows if r.get("repair_scope")}):
            subset = [r for r in rows if r.get("repair_scope") == scope]
            if not subset:
                continue
            thetas = sorted({r["theta_prime"] for r in subset})
            mark = " ★主" if pattern == "b" else ""
            print("\n### 到達率  パターン %s%s   射程 = %s" % (pattern, mark, scope))
            print("            θ′ → " + "".join("%12.4f" % t for t in thetas))
            for value in sorted({r["f"] for r in subset}):
                cells = []
                for theta in thetas:
                    picked = [r for r in subset
                              if r["f"] == value and r["theta_prime"] == theta]
                    reached = sum(1 for r in picked if r.get(key) is not None)
                    cells.append(reached / len(picked) if picked else None)
                print("  f=%-9.4f%s" % (value, "".join(fmt(c, 12) for c in cells)))
            break            # ★ 射程は 1 本だけ出す（二本が同一かは別途 grep で判定中）

    print("""
  読み方
    ★ 100% に張りついていれば、段階2 による条件づけは判別力を持たない
      → 通過率 ≒ E3 率になる。「段階2 は判別ではなく認定として働く」と読む
    ★ f 軸で動けば、段階2 は外生的な時計ではなく学習に応答している
      → その場合は U-092（枚の減衰則）の重さが下がる
""")


# ══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-def", required=True)
    args = parser.parse_args()

    path = Path(args.per_def)
    rows = load(path)
    print("読み込み  %s（def %d 行）" % (path, len(rows)))
    print("★ 追加走行なし。per_def.jsonl の既存の欄を層別しているだけ")

    check1_absorption(rows)
    check2_oa_by_mlive(rows)
    check3_stage2_rate(rows)


if __name__ == "__main__":
    main()
