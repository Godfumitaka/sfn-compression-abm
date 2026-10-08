"""指示5：完了済み種1〜3の記録を読むだけ。模型の輸入・再予測はしない。"""
from collections import Counter, defaultdict
import csv
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import resource
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'output'
CELL = 'f0.5000_th2.1000_vt0.3842_first_order'
OUT.mkdir(exist_ok=True)
started = time.perf_counter()
inputs = []

def provenance(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    inputs.append(dict(path='$WORKSPACE/' + str(path.relative_to(ROOT.parent)),
                       bytes=path.stat().st_size, sha256=h.hexdigest()))

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def table(name, rows):
    with (OUT / name).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)

probes = []
curves = []
disclosures = []
timings = []
for seed in (1, 2, 3):
    case = ROOT / f'stage2/pilot_s{seed}_5000'
    res = json.loads((case / 'resources.json').read_text())
    assert res['returncode'] == 0 and res['trial_count'] == 5000
    assert res['commit'] == '6408c7cfcf30f242e6be3aa43f646f440ad3195e'
    timings.append({k: res[k] for k in ('seed', 'trial_count', 'horizon', 'commit',
                    'started', 'ended', 'supervised_wall_seconds',
                    'process_peak_rss_bytes_time', 'max_aggregate_rss_mib_sampled_1s')})
    for file in ('resources.json', 'command.json', 'time.txt'):
        provenance(case / file)
    ledger = case / f'run/ledgers/cells/{CELL}/seed{seed:03}.jsonl.gz'
    assert ledger.with_name(f'seed{seed:03}.done').exists()
    counts = Counter(); blocks = defaultdict(Counter); ids = set()
    with gzip.open(ledger, 'rt') as f:
        header = json.loads(next(f))
        assert header['trial_count'] == 5000 and header['run_seed'] == seed
        for t, line in enumerate(f):
            row = json.loads(line)
            assert row['record_type'] == 'trial'
            # coin_tは抽選値であり試行番号ではない。台帳の試行の記録順は0始まり。
            ids.add(t)
            counts['trials'] += 1
            fired = bool(row['f_fired'])
            counts['disclosed'] += fired
            # 研究者欄はこの集計に限る。本人への入力・課題推定に使わない。
            past = bool(row['held_out_is_past'])
            counts['past_trials'] += past
            counts['past_disclosed'] += past and fired
            blocks[t // 1000]['trials'] += 1
            blocks[t // 1000]['disclosed'] += fired
    assert ids == set(range(5000))
    disclosures.append(dict(seed=seed, **counts, fraction=counts['disclosed']/5000,
                            blocks=[dict(first_trial=k*1000+1, last_trial=(k+1)*1000,
                                         **v) for k,v in sorted(blocks.items())]))
    provenance(ledger)
    pp = case / f'run/side/{CELL}/seed{seed:03}.probe.jsonl'
    per = defaultdict(list)
    for line in pp.read_text().splitlines():
        p = json.loads(line)
        assert p['verb_probe'] == 'past'
        if p['verb_class'] == 'novel':
            assert p['truth'] is None and p.get('oracle') is None
            assert p['exp_path_n'] == 0 and p['verbatim_n'] == 0
        ans = p.get('answer')
        category = 'abstain' if ans is None else ('REG' if ans == 'REG' else
                    ('IRR' if ans.startswith('IRR_') else 'other'))
        clean = dict(seed=seed, trial=p['t'], verb_name=p['verb_name'],
                     verb_class=p['verb_class'], truth=p['truth'], answer=ans,
                     oracle=p.get('oracle'), lexical_correct=p.get('answer_is_truth'),
                     category=category)
        probes.append(clean); per[p['t']].append(clean)
    assert sorted(per) == list(range(100,5001,100))
    for t, rows in sorted(per.items()):
        assert len(rows) == 48 and len({p['verb_name'] for p in rows}) == 48
        cls = {k:[p for p in rows if p['verb_class'] == k]
               for k in ('regular','irregular','novel')}
        assert [len(cls[k]) for k in cls] == [32,8,8]
        learned = cls['regular'] + cls['irregular']
        irr_correct = sum(p['oracle'] == 1 for p in cls['irregular'])
        over = sum(p['answer'] == 'REG' for p in cls['irregular'])
        c = dict(seed=seed, trial=t, correct=sum(p['oracle'] == 1 for p in learned),
                 learned_queries=40,
                 regular_correct=sum(p['oracle'] == 1 for p in cls['regular']),
                 regular_queries=32, irregular_correct=irr_correct,
                 irregular_queries=8, irregular_REG=over,
                 irregular_abstain=sum(p['answer'] is None for p in cls['irregular']),
                 irregular_other=8-irr_correct-over-sum(p['answer'] is None for p in cls['irregular']),
                 marcus_DEN=irr_correct+over,
                 marcus_REG_fraction=over/(irr_correct+over) if irr_correct+over else None,
                 novel_REG=sum(p['category'] == 'REG' for p in cls['novel']),
                 novel_IRR=sum(p['category'] == 'IRR' for p in cls['novel']),
                 novel_abstain=sum(p['category'] == 'abstain' for p in cls['novel']),
                 novel_other=sum(p['category'] == 'other' for p in cls['novel']))
        for n in range(1,9): c[f'novel_IRR_{n}'] = sum(p['answer'] == f'IRR_{n}' for p in cls['novel'])
        curves.append(c)
    provenance(pp)
    print(json.dumps({'seed':seed, 'disclosures':counts['disclosed'], 'probes':len(per)*48},ensure_ascii=False),flush=True)

means=[]
for t in range(100,5001,100):
    group=[c for c in curves if c['trial']==t]
    row={'trial':t}
    for k in ('correct','regular_correct','irregular_correct','irregular_REG',
              'irregular_abstain','novel_REG','novel_IRR','novel_abstain','novel_other'):
        denominator = 40 if k=='correct' else 32 if k=='regular_correct' else 8
        row[k+'_fraction'] = sum(c[k] for c in group)/(3*denominator)
    means.append(row)
table('probe_selected_fields.csv',probes)
table('curves_by_seed.csv',curves)
table('curves_three_seed_mean.csv',means)

blockmeans=[]
for seed in (1,2,3,0):
    for end in range(500,5001,500):
        rows=[c for c in curves if end-500<c['trial']<=end and (seed==0 or c['seed']==seed)]
        v=dict(seed=seed,first_probe=end-400,last_probe=end,probe_points=len(rows))
        for k in ('correct','regular_correct','irregular_correct','irregular_REG','novel_REG','novel_IRR','novel_abstain'):
            den=40 if k=='correct' else 32 if k=='regular_correct' else 8
            v[k+'_fraction']=sum(c[k] for c in rows)/(len(rows)*den)
        blockmeans.append(v)
table('curves_500trial_blocks.csv',blockmeans)

# 事後の記述規則。500試行のブロック平均が最後まで幅10/15/20ポイント以内か。
plateau=[]
for tolerance in (.10,.15,.20):
    for seed in (0,1,2,3):
        for key in ('correct_fraction','irregular_correct_fraction','irregular_REG_fraction','novel_REG_fraction'):
            bs=[c for c in blockmeans if c['seed']==seed]
            found=None
            for i in range(len(bs)-3):  # 少なくとも最後4ブロック=2000試行を含める
                values=[c[key] for c in bs[i:]]
                if max(values)-min(values)<=tolerance:
                    found=dict(first_block_start=bs[i]['first_probe']-99,
                               first_block_end=bs[i]['last_probe'], min=min(values),max=max(values));break
            plateau.append(dict(seed=seed,metric=key,tolerance=tolerance,found=found))

# 同じ不規則語の正答→REG→正答の連続したカテゴリー区間だけを拾う。
episodes=[]
for seed in (1,2,3):
    for name in sorted({p['verb_name'] for p in probes if p['verb_class']=='irregular'}):
        seq=sorted([p for p in probes if p['seed']==seed and p['verb_name']==name],key=lambda x:x['trial'])
        runs=[]
        for p in seq:
            cat='correct' if p['oracle']==1 else 'REG' if p['answer']=='REG' else 'abstain' if p['answer'] is None else 'other'
            if runs and runs[-1]['category']==cat: runs[-1]['end']=p['trial'];runs[-1]['points']+=1
            else:runs.append(dict(category=cat,start=p['trial'],end=p['trial'],points=1))
        for a,b,c in zip(runs,runs[1:],runs[2:]):
            if [x['category'] for x in (a,b,c)]==['correct','REG','correct']:
                episodes.append(dict(seed=seed,verb_name=name,correct_before_start=a['start'],
                    correct_before_end=a['end'],REG_start=b['start'],REG_end=b['end'],
                    correct_return_start=c['start'],correct_return_end=c['end'],
                    before_points=a['points'],REG_points=b['points'],return_points=c['points']))
if episodes: table('word_correct_REG_correct.csv',episodes)
save('plateau_descriptive.json',plateau)
save('old_timing_and_disclosures.json',dict(timings=timings,disclosures=disclosures,
     total_trials=15000,total_disclosed=sum(d['disclosed'] for d in disclosures),
     total_disclosure_fraction=sum(d['disclosed'] for d in disclosures)/15000,
     stage2_condition='tools/attnstage2_runtime.py:123 coin.f_fired; future ALLIN rate unmeasured'))
profile=ROOT.parent/'codex_sme_time_evict_2026-10-06/verb_profile1000_01/time_100_trials.csv'
provenance(profile)
(OUT/'sme_100trial_timing.csv').write_bytes(profile.read_bytes())
save('input_manifest.json',dict(at=datetime.now().astimezone().isoformat(),inputs=inputs,
     scope='completed old A seeds 1-3 only; no model import/replay; researcher fields used only in read-only report',
     elapsed_seconds=time.perf_counter()-started,max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
print(json.dumps({'elapsed_seconds':time.perf_counter()-started,
                  'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'episodes':len(episodes)},ensure_ascii=False),flush=True)
