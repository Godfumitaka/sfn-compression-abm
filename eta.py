#!/usr/bin/env python3
"""eta.py — 走行の残り時間を .done のタイムスタンプから実測する。

使い方
    python3.14 eta.py runs/abstain_2026-08-31 320

第1引数  走行ディレクトリ（cells/ の親でよい）
第2引数  予定の総走行数（省略可。省略すると速度だけ出す）

★ 読むだけ。何も書かない・消さない。走行中に実行してよい。
★ .done のタイムスタンプだけを見る。台帳（.gz）には触れない。
"""

import sys
import time
import pathlib
import datetime


def fmt_span(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} 時間 {m} 分"
    if m:
        return f"{m} 分 {s} 秒"
    return f"{s} 秒"


def main() -> int:
    if len(sys.argv) < 2:
        print("使い方: python3.14 eta.py <走行ディレクトリ> [予定総数]")
        return 2

    root = pathlib.Path(sys.argv[1])
    total = int(sys.argv[2]) if len(sys.argv) > 2 else None

    if not root.exists():
        print(f"パスがありません: {root}")
        return 2

    dones = sorted(root.rglob("*.done"), key=lambda p: p.stat().st_mtime)
    n = len(dones)
    now = time.time()

    print(f"走行ディレクトリ  {root}")
    print(f"完了した走行      {n} 件" + (f" / 予定 {total} 件" if total else ""))

    if n == 0:
        print("\nまだ 1 件も完了していません。")
        print("・起動直後なら正常です（1 走行ぶん待ってから再実行してください）")
        print("・パスが違う可能性もあります。ls で確認してください")
        return 0

    t_first = dones[0].stat().st_mtime
    t_last = dones[-1].stat().st_mtime

    print(f"最初の完了        {datetime.datetime.fromtimestamp(t_first):%H:%M:%S}")
    print(f"直近の完了        {datetime.datetime.fromtimestamp(t_last):%H:%M:%S}"
          f"（{fmt_span(now - t_last)} 前）")

    if n < 2:
        print("\n速度を出すには 2 件以上の完了が要ります。数分後に再実行してください。")
        return 0

    span = t_last - t_first
    if span <= 0:
        print("\nタイムスタンプの差がありません。数分後に再実行してください。")
        return 0

    rate_per_hour = (n - 1) / span * 3600.0
    print(f"\n実測の速度        {rate_per_hour:.1f} 走行/時"
          f"（{(n - 1)} 件を {fmt_span(span)} で処理）")

    # 停止の検出：直近の完了から、平均間隔の 5 倍以上あいていたら警告
    mean_gap = span / (n - 1)
    if now - t_last > mean_gap * 5:
        print("\n★ 警告  直近の完了から、平均間隔の 5 倍以上あいています。")
        print("        走行が止まっている可能性があります。")
        print("        pgrep -fl sweep.py と pmset -g batt を確認してください。")

    if total is None:
        return 0

    remaining = total - n
    if remaining <= 0:
        print(f"\n★ 完走しています（{n} / {total}）。")
        return 0

    eta_seconds = remaining / rate_per_hour * 3600.0
    finish = datetime.datetime.fromtimestamp(now + eta_seconds)

    print(f"残り              {remaining} 件")
    print(f"★ 残り時間        {fmt_span(eta_seconds)}")
    print(f"★ 完了予定        {finish:%m/%d %H:%M}")
    print(f"進捗              {n / total * 100:.1f} %")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
