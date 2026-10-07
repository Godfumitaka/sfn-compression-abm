"""指定された高速符号化が型・順・全バイトを維持することを検査する。"""
from dataclasses import dataclass
from enum import Enum,IntEnum
import json
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1])]
import pytest
import smereplay
from test_attncstar import cstar,retained_U_structure,build
from test_sme2017_connection import separate


class Number(IntEnum):
    item=1


class Name(str,Enum):
    item='name'


@dataclass(frozen=True)
class Nested:
    value:object


def test_fast_encoder_keeps_enum_dataclass_sequence_and_mapping_order():
    value=Nested({Number.item:(Name.item,[None,True,3,2.5,'名']),
                  'set':frozenset({'b','a'}),'tuple':(Nested(False),)})
    assert json.dumps(smereplay._fast_encode(value),ensure_ascii=False)==json.dumps(
        smereplay.encode(value),ensure_ascii=False)
    # 復号の既存allowlistは狭めたり広げたりしない。この検査用の型は拒否する。
    for encoder in (smereplay.encode,smereplay._fast_encode):
        with pytest.raises(ValueError,match='認めていない型'):
            smereplay.decode(encoder(value))


def test_fast_encoder_actual_state_input_config_and_rng_bytes_equal(cstar,retained_U_structure):
    from random import Random
    state,cfg,obs,ai=build()
    before=repr(state),repr(ai),repr(cfg),repr(obs)
    for value in (state,ai,cfg,Random(42).getstate()):
        assert json.dumps(smereplay._fast_encode(value),ensure_ascii=False)==json.dumps(
            smereplay.encode(value),ensure_ascii=False)
    assert (repr(state),repr(ai),repr(cfg),repr(obs))==before
