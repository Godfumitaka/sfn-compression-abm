"""完了した一対一の台帳を数える。入力も模型も変更しない。"""
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT/'source'
sys.path.insert(0, str(SOURCE/'tools'))
import v311c_report

OUTPUTS = ROOT/'outputs'
ANALYSIS = ROOT/'analysis'
PATTERN = re.compile(r'pilot_w([12])_(recvA|no_comm)_g(0(?:0[1-9]|1[0-9]|20))$')


def write(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1)+'\n')


def one(run):
    match = PATTERN.fullmatch(run.name)
    assert match
    world, mode, group = int(match[1]), match[2], int(match[3])
    comm_path = run/'comm'/f'run{group:03d}.jsonl'
    comm = [json.loads(l) for l in comm_path.read_text().splitlines()]
    summary = next(r for r in comm if r['kind'] == 'summary')
    assert summary['trials'] == 1740 and not summary['errors']
    assert [a['seed'] for a in summary['agents']] == [group, group+1000]
    common = v311c_report.one_population(str(run), str(comm_path))
    audit, numbers = common['突き合わせ'], common['数']
    assert common['失敗'] == 0 and numbers['課題'] == 3480
    assert audit['個体の課題の和'] == audit['誤答の出どころの和'] == 2
    assert audit.get('一致の四分類の和', 0) == common['probes']
    assert all(audit[k] == 1 for k in ('送信＝配達', '配達＝受け取りの記録', '束のある試行は実際に答えた試行',
                                     '一個体一試行に束は一つまで', '受け取りで束を送らない'))
    assert all(numbers.get('STATS_'+k,0) == 0 for k in ('recv_score_changed', 'recv_merit_changed', 'dC_mismatch'))
    assert numbers.get('誤答_?',0) == 0
    actual = {}
    births = [defaultdict(list), defaultdict(list)]
    selected = [[], []]
    doors = {cue: Counter() for cue in ('n', 'e')}
    reasons = Counter()
    for agent, meta in enumerate(summary['agents']):
        path = run/'ledgers/cells'/meta['cell']/f"seed{meta['seed']:03d}.jsonl.gz"
        with gzip.open(path, 'rt') as stream:
            next(stream)
            for line in stream:
                row = json.loads(line)
                t = row['prediction_order']
                cue = row['shop_cue']
                assert cue in ('n', 'e')
                actual[agent,t] = {'coverage': row['coverage'], 'hit': row['hit'],
                                   'cue': cue, 'is_door': row['held_out_is_door'],
                                   'prediction': row['predicted_edge']}
                category = '正解' if row['coverage'] == 1 and row['hit'] == 1 else '誤答' if row['coverage'] == 1 else '棄権'
                if row['held_out_is_door']:
                    doors[cue]['課題'] += 1
                    doors[cue][category] += 1
                if category == '棄権':
                    reasons[row['abstain_reason']] += 1
                for event in row.get('reg_del_events') or []:
                    if event.get('kind') == 'registration' and not event['was_extension']:
                        births[agent][event['R']].append(event['trial'])
                if row.get('R_used') is not None:
                    selected[agent].append((t,row['R_used'],row['coverage']))
    assert len(actual) == 3480
    bundles = [r for r in comm if r['kind'] == 'bundle']
    receives = [r for r in comm if r['kind'] == 'recv']
    for r in receives:
        if r['result'] == '誕生':
            births[r['agent']][r['R']].append(r['R_born'])
    for by_name in births:
        for R, times in by_name.items():
            times.sort()

    def identity(agent,R,t):
        times = [b for b in births[agent][R] if b <= t]
        return max(times) if times else None

    received_by = {(r['t'],r['from']): r for r in receives}
    assert len(received_by) == len(receives)
    sent = [b for b in bundles if b.get('send')]
    assert len(sent) == len(receives) == numbers.get('送信',0)
    for b in bundles:
        row = actual[b['agent'],b['t']]
        assert row['coverage'] == 1
        if not b.get('empty'):
            p = row['prediction']
            assert b['pred'] == [p['relation_id'],p['predicate'],p['arguments']]
    exception_receipts = []
    flow = Counter(送信=len(sent))
    for b in sent:
        row = actual[b['agent'],b['t']]
        if row['cue'] != 'e':
            continue
        flow['例外由来'] += 1
        has_cue = any(rel[1] == 'sig_e' for rel in b['relations'])
        flow['例外由来でsig_eあり'] += has_cue
        receipt = received_by[b['t'],b['agent']]
        assert receipt['agent'] == b['to'] and receipt['bundle'] == b['bundle']
        incorporated = receipt['result'] in ('同化','誕生')
        flow['例外由来の取り込み'] += incorporated
        result = {'sender':b['agent'],'recipient':receipt['agent'],'t':b['t'],'bundle':b['bundle'],
                  'sender_world_seed':summary['agents'][b['agent']]['seed'], 'has_sig_e':has_cue,
                  'result':receipt['result'], 'incorporated':incorporated,
                  'R':receipt.get('R'), 'R_born':receipt.get('R_born'),
                  'selected_later':False,'answered_later':False,'sent_later':False}
        if incorporated:
            agent,R,born,t = receipt['agent'],receipt['R'],receipt['R_born'],receipt['t']
            later = [(tt,cov) for tt,rr,cov in selected[agent] if tt > t and rr == R and identity(agent,rr,tt) == born]
            result['selected_later'] = bool(later)
            result['answered_later'] = any(cov == 1 for _,cov in later)
            result['sent_later'] = any(bb['agent'] == agent and bb['t'] > t and bb.get('R') == R
                                       and bb.get('R_born') == born for bb in sent)
            flow['取り込んだ定義が世界で使われた'] += result['selected_later']
            flow['取り込んだ定義が世界で回答した'] += result['answered_later']
            flow['取り込んだ定義が再伝達された'] += result['sent_later']
        exception_receipts.append(result)
    for cue,n in doors.items():
        assert n['正解']+n['誤答']+n['棄権'] == n['課題']
    if mode == 'no_comm':
        assert not sent and not receives and not exception_receipts
    return {'condition':run.name,'world':world,'mode':mode,'group_seed':group,
            'world_seeds':[group,group+1000],'doors':{cue:dict(n) for cue,n in doors.items()},
            'exception_flow':dict(flow),'exception_receipts':exception_receipts,
            'abstain_reasons':dict(reasons),'common':common,
            'prediction_bundle_mismatches':0}


if __name__ == '__main__':
    ANALYSIS.mkdir(exist_ok=True)
    for run in sorted(OUTPUTS.glob('pilot_*')):
        if not run.is_dir() or not PATTERN.fullmatch(run.name):
            continue
        dest = ANALYSIS/(run.name+'.json')
        if dest.exists():
            continue
        summary = list((run/'comm').glob('*.summary.json'))
        if not summary:
            continue
        try:
            meta = json.loads(summary[0].read_text())
        except ValueError:
            continue
        if meta['trials'] != 1740:
            continue
        value = one(run)
        write(dest,value)
        print(json.dumps({k:value[k] for k in ('condition','doors','exception_flow')},ensure_ascii=False),flush=True)
