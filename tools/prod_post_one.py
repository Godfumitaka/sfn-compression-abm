"""本番の流れ（2026-09-26 夜、アストラさんの指示）：台帳が一本できるたびに、台帳を読む解析を全部かけ、本体の sha256 を控え、台帳を消す。
★ seed001・002 の台帳は消さない。★ 模型と台帳の中身は変えない（読むだけ。消すのは解析と控えが済んだ後）。
かける解析（台帳一本ごと。出力は <腕の走行根>/post/<セル>/seedNNN/ に置く）
  rows2（tools/rows2_par.py）・traj8（tools/traj8_par.py）・lsweep（analysis_pred_2026-09-22/lsweep.py）・newlabelR（analysis_newlabel_2026-09-19/newlabel_R.py）・
  走査の版 7（tools/l2scan_spoke_v7.py。水準 2 の a/b〔l2scan2 と同じ数え方〕・版 5〜7 の列を全部含む）・数え（tools/prod_readcounts.py：写しの割合・話した定義・L）。
  ★ l2scan2.py は、版 7 の走査に同じ数（a_*・b_*）が入っているので、既定ではかけない（PROD_L2SCAN2=1 でかける）。
  ★ 道具は中身を変えずに呼ぶ。lsweep と newlabel_R は、このマックの場所（/Users/tatsu-admin/sfn/sfn-compression-abm）に決め打ちで書くので、
    書かれた物を台帳ごとの置き場へ移す（デスクトップでは、その場所をリポジトリへのリンクとして作っておく）。
  ★ 道具に渡す腕名は「<腕>__<セル>__seedNNN」（台帳ごとに別の名前。道具は既にある出力を上書きしないため）。
控え：<腕の走行根>/post/sha256.jsonl に一行（腕・セル・種・本体〔見出しを除く〕の sha256・行数・台帳の大きさ・見出しの code_commit・消したか）。
やり直し：POSTDONE があれば何もしない。解析の出力が既にあれば、その解析は飛ばす。台帳が無く POSTDONE も無ければ、止めて知らせる。
使い方  python3.12 tools/prod_post_one.py <腕の走行根> <腕名> <セル（台帳の置き場所の名前）> <種の番号>"""
import gzip, hashlib, json, os, pathlib, shutil, subprocess, sys, time

REPO = pathlib.Path(__file__).resolve().parent.parent
MAC = pathlib.Path("/Users/tatsu-admin/sfn/sfn-compression-abm")
KEEP = {int(x) for x in os.environ.get("PROD_KEEP_SEEDS", "1 2").split()}   # ★ 残す種（既定 1・2。明日の並びの s21 の腕は 21・22 を渡す）


def body_sha(p):
    h = hashlib.sha256(); n = 0; header = None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == 0:
                header = json.loads(line); continue
            h.update(line.encode("utf-8")); n += 1
    return h.hexdigest(), n, header


def main():
    arm_root, arm, cell, seed = pathlib.Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3], int(sys.argv[4])
    py = sys.executable
    seedf = str(REPO / "seeds/U-011_seed_v3a2.json")
    sd = f"seed{seed:03d}"
    led = arm_root / "ledgers" / "cells" / cell / f"{sd}.jsonl.gz"
    done = arm_root / "ledgers" / "cells" / cell / f"{sd}.done"
    post = arm_root / "post" / cell / sd
    if (post / "POSTDONE").exists():
        return 0
    if not done.exists():
        print(f"★ 走行が終わっていない（.done が無い） {led}"); return 2
    if not led.exists():
        print(f"★ 台帳が無いのに POSTDONE も無い（解析の前に消えた？） {led}"); return 3
    if not MAC.exists():
        print(f"★ {MAC} が無い（決め打ちの道具のため、リポジトリへのリンクとして作っておく）"); return 4
    post.mkdir(parents=True, exist_ok=True)
    rdl = post / "rd" / "ledgers" / "cells" / cell
    rdl.mkdir(parents=True, exist_ok=True)
    link = rdl / f"{sd}.jsonl.gz"
    if not link.is_symlink():
        link.symlink_to(led)
    fl = post / "rd" / "flag.json"                    # 走査の版 7 は、走行根の一つ上の flag.json で直しの有無を決める
    if not fl.is_symlink():
        fl.symlink_to(arm_root / "flag.json")
    tag = f"{arm}__{cell}__{sd}"
    RD = str(post / "rd" / "ledgers")
    steps = [
        ("rows2", [py, str(REPO / "tools/rows2_par.py"), tag, RD, seedf, str(post / "rows2.json"), "1"], None),
        ("traj8", [py, str(REPO / "tools/traj8_par.py"), tag, RD, seedf, str(post / "traj8.json"), "1"], None),
        ("lsweep", [py, str(REPO / "analysis_pred_2026-09-22/lsweep.py"), tag, RD, "1"],
         MAC / f"analysis_pred_2026-09-22/lsweep_{tag}.json"),
        ("newlabelR", [py, str(REPO / "analysis_newlabel_2026-09-19/newlabel_R.py"), tag, RD, "1"],
         MAC / f"analysis_newlabel_2026-09-19/newlabelR_{tag}.json"),
        ("l2s7", [py, str(REPO / "tools/l2scan_spoke_v7.py"), tag, RD, seedf, str(post / "l2s7.json"), "1"], None),
        ("counts", [py, str(REPO / "tools/prod_readcounts.py"), tag, RD, str(post / "counts.json"), "1",
                    "--lsweep", str(post / "lsweep.json")], None),
    ]
    if os.environ.get("PROD_L2SCAN2") == "1":
        steps.append(("l2b", [py, str(REPO / "analysis_pred_2026-09-22/l2scan2.py"), tag, RD, seedf, "1"],
                      MAC / f"analysis_pred_2026-09-22/l2b_{tag}.json"))
    t0 = time.time(); secs = {}
    for name, cmd, written in steps:
        out = post / f"{name}.json"
        if out.exists():
            continue
        if written is not None and written.exists():
            written.unlink()                              # この台帳だけの名前の、前の途中の残り
        t1 = time.time()
        r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
        (post / f"{name}.log").write_text(r.stdout + r.stderr, encoding="utf-8")
        if written is not None and written.exists():
            shutil.move(str(written), str(out))
        if r.returncode != 0 or not out.exists():
            print(f"★ 解析 {name} が失敗 rc={r.returncode} {post}/{name}.log"); return 5
        json.load(open(out, encoding="utf-8"))           # 読めるか
        secs[name] = round(time.time() - t1, 1)
    sha, n, header = body_sha(led)
    rec = dict(arm=arm, cell=cell, seed=seed, body_sha256=sha, n_body=n, ledger_bytes=led.stat().st_size,
               code_commit=(header or {}).get("code_commit"), run_seed=(header or {}).get("run_seed"),
               analyses=[s[0] for s in steps], analysis_secs=secs, post_secs=round(time.time() - t0, 1),
               deleted=seed not in KEEP, at=time.strftime("%Y-%m-%d %H:%M:%S"))
    (post / "sha.json").write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    with open(arm_root / "post" / "sha256.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if seed not in KEEP:
        led.unlink()
    (post / "POSTDONE").write_text(rec["at"] + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
