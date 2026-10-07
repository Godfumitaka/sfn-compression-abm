"""全候補の最終回答の損を、一席の一段の忘却で測る。

照合に依存しない数値部品。対応・回答は開示前の写しで作った候補を
渡す。開示は損の評価だけに渡し、薄くした候補の作成には渡さない。
"""
from dataclasses import asdict, dataclass, replace
import math
import time
import attnratio as A


# 第一段は softmax(z) であり、温度係数は暗黙に1。新しい値は加えない。
LEARNING_TEMPERATURE = 1.0


@dataclass(frozen=True)
class Seat:
    definition: str
    slot: int
    state: str
    generation: int


@dataclass(frozen=True)
class Loss:
    value: float
    selected: str | None
    correct_mass: float | None
    reason: str | None = None


def resolve_loss(mode, *, score_logp):
    if mode not in ('alpha', 'top1', 'mixture', 'arm'):
        raise ValueError('第二段の損の旗が不正')
    return ('top1' if score_logp else 'alpha') if mode == 'arm' else mode


def loss(candidates, attention, correct, ell, *, mode, choose, temperature=LEARNING_TEMPERATURE, background=None):
    """chooseは元の同点規則。損の評価は門を含む固定済み回答を使う。"""
    if mode in ('top1','mixture'):
        if background is None:raise ValueError('開示前に固定した基底分布が必要')
        from attnstage2_readout import loss as readout_loss
        return readout_loss(candidates,attention,correct,ell,mode=mode,choose=choose,
                            background=background,temperature=temperature)
    selected = choose(candidates, attention)
    name = None if selected is None else selected.name
    if mode == 'alpha':
        return Loss(0. if selected is not None and selected.answer == correct else float(ell), name, None)
    # 旧betaは過去の検査の比較専用。42′の旗からは呼べない。
    if mode != 'beta' or not math.isfinite(temperature) or temperature <= 0:
        raise ValueError('損又は学びの温度が不正')
    scored = A.log_scores(candidates, attention)
    good = [temperature*z for c,z in scored if c.answer == correct]
    if not good:
        return Loss(math.inf, name, 0., 'no_correct_candidates')
    all_z = [temperature*z for _,z in scored]
    def logsum(values):
        top = max(values)
        return top+math.log(sum(math.exp(v-top) for v in values))
    natural = logsum(all_z)-logsum(good)
    return Loss(natural/math.log(2.), name, math.exp(-natural))


def bit_gradient(candidates, attention, correct):
    """第一段の自然対数の勾配との単位差を明示する。第一段は変えない。"""
    natural,g,reason = A.loss_gradient(candidates,attention,correct)
    if reason is not None:
        return None, {}, reason
    return natural/math.log(2.), {k:v/math.log(2.) for k,v in g.items()}, None


def measurement_seats(seats, *, scope, selected):
    """42⁗のC。測る席の集合以外は全候補版と変えない。"""
    if scope not in ('all','chosen'):raise ValueError('第二段の席の範囲が不正')
    return tuple(seat for seat in seats if scope=='all' or seat.definition==selected)


def compare_seats(candidates, attention, seats, thin_fixed, thin_exact, *, correct, ell, mode, choose, background=None,method='fixed'):
    """各席で一つの候補だけを差し替え、全候補を並べ直す。

    methodで主の一席再照合と固定対応の監査を区別する。
    strictの呼び出しは小例の検査だけ。undefinedな∞−∞を値にしない。
    回答を作るcallbackへcorrect/ellは渡さない。
    """
    start = time.perf_counter()
    if method not in ('fixed','rematched'):raise ValueError('反実仮想の方法が不正')
    base = loss(candidates,attention,correct,ell,mode=mode,choose=choose,background=background)
    rows = []
    for seat in seats:
        fixed = thin_fixed(seat)
        changed = tuple(fixed if c.name == seat.definition else c for c in candidates)
        changed = tuple(c for c in changed if c is not None)
        after = loss(changed,attention,correct,ell,mode=mode,choose=choose,background=background)
        delta = after.value-base.value
        if not math.isfinite(delta):
            raise ArithmeticError(('第二段のΔrが有限でない',seat,base,after))
        row = {'R':seat.definition,'slot':seat.slot,'state':seat.state,'gen':seat.generation,
               'method':method,'r_after':after.value,'delta':delta,
               'selected_after':after.selected,'q_after':None if fixed is None else float(fixed.q),
               'r_before':base.value,'r_fixed':after.value,'delta_fixed':delta,
               'selected_before':base.selected,'selected_fixed':after.selected,
               'fixed_q':None if fixed is None else float(fixed.q)}
        if thin_exact is not None:
            exact = thin_exact(seat)
            exact_loss = loss(exact,attention,correct,ell,mode=mode,choose=choose,background=background)
            row.update(r_exact=exact_loss.value,delta_exact=exact_loss.value-base.value,
                       selected_exact=exact_loss.selected,
                       loss_difference=after.value-exact_loss.value)
        rows.append(row)
    chosen=next((c for c in candidates if c.name==base.selected),None)
    return rows, {'seconds':time.perf_counter()-start,'thinned_seats':len(rows),
                  'baseline_loss':asdict(base),
                  'baseline_readout':None if chosen is None else chosen.payload.get('readout'),
                  'rerankings':1+len(rows)*(2 if thin_exact is not None else 1)}


def accumulate(seats_in, rows, trial):
    """同じrec_addへΔrだけを積む。Aの局所損は加えない。

    RF/RH/RUの既存四列を差分の容器として使う：Fでは(0,Δr,Δr)、
    Hでは(0,0,Δr)。FHでRFが消えてもRH−RU=0で、新しいHの値を
    古いFの値から流用しない。記憶のビットと世代の規則は変えない。
    """
    import v39
    seats = dict(seats_in)
    applied = []
    for row in rows:
        key = (row['R'],row['slot'])
        rec = seats.get(key)
        if rec is None or rec.gen != row['gen'] or rec.state != row['state']:
            continue
        value = row['delta'] if 'delta' in row else row['delta_fixed']
        if not math.isfinite(value):
            raise ArithmeticError('第二段の保持記録へ非有限値を入れない')
        inc = (0.,value,value,1.) if row['state'] == 'F' else (0.,0.,value,1.)
        seats[key] = v39.rec_add(rec,trial,inc)
        applied.append(key)
    return seats, applied
