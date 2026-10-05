"""候補を先に計算し、その後の全試行で観測を完了する構造を確かめる。"""
from analyse_run import observe_after_trial


def test_observation_follows_prediction_even_when_candidate_reading_stops():
    events = []

    def source():
        for trial in range(3):
            events.append(("read", trial))
            yield trial

    iterator = observe_after_trial(source(), lambda trial: events.append(("post", trial)))
    assert next(iterator) == 0
    assert events == [("read", 0)]
    events.append(("candidate", 0))
    # 候補側がここで終わっても、包みが最後まで読めば観測は欠けない。
    assert list(iterator) == [1, 2]
    assert events == [("read", 0), ("candidate", 0), ("post", 0),
                      ("read", 1), ("post", 1), ("read", 2), ("post", 2)]
