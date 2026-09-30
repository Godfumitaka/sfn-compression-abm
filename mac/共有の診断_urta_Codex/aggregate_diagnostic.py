"""完了済みの判断の記録から、分布と走行ごとの表を作る。"""
from pathlib import Path
import collections
import csv
import gzip
import hashlib
import io
import json
import math
import time

ROOT=Path(__file__).resolve().parent
DEST=ROOT/'diagnostic_tables'
DEST.mkdir(exist_ok=True)
METRICS=('required_net_saving','gross_selected_min','gross_selected_max','gross_max','net_memory_saving',
         'net_memory_saving_ratio','gross_selected_ratio_min','gross_selected_ratio_max','reference_selected_min','reference_selected_max',
         'remaining_unchanged','remaining_unchanged_existing')

def distribution(values):
    xs=sorted(v for v in values if v is not None)
    def quantile(q):
        i=(len(xs)-1)*q
        lo=math.floor(i); hi=math.ceil(i)
        return xs[lo]+(xs[hi]-xs[lo])*(i-lo)
    return dict(n=len(xs),undefined=len(values)-len(xs),positive=sum(v>0 for v in xs),
                mean=sum(xs)/len(xs) if xs else None,
                **{k:quantile(q) if xs else None for k,q in
                   [('min',0),('p25',.25),('median',.5),('p75',.75),('p90',.9),('max',1)]})

def bounds(options,key):
    values=[key(o) for o in options]
    return (min(values),max(values)) if values else (None,None)

