"""42′の最終分布の損。候補の分布は開示前に確定して渡す。"""
from dataclasses import dataclass
import math
import attnratio as A


@dataclass(frozen=True)
class Loss:
    value: float
    selected: str | None
    correct_mass: float | None
    reason: str | None
    source: str
    escaped: bool


def predicate(correct):
    return correct[0] if isinstance(correct, tuple) else correct


def probability(distribution, name):
    p=float(distribution.get(name,0.))
    if not math.isfinite(p) or not 0<=p<=1:
        raise ValueError('答える位置の確率は有限で0以上1以下')
    return p


def cost(p, ell):
    """確率0は既存L_ofの符号長。微小確率の追加はしない。"""
    if not math.isfinite(p) or p<0 or not math.isfinite(ell) or ell<0:
        raise ValueError('確率と退避符号の長さが不正')
    return -math.log2(p) if p>0 else float(ell)


def candidate_distribution(candidate, background):
    item=candidate.payload.get('readout') or {}
    if not item.get('gate_passed',False):
        return background,'background_gate_closed'
    if item.get('slot') is None or item.get('P') is None:
        return background,'background_no_answer_slot'
    return item['P'],'equal_slot_mixture' if item.get('distribution_case')=='equal_slot_mixture' else 'selected_slot'


def softmax(candidates, attention, temperature=1.):
    if not math.isfinite(temperature) or temperature<=0:
        raise ValueError('既存の注意の温度は有限で正')
    scored=A.log_scores(candidates,attention)
    if not scored:return ()
    top=max(temperature*z for _,z in scored)
    exponentials=[math.exp(temperature*z-top) for _,z in scored]
    total=sum(exponentials)
    return tuple((c,e/total) for (c,_),e in zip(scored,exponentials))


def loss(candidates, attention, correct, ell, *, mode, choose, background, temperature=1.):
    selected=choose(candidates,attention)
    name=None if selected is None else selected.name
    if mode=='alpha':
        return Loss(0. if selected is not None and selected.answer==correct else float(ell),
                    name,None,None,'spoken_answer',False)
    target=predicate(correct)
    if mode=='top1':
        distribution,source=(background,'background_no_candidate') if selected is None else \
                             candidate_distribution(selected,background)
        p=probability(distribution,target)
    elif mode=='mixture':
        weighted=softmax(candidates,attention,temperature)
        source='mixture' if weighted else 'background_no_positive_candidate'
        p=math.fsum(pi*probability(candidate_distribution(c,background)[0],target)
                    for c,pi in weighted) if weighted else probability(background,target)
    else:raise ValueError('42′の損はalpha/top1/mixture')
    return Loss(cost(p,ell),name,p,None,source,p==0)


def mixture_gradient(candidates, attention, correct, ell, *, background, bits=True, temperature=1.):
    """対応・候補・席の分布を固定した範囲の代理損の勾配。"""
    target=predicate(correct)
    weighted=softmax(candidates,attention,temperature)
    if not weighted:
        p=probability(background,target)
        value=cost(p,ell)
        return value if bits else value*math.log(2.),{},'no_positive_candidate'
    masses=[pi*probability(candidate_distribution(c,background)[0],target) for c,pi in weighted]
    p=math.fsum(masses)
    if p==0:
        # 退避符号は、この固定した範囲ではaに依存しない。
        return float(ell) if bits else float(ell)*math.log(2.),{},'zero_probability_escape'
    gradient={}
    unit=temperature/math.log(2.) if bits else temperature
    for (candidate,pi),mass in zip(weighted,masses):
        for key,m in candidate.mismatch:
            gradient[key]=gradient.get(key,0.)+unit*(mass/p-pi)*m
    value=-math.log2(p) if bits else -math.log(p)
    return value,gradient,None
