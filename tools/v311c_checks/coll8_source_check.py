"""保存記録だけを読む採点欄の検査。模型からは呼ばない。"""

# no_m1の記録はこの7欄だけ。採点欄・source・未知の欄を許さない。
INITIAL_KEYS = frozenset(('kind', 'trial', 'x', 'R_B', 'R_E', 'C_end', 'zero_release'))
SCORE_KEYS = frozenset(('K', 'r', 'cands', 'lam', 'chosen', 'reg', 'x_rows', 'N',
                        'dC_pred', 'dC_real', 'dT', 'C_after_E', 'ties',
                        'was_extension', 'hist_inc'))


def validate_source(row, expected):
    """採点がある記録は出どころ必須。未採点の記録も明示的に検査する。"""
    if row.get('kind') != 'v310be':
        raise ValueError('v310be以外を渡した')
    if row.get('x') == 'no_m1':
        if (expected != '世界' or set(row) != INITIAL_KEYS or row['trial'] != 0
                or row['R_B'] != 0 or row['R_E'] != 0 or row['zero_release'] != []):
            raise ValueError('未採点の初期行に採点欄・非零の採点・未知の欄がある')
        return 'initial_unscored'
    if row.get('source') != expected:
        raise ValueError('採点又はm1の記録に正しいsourceが無い')
    score_keys = SCORE_KEYS.intersection(row)
    if score_keys:
        if not {'K', 'r', 'cands'} <= set(row) or not row['cands']:
            raise ValueError('採点欄が一部だけある')
        return 'scored'
    # 既存のm1の不成立二経路。採点欄が無いことを欄集合でも確認する。
    empty_keys = {'kind', 'trial', 'disclosed', 'source', 'x', 'new_excluded',
                  'R_B', 'R_E', 'C_end', 'zero_release'}
    if (not set(row) <= empty_keys or not
            (('x' in row and row['x'] is None) or 'new_excluded' in row)
            or row.get('R_E', 0) != 0):
        raise ValueError('未採点のm1不成立行に採点欄があるか、経路が不明')
    return 'm1_unscored'
