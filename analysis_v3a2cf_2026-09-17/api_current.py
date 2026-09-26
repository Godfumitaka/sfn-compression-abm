"""現行APIに渡す種と設定。解析専用・台帳SHAで明示解決。"""
from pathlib import Path
from functools import lru_cache
from dataclasses import replace
from abm.seed import load_seed, higher_order_predicates
HERE=Path(__file__).resolve().parent
@lru_cache(None)
def seed_for_sha(digest):
    for path in (HERE/'current_runtime'/'seeds').glob('*.json'):
        seed=load_seed(path)
        if seed.file_sha256==digest:return seed
    raise ValueError('台帳の種SHAに一致する固定種なし: '+digest)
def seed_for_header(h):return seed_for_sha(h['seed_file_sha256'])
def configure(config,h):
    return replace(config,local_lambda=h.get('arm_local_lambda',0.0),
        holdout_include_second_order=h.get('arm_holdout_second_order',False),
        higher_order_predicates=higher_order_predicates(seed_for_header(h)))
def history_value(v):
    if isinstance(v,dict):
        if any(not isinstance(n,int) or n<0 for n in v.values()):raise ValueError('履歴回数が非負整数でない')
        return dict(v)
    if isinstance(v,(list,tuple,set,frozenset)):return frozenset(v)
    raise TypeError('未知の履歴形式 '+str(type(v)))
