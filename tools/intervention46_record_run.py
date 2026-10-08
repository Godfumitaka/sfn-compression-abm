"""既存ドライバをそのまま走らせ、指示5の記録だけを別の出力先へ足す。"""
import os
from pathlib import Path
import sys

import v3_run as native

_native_worker = native.worker
RECORD_ENV = "INTERVENTION46_RESEARCH_RECORD_DIR"


def worker(task):
    path = os.environ.get(RECORD_ENV)
    if path is None:
        return _native_worker(task)
    if not 1 <= task["seed"] <= 20:
        raise ValueError("この入口の承認範囲は種1〜20")
    if task.get("stage2") != "on" or not task.get("attn_allin"):
        raise ValueError("指示5の取り付けは全部入りの第二段の入口で使う")
    import attnstage2_runtime as stage2
    from intervention46_records import Recorder
    original_install = stage2.install
    recorders = []

    def install(*args, **kwargs):
        result = original_install(*args, **kwargs)
        recorder = Recorder(Path(path) / task["cell"] / f"seed{task['seed']:03d}.jsonl.gz")
        recorder.install()
        recorders.append(recorder)
        return result

    stage2.install = install
    try:
        return _native_worker(task)
    finally:
        for recorder in reversed(recorders):
            recorder.close()
        stage2.install = original_install


# spawnされた子でも、関数の読み込みだけで同じドライバに接続する。
native.worker = worker


def main():
    option = "--intervention-record-dir"
    if option in sys.argv:
        index = sys.argv.index(option)
        if index + 1 >= len(sys.argv):
            raise SystemExit("記録の出力先が無い")
        os.environ[RECORD_ENV] = str(Path(sys.argv[index + 1]).resolve())
        del sys.argv[index:index + 2]
    else:
        os.environ.pop(RECORD_ENV, None)
    native.main()


if __name__ == "__main__":
    main()
