"""指定した一対一12集団の数表と、再計算用の記録を保存する。"""
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT/'outputs_recheck_2026-10-02'
ANALYSIS = ROOT/'pilot_analysis_20261002'
RESULTS = ROOT.parents[1]/'codex_worldv4_2026-10-01/results'
DEST = RESULTS/'mac/collective_strictpc_20261001/pilot_20261002'
REPORT = RESULTS/'control/2026-10-01_穴出しと集団化_Codex.md'
MARKER = '### 段3：お店の世界の一対一（2026-10-02）'


def save(path,value):
    assert not path.exists(),path
    path.write_text(json.dumps(value,ensure_ascii=False,indent=1)+'\n')


def main():
    assert (OUTPUTS/'gate_passed.json').exists()
    pops = [json.loads(p.read_text()) for p in sorted(ANALYSIS.glob('pilot_*.json'))]
    assert len(pops) == 12 and sum(p['common']['数']['課題'] for p in pops) == 41760
    assert {(p['world'],p['mode'],p['group_seed']) for p in pops} == {
        (world,mode,seed) for world in (1,2) for mode in ('recvA','no_comm') for seed in (1,2,3)}
    assert not DEST.exists() and MARKER not in REPORT.read_text()
    DEST.mkdir()
    aggregate = {}
    for world in (1,2):
        for mode in ('recvA','no_comm'):
            selected = [p for p in pops if p['world'] == world and p['mode'] == mode]
            doors = {cue: Counter() for cue in ('n','e')}
            flow,numbers,reasons = Counter(),Counter(),Counter()
            for p in selected:
                for cue,n in p['doors'].items():
                    doors[cue].update(n)
                flow.update(p['exception_flow'])
                numbers.update(p['common']['数'])
                reasons.update(p['abstain_reasons'])
            aggregate[f'w{world}_{mode}'] = {'world':world,'mode':mode,'populations':3,
                'world_tasks':numbers['課題'],'doors':{cue:dict(n) for cue,n in doors.items()},
                'exception_flow':dict(flow),'numbers':dict(numbers),'abstain_reasons':dict(reasons)}
    for world in (1,2):
        for cue in ('n','e'):
            assert aggregate[f'w{world}_recvA']['doors'][cue]['課題'] == aggregate[f'w{world}_no_comm']['doors'][cue]['課題']
    save(DEST/'aggregate.json',aggregate)
    manifest = []
    for p in pops:
        name = p['condition']
        run = OUTPUTS/name
        target = DEST/'runs'/name
        target.mkdir(parents=True)
        shutil.copyfile(ANALYSIS/(name+'.json'),target/'counts.json')
        shutil.copyfile(run/'flag.json',target/'flag.json')
        shutil.copyfile(OUTPUTS/(name+'.argv.json'),target/'argv.json')
        for path in sorted((run/'comm').glob('*')):
            dest = target/(path.name+'.gz' if path.suffix == '.jsonl' else path.name)
            if path.suffix == '.jsonl':
                dest.write_bytes(gzip.compress(path.read_bytes(),mtime=0))
            else:
                shutil.copyfile(path,dest)
        for path in sorted((run/'ledgers/cells').glob('*/*.jsonl.gz')):
            seed = int(path.name.split('.')[0][4:])
            assert seed in (p['group_seed'],p['group_seed']+1000)
            digest,n = hashlib.sha256(),0
            with gzip.open(path,'rb') as f:
                next(f)
                for line in f:
                    digest.update(line)
                    n += 1
            assert n == 1740
            manifest.append({'condition':name,'world_seed':seed,'path':str(path),'rows':n,
                             'body_sha256':digest.hexdigest(),'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    assert len(manifest) == 24
    save(DEST/'ledger_manifest.json',manifest)
    source_sha = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT/'source',text=True).strip()
    save(DEST/'source_and_scope.json',{'source':source_sha,'branch':'codex-collective-strictpc','python':'3.12.13',
                                     'populations':12,'world_tasks':41760,'world_seeds':[1,2,3,1001,1002,1003],
                                     'parallel_populations':2,'forgetting_price':0.0187,'learning_price':0.0187,
                                     'f':[0.5,0.5],'send_probability':{'recvA':0.2,'no_comm':0},
                                     'config':'config/sweep_shop_hide1_s1_2026-10-01.json','gate_passed':True})
    scripts = DEST/'scripts'
    scripts.mkdir()
    for name in ('analyze_pilot.py','report_pilot.py'):
        shutil.copyfile(ROOT/name,scripts/name)
    lines = [
        '\n'+MARKER+'\n',
        f'保存時刻：{datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")}。コード codex-collective-strictpc（{source_sha}）。動作確認として実施し、数と事実だけを記録。',
        '',
        '世界1・2 × 受信A・通信なし × 集団の種1〜3＝12集団、24個体走行、41,760世界課題。各集団は二体、両方f=0.5、受信Aは送信確率0.2、通信なしは0。忘却・学習の値段はともに0.0187。各個体1,740試行。二体目の世界の種は集団の種＋1000。設定 config/sweep_shop_hide1_s1_2026-10-01.json。--answer-gap --strict-pc と、関門で非介入を確認した --cf-value --probe-world を使用。実行引数と全旗を保存。',
        '走行の並列は最大2集団。全走行をこのマックで実施。種21〜40と8体の集団は使っていない。台帳は全て保持。',
        '',
        'Fは固定の答えを持つ席、Hは候補の名と回数の履歴から答える席、Uは席の中身を忘れ、全体の頻度から答える席。',
        'ドアの課題は held_out_is_door=true の世界課題。通常／例外は場面側の shop_cue=n/e で分けた。分母は二体の課題の和。',
        '',
        '#### 通常・例外のドア（各条件3集団の和）',
        '',
        '| 世界 | 通信 | 日 | 課題（分母） | 正解 | 誤答 | 棄権 |',
        '|---|---|---|---:|---:|---:|---:|',
    ]
    for a in aggregate.values():
        for cue,day in [('n','通常'),('e','例外')]:
            n=a['doors'][cue]
            lines.append(f"| {a['world']} | {'受信A' if a['mode']=='recvA' else 'なし'} | {day} | {n['課題']} | {n.get('正解',0)} | {n.get('誤答',0)} | {n.get('棄権',0)} |")
    lines += ['', '#### 集団の種ごとのドア', '',
              '| 世界 | 通信 | 集団の種 | 通常：課題/正解/誤答/棄権 | 例外：課題/正解/誤答/棄権 |',
              '|---|---|---:|---|---|']
    for p in pops:
        parts=['/'.join(str(p['doors'][cue].get(k,0)) for k in ('課題','正解','誤答','棄権')) for cue in ('n','e')]
        lines.append(f"| {p['world']} | {'受信A' if p['mode']=='recvA' else 'なし'} | {p['group_seed']} | {parts[0]} | {parts[1]} |")
    lines += [
        '', '#### 例外の場面から送られた束', '',
        '例外由来は、送った人の実際の世界の場面が例外だった束。送信の記録から、その人と試行番号で場面を突き合わせた。受け手へ例外の印を追加していない。sig_eは束の中に含まれた例外のシールの述語。',
        '取り込みは、受信の結果が「同化」か「誕生」だった件数。使用は、その取り込んだ定義が後の世界試行で選ばれた（R_used）こと。回答もした件数を別列に記載。再伝達は、その定義から後の試行で束を送ったこと。定義の名前と生まれた試行を併せて区別した。',
        '各受信を一件として、その後に一回以上あれば一件と数える。同じ定義に複数の受信が入ったときは、各受信を別々に数える。取り込まれた後の定義の履歴は変わりうる。',
        '',
        '| 世界/通信 | 例外由来の送信 / 全送信 | sig_eを含む / 例外由来 | 取り込み / 例外由来 | 後で世界で使用 / 取り込み | 後で世界で回答 / 取り込み | 後で再伝達 / 取り込み |',
        '|---|---|---|---|---|---|---|',
    ]
    def flow_row(label,f):
        n=f.get('例外由来',0);inc=f.get('例外由来の取り込み',0)
        return f"| {label} | {n} / {f.get('送信',0)} | {f.get('例外由来でsig_eあり',0)} / {n} | {inc} / {n} | {f.get('取り込んだ定義が世界で使われた',0)} / {inc} | {f.get('取り込んだ定義が世界で回答した',0)} / {inc} | {f.get('取り込んだ定義が再伝達された',0)} / {inc} |"
    for a in aggregate.values():
        lines.append(flow_row(f"{a['world']} / {'受信A' if a['mode']=='recvA' else 'なし'}",a['exception_flow']))
    lines += ['', '0/0は対象の送信が無いことを表し、割合を計算していない。', '',
              '| 世界/通信/集団の種 | 例外由来の送信 / 全送信 | sig_eを含む / 例外由来 | 取り込み / 例外由来 | 後で世界で使用 / 取り込み | 後で世界で回答 / 取り込み | 後で再伝達 / 取り込み |',
              '|---|---|---|---|---|---|---|']
    for p in pops:
        lines.append(flow_row(f"{p['world']} / {'受信A' if p['mode']=='recvA' else 'なし'} / {p['group_seed']}",p['exception_flow']))
    lines += ['', '#### 全世界課題の突き合わせ', '',
              '| 世界 | 通信 | 課題 | 正解 | 誤答 | 棄権 | 誤答F | 誤答H | 誤答U |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for a in aggregate.values():
        n=a['numbers']
        lines.append(f"| {a['world']} | {'受信A' if a['mode']=='recvA' else 'なし'} | {n['課題']} | {n.get('正解',0)} | {n.get('誤答',0)} | {n.get('棄権',0)} | {n.get('誤答_F',0)} | {n.get('誤答_H',0)} | {n.get('誤答_U',0)} |")
    lines += ['', '棄権の理由別の全件数は aggregate.json、各集団の件数と各例外由来の受信の追跡は runs/*/counts.json に保存。',
              '全12集団で、課題数＝正解＋誤答＋棄権、誤答の出どころの和、回答一致の四分類、送信＝配達＝受信、束の予測＝実回答が一致。棄権した試行の束0、一個体一試行の束は最多1。受信の通常採点・価値の変更・費用の見積りと実値の相違は全件0。',
              '', '保存先：mac/collective_strictpc_20261001/pilot_20261002/。全数表、例外由来の束の一件ごとの追跡、通信の元記録、旗と実行引数、24本の台帳の指紋と場所を保存。台帳と答えごとの元記録は '+str(OUTPUTS)+' に保持。',
              '段3の12集団の動作確認と数表の保存を終了。']
    with REPORT.open('a') as f:
        f.write('\n'.join(lines)+'\n')
    files=[{'path':str(p.relative_to(DEST)),'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
           for p in sorted(DEST.rglob('*')) if p.is_file()]
    save(DEST/'files.json',files)
    print(json.dumps({'populations':12,'world_tasks':41760,'files':len(files)+1,'bytes':sum(p['size'] for p in files)},ensure_ascii=False))


if __name__ == '__main__':
    main()
