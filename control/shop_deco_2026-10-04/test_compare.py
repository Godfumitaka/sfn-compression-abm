"""研究者用比較の例外をsec_trialの値に限る。模型は呼ばない。"""
from run_registered import without_measured_sec


def test_only_the_measured_value_is_ignored():
    a = b'{"trial": 3, "value": 4.25, "sec_trial": 0.123}\n'
    b = b'{"trial": 3, "value": 4.25, "sec_trial": 1.234567e-03}\n'
    assert without_measured_sec(a) == without_measured_sec(b)
    assert a.endswith(b'0.123}\n') and b.endswith(b'1.234567e-03}\n')
    assert without_measured_sec(a) != without_measured_sec(b.replace(b'4.25', b'4.26'))
    assert without_measured_sec(a) != without_measured_sec(b.replace(b'"value": ', b'"value":  '))
