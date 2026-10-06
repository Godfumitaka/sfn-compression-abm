"""事前指定三手例で相対費用の手計算・中央差分・直接費用の等価を検査。"""
import argparse,gzip,json,math
from pathlib import Path
import attnratio as P
from attnratio_features import candidate
from attnposition_input import records,fingerprint

def softmax(values):
    top=max(values);e=[math.exp(z-top) for z in values];total=sum(e)
    return [v/total for v in e]

def cost(p,length):return -math.log(p) if p>0 else length*math.log(2.)

def run(base,output):
    old=base/'position_attention_2026-10-06'
    hands=json.loads((old/'hand_gate_checks.json').read_text())['examples']
    results=[];gradients=[];equivalence=[]
    for hand in hands:
        world,seed,trial=hand['world'],hand['seed'],hand['trial']
        source=output/'features'/f'n3_w{world}_A_L50'/f'seed{seed:03d}.features.jsonl.gz'
        frame=next(f for f in records(source) if f['trial']==trial)
        byname={c['R']:c for c in frame['candidates']}
        # 正解役は既に事後選定済みの手例。学習器へ研究者の型は渡さない。
        correctdef=next(d for d in hand['definitions'] if d['role']!='selected_wrong')
        answer=byname[correctdef['R']]['answer'];correct=(answer[0],tuple(answer[1]))
        definitions=[]
        for definition in hand['definitions']:
            c=byname[definition['R']];oldslots={d['slot']:d for d in definition['positions']}
            positions=[]
            for detail in c['details']:
                if detail['reason'] is not None:
                    positions.append({'slot':detail['slot'],'reason':detail['reason'],'m_global':0.,'m_position':0.});continue
                d=oldslots[detail['slot']];name=detail['visible_name'];parts={}
                for mode in ('global','position'):
                    b=detail['b_'+mode].get(name,0.)
                    q=(b if detail['q_H_empty_fallback'] else detail['q_H'].get(name,0.))
                    st=detail['state'];p=b if st=='U' else .5*b+.5*(d['fixed']==name) if st=='F' else .5*q+.5*b
                    length=d[mode]['L_of_bits'];mp=0. if st=='U' else cost(p,length)-cost(b,length)
                    assert p==detail['p_'+mode] and mp==detail['m_'+mode],(trial,c['R'],detail['slot'],mode)
                    parts[mode]={'b':b,'P':p,'L_of_bits':length,'c_P':cost(p,length),'c_b':cost(b,length),'m_prime':mp}
                positions.append({'slot':detail['slot'],'state':detail['state'],'visible_name':name,
                                  'key':detail['key'],'calculation':parts})
            qa={}
            for mode in ('global','position'):
                penalty=sum(d['calculation'][mode]['m_prime'] for d in positions if 'calculation' in d)
                expected=float(candidate(c,mode).q)*math.exp(-penalty)
                actual=math.exp(P.log_scores([candidate(c,mode)],dict.fromkeys(c['m'][mode],1.))[0][1])
                assert abs(expected-actual)<1e-12*max(1.,abs(expected))
                qa[mode]={'Q':float(candidate(c,mode).q),'sum_m_prime':penalty,'Q_a_hand':expected,'Q_a_kernel':actual}
            definitions.append({'R':c['R'],'role':definition['role'],'positions':positions,'Q_a':qa})
        results.append({'world':world,'seed':seed,'trial':trial,'class':hand['baseline_seal_class'],
                        'definitions':definitions,'input':fingerprint(source)})
        for mode in ('global','position'):
            cs=tuple(candidate(c,mode) for c in frame['candidates']);keys=sorted({k for c in cs for k,_ in c.mismatch})
            a=dict.fromkeys(keys,.3);loss,g,reason=P.loss_gradient(cs,a,correct);assert reason is None
            rows=[]
            for k in keys:
                plus,minus=dict(a),dict(a);plus[k]+=1e-5;minus[k]-=1e-5
                n=(P.loss_gradient(cs,plus,correct)[0]-P.loss_gradient(cs,minus,correct)[0])/2e-5
                assert abs(n-g.get(k,0.))<=2e-9+1e-7*abs(g.get(k,0.)),(trial,mode,k,n,g.get(k))
                rows.append({'key':k,'analytic':g.get(k,0.),'central_difference':n,'abs_difference':abs(n-g.get(k,0.))})
            gradients.append({'world':world,'seed':seed,'trial':trial,'mode':mode,'L':loss,'gradient':rows})
            relative=[z for _,z in P.log_scores(cs,a)];direct=[]
            for c in frame['candidates']:
                if c['q_numerator']==0:continue
                valid={d['key']:d for d in c['details'] if d['reason'] is None}
                total=0.
                for row in frame['visible_positions']:
                    key=row['key'];b=frame['common_bases'][key][mode].get(row['visible_name'],0.)
                    # 基底の費用は当該試行の既存L_ofで、保存済み値を参照する。
                    # 同じ可視名のL_ofはどの候補でも同じ。
                    cb=next((d['c_b_'+mode] for x in frame['candidates'] for d in x['details']
                             if d['reason'] is None and d['key']==key),None)
                    if cb is None:
                        cb=frame['common_bases'][key]['cost_'+mode][row['visible_name']]
                    cp=valid[key]['c_P_'+mode] if key in valid else cb
                    total+=a.get(key,0.)*cp
                direct.append(math.log(candidate(c,mode).q)-total)
            p1,p2=softmax(relative),softmax(direct);diff=max(abs(x-y) for x,y in zip(p1,p2))
            assert diff<1e-12,(trial,mode,diff)
            equivalence.append({'world':world,'seed':seed,'trial':trial,'mode':mode,
                                'candidates':len(p1),'max_probability_difference':diff,'probabilities_relative':p1,'probabilities_direct':p2})
    result={'passed':True,'gate2_trials':3,'gate3_trials':3,'gate4_trials':3,
            'hand_examples':results,'gradients':gradients,'equivalence':equivalence}
    path=output/'hand_gates.json'
    if path.exists():raise RuntimeError('手例の関門の控えを重複しない')
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':True,'gates':[2,3,4]}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.base,a.output)
