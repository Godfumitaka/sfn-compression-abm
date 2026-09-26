"""結果のブランチ（results-2026-09-27）へ、腕の結果を確かに上げる（2026-09-26 夜、アストラさんの指示）。
★ 前の tools/prod_arm_done.py は、コミットの失敗を黙って捨て、何も上がっていなくても「上げた」と記録していた（デスクトップで見つかった）。
手順
  1 git add -A <機械>/<腕>。失敗すれば、その旨を返す。
  2 追加・変更があればコミットする。失敗すれば（名前の設定が無いなど）、git の出力を添えて失敗を返す。
  3 push する。はじかれたら fetch → pull --rebase（失敗すれば rebase --abort）してから、上げ直す（最大 6 回、待ちを伸ばしながら）。
  4 確かめ：fetch したリモートの results-2026-09-27 に、手元の <機械>/<腕>/ のファイルが全部あり、中身も同じか（git ls-tree と git diff）。
     そろっていなければ失敗を返す。そろっていれば「確かめ済み」を返す。
使い方  from results_push import push_arm; ok, lines = push_arm(<結果の作業場所>, <機械>, <腕>, <コミットの文>)
        python3.12 tools/results_push.py <結果の作業場所> <機械> <腕> [<コミットの文>]   … 単独でも使える（確かめと上げ直し）"""
from __future__ import annotations

import os
import subprocess
import sys
import time

BRANCH = "results-2026-09-27"


def _git(resdir, *args):
    return subprocess.run(["git", "-C", str(resdir), *args], capture_output=True, text=True)


def _local_files(resdir, host, arm):
    base = os.path.join(str(resdir), host, arm)
    out = set()
    for root, _dirs, files in os.walk(base):
        for f in files:
            out.add(os.path.relpath(os.path.join(root, f), str(resdir)).replace(os.sep, "/"))
    return out


def verify(resdir, host, arm):
    """リモートに手元の <機械>/<腕>/ が全部あり、中身が同じか。（ok, 足りないファイル, 中身が違うか）"""
    f = _git(resdir, "fetch", "-q", "origin", BRANCH)
    if f.returncode != 0:
        return False, ["★ fetch が失敗 " + (f.stderr or "").strip()[-300:]], True
    r = _git(resdir, "-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", f"origin/{BRANCH}", "--", f"{host}/{arm}")
    remote = set(r.stdout.splitlines())
    local = _local_files(resdir, host, arm)
    missing = sorted(local - remote)
    d = _git(resdir, "diff", "--quiet", f"origin/{BRANCH}", "--", f"{host}/{arm}")
    differ = d.returncode != 0
    return (bool(local) and not missing and not differ), missing, differ


def push_arm(resdir, host, arm, message, tries=6):
    lines = []
    a = _git(resdir, "add", "-A", f"{host}/{arm}")
    if a.returncode != 0:
        return False, [f"★ git add が失敗：{(a.stderr or '').strip()[-300:]}"]
    staged = _git(resdir, "diff", "--cached", "--quiet").returncode != 0
    if staged:
        c = _git(resdir, "commit", "-q", "-m", message)
        if c.returncode != 0:
            return False, [f"★ コミットが失敗（上げていない）：{((c.stdout or '') + (c.stderr or '')).strip()[-400:]}"]
        lines.append("コミットした " + _git(resdir, "log", "--oneline", "-1").stdout.strip())
    else:
        lines.append("コミットするものは無かった（手元の枝に入っている）")
    for i in range(tries):
        p = _git(resdir, "push", "-q", "origin", f"HEAD:{BRANCH}")
        if p.returncode == 0:
            lines.append(f"push した（{i + 1} 回目）")
            break
        lines.append(f"push がはじかれた（{i + 1} 回目）：{(p.stderr or '').strip().splitlines()[-1:] }")
        _git(resdir, "fetch", "-q", "origin", BRANCH)
        rb = _git(resdir, "pull", "-q", "--rebase", "origin", BRANCH)
        if rb.returncode != 0:
            _git(resdir, "rebase", "--abort")
            lines.append(f"pull --rebase が失敗し、取りやめた：{(rb.stderr or '').strip()[-200:]}")
        time.sleep(min(10 * (i + 1), 60))
    ok, missing, differ = verify(resdir, host, arm)
    if ok:
        lines.append(f"確かめ済み：リモートの {BRANCH} に {host}/{arm}/ の {len(_local_files(resdir, host, arm))} ファイルが同じ中身である")
        return True, lines
    lines.append(f"★ 確かめで足りない：無いファイル {missing[:10]}・中身の違い {differ}")
    return False, lines


if __name__ == "__main__":
    resdir, host, arm = sys.argv[1], sys.argv[2], sys.argv[3]
    msg = sys.argv[4] if len(sys.argv) > 4 else f"結果：{host} の {arm}（上げ直し）"
    ok0, missing, differ = verify(resdir, host, arm)
    if ok0:
        print(f"すでに上がっている：{host}/{arm}"); sys.exit(0)
    print(f"上がっていない（無いファイル {len(missing)}・中身の違い {differ}）。上げ直す")
    ok, lines = push_arm(resdir, host, arm, msg)
    print("\n".join(lines))
    sys.exit(0 if ok else 3)
