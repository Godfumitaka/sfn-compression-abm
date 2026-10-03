"""直列旗の終了通知だけを検査する。模型を動かさず、送信待ちと逆順の完了を作る。"""
import multiprocessing as mp
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import v311c
import v3_run


def test_large_terminal_messages_reverse_completion(monkeypatch):
    # 八体の計算は一度に一体。4 MiB の通知は親が読むまで pipe に収まらない。
    ctx = mp.get_context("fork")
    lock = ctx.BoundedSemaphore(1)
    computed = [ctx.Event() for _ in range(8)]
    order = ctx.Queue()
    payload = "x" * (4 * 1024 * 1024)

    def worker(task):
        i = task["v311c"]["agent"]
        order.put(i)
        computed[i].set()
        return {"agent": i, "payload": payload, "v311c": {"agent": i}}

    monkeypatch.setattr(v3_run, "worker", worker)
    conns, procs = {}, []
    try:
        for i in reversed(range(8)):
            parent, child = ctx.Pipe()
            conns[i] = parent
            p = ctx.Process(target=v311c._agent_main,
                            args=(child, {"v311c": {"agent": i, "serial_lock": lock}}))
            p.start()
            child.close()
            procs.append(p)
            assert computed[i].wait(10), f"個体{i}が直列ロックを取得できない"
        assert [order.get(timeout=10) for _ in range(8)] == list(reversed(range(8)))
        # 計算は逆順に完了したが、実際のまとめ役と同じ個体番号順で通知を読む。
        for i in range(8):
            assert conns[i].poll(10)
            assert conns[i].recv() == {"type": "done", "rec": {
                "agent": i, "payload": payload, "v311c": {"agent": i}}}
        for p in procs:
            p.join(10)
            assert not p.is_alive()
            assert p.exitcode == 0
        assert lock.acquire(timeout=1)
        lock.release()
    finally:
        for p in procs:
            if p.is_alive():
                p.terminate()
            p.join(10)
        for c in conns.values():
            c.close()
        order.close()
        order.join_thread()


@pytest.mark.parametrize("failure", [None, "worker", "serialize", "send"])
def test_terminal_prepared_under_lock_sent_after_single_release(monkeypatch, failure):
    class Lock:
        held = False
        releases = 0

        def acquire(self):
            assert not self.held
            self.held = True

        def release(self):
            assert self.held
            self.held = False
            self.releases += 1

    lock = Lock()
    messages = []

    class Conn:
        def send(self, message):
            assert not lock.held
            if failure == "send" and message["type"] == "done":
                raise OSError("終了通知の送信失敗")
            messages.append(message)

    def worker(task):
        assert lock.held
        if failure == "worker":
            raise RuntimeError("個体の計算失敗")
        return {"answer": 3, "v311c": {"sent": 2}}

    def jsonable(rec):
        assert lock.held
        if failure == "serialize":
            raise TypeError("通知の準備失敗")
        return rec

    monkeypatch.setattr(v3_run, "worker", worker)
    monkeypatch.setattr(v311c, "_jsonable", jsonable)
    v311c._agent_main(Conn(), {"v311c": {"serial_lock": lock}})
    assert lock.releases == 1
    assert not lock.held
    assert messages[0]["type"] == ("error" if failure else "done")
    if failure is None:
        assert messages == [{"type": "done", "rec": {"answer": 3, "v311c": {"sent": 2}}}]