def reduce_run(path):
    meta=json.loads(path.read_text())
    arm=meta['arm']; seed=meta['seed']
    assert 1<=seed<=20 and meta['counts']['trials']==1740
    stem=f'{arm}/seed{seed:03d}'
    folder=DEST/arm;folder.mkdir(exist_ok=True)
    output=folder/f'seed{seed:03d}.quantities.csv.gz'
    result=folder/f'seed{seed:03d}.aggregate.json'
    if output.exists() or result.exists():raise FileExistsError(stem)
    values={lev:{k:[] for k in METRICS} for lev in ('A','B')}
    counts={lev:collections.Counter() for lev in ('A','B')}
    writer=None;actual=collections.Counter();digest=hashlib.sha256()
    with output.open('xb') as raw, gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as gz:
        with io.TextIOWrapper(gz,encoding='utf-8',newline='') as out:
            with gzip.open(meta['decision_file'],'rt',encoding='utf-8') as records:
                for line in records:
                    digest.update(line.encode('utf-8'))
                    row=json.loads(line)
                    actual['decisions']+=1
                    actual['existing']+=row['original'] is not None
                    actual['new']+=row['original'] is None
                    actual['cross']+=row['cross_motif']
                    new=next((c for c in row['candidates'] if c['R'] is None),None)
                    for lev in ('A','B'):
                        decision=row['decisions'][lev];stat=counts[lev]
                        for key in ('changed','existing_to_new','new_to_existing'):
                            stat[key]+=decision[key]
                        stat['cross_to_new']+=decision['existing_to_new'] and row['cross_motif']
                        stat['existing_to_other_existing']+=decision['changed'] and row['original'] is not None and decision['chosen'] is not None
                        stat['candidate_evaluations']+=len(row['candidates'])
                        stat['source_evaluations_after']+=sum(len(c['levels'][lev]['after']['source_U']) for c in row['candidates'])
                        stat['multiple_sources_after']+=sum(c['levels'][lev]['after']['multiple_sources'] for c in row['candidates'])
                        stat['multiple_sources_before']+=sum(bool(c['levels'][lev]['before'] and c['levels'][lev]['before']['multiple_sources']) for c in row['candidates'])
                        stat['any_candidate_multiple_sources']+=any(c['levels'][lev]['after']['multiple_sources'] for c in row['candidates'])
                        stat['excluded_U_N_after_exposures']+=sum(c['levels'][lev]['after']['excluded_U_N'] for c in row['candidates'])
                        stat['excluded_U_S_after_exposures']+=sum(sum(c['levels'][lev]['after']['source_U'].values()) for c in row['candidates'])
                        entry=dict(arm=arm,seed=seed,trial=row['trial'],lambda_=row['lambda_'],level=lev,
                                   original=row['original'],chosen=decision['chosen'],changed=int(decision['changed']),
                                   existing_to_new=int(decision['existing_to_new']),cross_motif=int(row['cross_motif']),
                                   new_available=int(new is not None),required_net_saving=row['required_net_saving'],
                                   remaining_bits=decision['remaining_bits'])
                        if row['original'] is not None:
                            values[lev]['required_net_saving'].append(row['required_net_saving'])
                        if not decision['changed']:
                            values[lev]['remaining_unchanged'].append(decision['remaining_bits'])
                            if row['original'] is not None:
                                values[lev]['remaining_unchanged_existing'].append(decision['remaining_bits'])
                        if new:
                            ns=new['levels'][lev];after=ns['after'];best=after['best']
                            net=new['dC']-ns['dC']
                            ratio=net/new['dC'] if new['dC'] else None
                            winners=[o for o in after['options'] if o['source'] in after['source_ties']]
                            gl,gh=bounds(winners,lambda o:o['saving'])
                            rl,rh=bounds(winners,lambda o:o['reference_total'])
                            gl=gl or 0;gh=gh or 0
                            rl=rl if rl is not None else 1;rh=rh if rh is not None else 1
                            stat['new_shared']+=after['shared']
                            stat['new_multiple_sources']+=after['multiple_sources']
                            stat['new_excluded_U_N']+=after['excluded_U_N']
                            stat['new_excluded_U_S_exposures']+=sum(after['source_U'].values())
                            for k,v in dict(gross_selected_min=gl,gross_selected_max=gh,gross_max=after['max_gross'],
                                net_memory_saving=net,net_memory_saving_ratio=ratio,
                                gross_selected_ratio_min=gl/new['dC'] if new['dC'] else None,
                                gross_selected_ratio_max=gh/new['dC'] if new['dC'] else None,
                                reference_selected_min=rl,reference_selected_max=rh).items():
                                values[lev][k].append(v)
                            low,high=bounds(after['raw_best'],lambda o:o['saving'])
                            rlow,rhigh=bounds(after['raw_best'],lambda o:o['reference_total'])
                            # 同点の共有先は全部残す。費用は同じなので表では範囲を出す。
                            entry.update(new_dC_original=new['dC'],new_dC_shared=ns['dC'],
                                new_K_original=new['K'],new_K_shared=ns['K'],
                                shared=int(after['shared']),source_ties=json.dumps(after['source_ties']),
                                gross_selected_min=gl,gross_selected_max=gh,
                                gross_max=after['max_gross'],raw_best_gross_min=low,raw_best_gross_max=high,
                                raw_best_reference_min=rlow,raw_best_reference_max=rhigh,
                                net_memory_saving=net,net_memory_saving_ratio=ratio,
                                eligible_sources=after['eligible_sources'],excluded_U_N=after['excluded_U_N'],
                                excluded_U_S_exposures=sum(after['source_U'].values()))
                            for name in 'abcde':
                                vals=[o['reference'][name] for o in after['options'] if o['source'] in after['source_ties']]
                                entry['reference_'+name+'_min']=min(vals) if vals else (1 if name=='a' else 0)
                                entry['reference_'+name+'_max']=max(vals) if vals else (1 if name=='a' else 0)
                        else:
                            for key in ('new_dC_original','new_dC_shared','new_K_original','new_K_shared','shared','source_ties',
                                        'gross_selected_min','gross_selected_max','gross_max','raw_best_gross_min',
                                        'raw_best_gross_max','raw_best_reference_min','raw_best_reference_max',
                                        'net_memory_saving','net_memory_saving_ratio','eligible_sources','excluded_U_N',
                                        'excluded_U_S_exposures'):
                                entry[key]=None
                            for name in 'abcde':
                                entry['reference_'+name+'_min']=entry['reference_'+name+'_max']=None
                        if writer is None:
                            writer=csv.DictWriter(out,fieldnames=list(entry));writer.writeheader()
                        writer.writerow(entry)
    for key,count in actual.items():assert count==meta['counts'][key],(stem,key,count,meta['counts'][key])
    for lev in ('A','B'):
        for key in ('changed','existing_to_new','new_to_existing','cross_to_new'):
            assert counts[lev][key]==meta['counts'][f'{lev}_{key}']
    aggregate=dict(arm=arm,seed=seed,input_summary=meta,decision_text_sha256=digest.hexdigest(),
        counts={lev:dict(counts[lev]) for lev in counts},
        distributions={lev:{k:distribution(v) for k,v in values[lev].items()} for lev in values})
    result.write_text(json.dumps(aggregate,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'aggregated':stem,'decisions':actual['decisions']},ensure_ascii=False),flush=True)

if __name__=='__main__':
    done=set()
    while len(done)<220:
        for path in sorted((ROOT/'diagnostic_full').glob('*/seed*.summary.json')):
            if path in done:continue
            reduce_run(path);done.add(path)
        if 'Traceback' in (ROOT/'diagnostic_full.log').read_text():raise RuntimeError('解析の停止を確認。完了分の表を保持する')
        if len(done)<220:time.sleep(10)
    print('全220走行の表を保存',flush=True)
