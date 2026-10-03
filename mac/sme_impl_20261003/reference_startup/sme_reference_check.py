"""公式SMEの回帰検査を、模型を変更せず専用の場所で再実行する。

配布の照合・点・検査・期待値はそのまま使う。変更はSBCLでの
package設定と、ローダーの警告書式への対応だけ。Pythonで期待値を作らない。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import zipfile


OFFICIAL_URL = "https://www.qrg.northwestern.edu/software/sme4/sme4.zip"
OFFICIAL_SHA256 = "cef95b9f6994ec595095d69dc1e9219b54273634ba9424cd1dfd1072e1df6d45"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lisp_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--sbcl", type=Path, required=True)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--library-path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    archive = args.archive.resolve()
    executable = args.sbcl.resolve()
    output = args.output.resolve()
    if sha256(archive) != OFFICIAL_SHA256:
        parser.error("指定した公式配布のsha256と一致しません")
    if output.exists():
        parser.error("出力先はまだ存在しない専用の場所を指定してください")
    output.mkdir(parents=True)
    shutil.copy2(archive, output / "official_sme4.zip")
    source = output / "distribution"
    source.mkdir()
    original_hashes = {}
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            dest = (source / member.filename).resolve()
            if not dest.is_relative_to(source):
                raise ValueError("配布に出力先の外への参照があります")
            if not member.is_dir():
                original_hashes[member.filename] = hashlib.sha256(bundle.read(member)).hexdigest()
        bundle.extractall(source)

    # 原典の算法は触らず、SMEを置くpackageだけをSBCLにも定義する。
    defsys = source / "v4/defsys.lsp"
    original = defsys.read_text()
    unsupported = "#+(not (or lucid allegro aclpc mcl))"
    project = "#+(or mcl allegro) (:use :qrg :common-lisp :clos :sme)"
    if original.count(unsupported) != 1 or original.count(project) != 1:
        raise ValueError("確認した配布のpackage設定と異なります")
    compatible = original.replace(
        unsupported,
        "#+sbcl (:use :common-lisp :qrg)\n"
        "     #+(not (or lucid allegro aclpc mcl sbcl))",
    ).replace(project, "#+sbcl (:use :qrg :common-lisp :sme)\n       " + project)
    (output / "original_defsys.lsp").write_bytes(defsys.read_bytes())
    defsys.write_text(compatible)
    scientific_changes = [
        name for name, digest in original_hashes.items()
        if name != "v4/defsys.lsp" and sha256(source / name) != digest
    ]
    if scientific_changes:
        raise ValueError("起動設定以外に変更があります: " + repr(scientific_changes))

    startup = output / "startup.lsp"
    startup.write_text(f"""(in-package :cl-user)
;; CLのpackage別名を用意する。照合・採点の関数は変えない。
(unless (find-package :lisp)
  (defpackage :lisp (:use :cl))
  (do-external-symbols (s :cl) (export s :lisp)))
(load {lisp_string(str(source / 'qrgsetup.lsp'))})
(setf qrg::*qrg-path* {lisp_string(str(source) + '/')})
(qrg:load-qrg-defsys "v4")
;; SBCLの警告の書式は文字列でないことがある。警告を隠さない。
(defun qrg::muffle-compile-sys-load-warning? (condition)
  (declare (ignore condition)) nil)
(qrg:compile-sys :sme)
(qrg:load-sys :sme)
(sme:sme-shakedown)
;; 表の期待値も実測値もLispの検査と結果から読む。
(dolist (test sme::*sme-tests*)
  (let ((instance (cdr (assoc test sme::*detailed-sme-test-results*))))
    (format t "~&SME-CODEX-ROW~C~A~C~A~C~A~C~A~C~A~C~A~%"
      #\\Tab (sme::name test) #\\Tab (if (sme::passed? test) 1 0)
      #\\Tab (second (assoc :mh-count (sme::sme-tests test)))
      #\\Tab (length (sme::mhs instance))
      #\\Tab (second (assoc :mapping-count (sme::sme-tests test)))
      #\\Tab (length (sme::mappings instance)))))
""", encoding="utf-8")
    command = [str(executable)]
    if args.core:
        command += ["--core", str(args.core.resolve())]
    command += ["--noinform", "--non-interactive", "--load", str(startup)]
    environment = os.environ.copy()
    if args.library_path:
        environment["DYLD_LIBRARY_PATH"] = str(args.library_path.resolve())
    log = output / "official_reference.log"
    start = time.monotonic()
    with log.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(command, cwd=output, env=environment,
                                   stdout=stream, stderr=subprocess.STDOUT, check=False)
    elapsed = time.monotonic() - start
    rows = []
    for line in log.read_text().splitlines():
        if not line.startswith("SME-CODEX-ROW\t"):
            continue
        _, name, passed, expected_mh, actual_mh, expected_maps, actual_maps = line.split("\t")
        rows.append(dict(name=name, passed=int(passed), expected_mh=int(expected_mh),
                         actual_mh=int(actual_mh), expected_maps=int(expected_maps),
                         actual_maps=int(actual_maps)))
    if rows:
        with (output / "official_regression.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    metadata = dict(official_url=OFFICIAL_URL, archive_sha256=OFFICIAL_SHA256,
                    source_member_hashes=original_hashes,
                    changed_source_files=["v4/defsys.lsp"],
                    changed_algorithm_files=[], changed_expected_values=[],
                    command=command, elapsed_seconds=elapsed,
                    lisp_exit_code=completed.returncode, tests=len(rows),
                    passed=sum(row["passed"] for row in rows), rows=rows)
    (output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: metadata[key] for key in
                      ("lisp_exit_code", "tests", "passed", "elapsed_seconds")}, ensure_ascii=False))
    return 0 if completed.returncode == 0 and len(rows) == 7 and all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
