"""完了済みの集団だけを保存・集計。模型と台帳を変更しない。"""
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import gzip, hashlib, json, shutil, subprocess

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT.parent/'codex_worldv4_2026-10-01/results'
DEST=RESULTS/'mac/collective20_20261002/C'
REPORT=RESULTS/'control/2026-10-02_集団化の一対一_Codex.md'
PROGRESS=RESULTS/'control/2026-09-30_Codex_進み具合.md'
MARKER='<!-- collective20-C-results -->'

def now(): return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=1)+'\n')
def body(path):
    h=hashlib.sha256();n=0
    with gzip.open(path,'rb') as f:
        next(f)
        for line in f: h.update(line);n+=1
    assert n==1740,(path,n)
    return {'path':str(path),'rows':n,'body_sha256':h.hexdigest(),'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
def publish_run(p):
    name=p['condition'];run=ROOT/'outputs_C'/name;dest=DEST/'runs'/name
    dest.mkdir(parents=True,exist_ok=True)
    if (dest/'saved.json').exists(): return
    for source,name2 in [(ROOT/'analysis_C'/(name+'.json'),'counts.json'),
                         (ROOT/'analysis_C'/(name+'.unselected.json'),'unselected.json'),
                         (ROOT/'outputs_C'/(name+'.argv.json'),'argv.json'),(run/'flag.json','flag.json'),
                         (ROOT/'outputs_C'/(name+'.resource.json'),'resource.json')]:
        assert source.exists(),source
        shutil.copyfile(source,dest/name2)
    for path in sorted((run/'comm').glob('*')):
        if path.suffix=='.jsonl': (dest/(path.name+'.gz')).write_bytes(gzip.compress(path.read_bytes(),mtime=0))
        else: shutil.copyfile(path,dest/path.name)
    for path in sorted((run/'side').glob('*/*.answers.csv')):
        (dest/(path.name+'.gz')).write_bytes(gzip.compress(path.read_bytes(),mtime=0))
    manifest=[body(path) for path in sorted((run/'ledgers/cells').glob('*/*.jsonl.gz'))]
    assert len(manifest)==2
    save(dest/'ledger_manifest.json',manifest)
    save(dest/'saved.json',{'time':now(),'condition':p['condition']})
def table_rows(pops):
    aggregate={}
    for mode in ('no_comm','recvA'):
        selected=[p for p in pops if p['mode']==mode]
        doors={cue:Counter() for cue in ('n','e')};flow=Counter();numbers=Counter();unselected=Counter()
        for p in selected:
            for cue,n in p['doors'].items(): doors[cue].update(n)
            flow.update(p['exception_flow']);numbers.update(p['common']['数'])
            u=json.loads((ROOT/'analysis_C'/(p['condition']+'.unselected.json')).read_text())
            unselected.update(u['counts'])
        aggregate[mode]={'group_seeds':[p['group_seed'] for p in selected],
                         'doors':{cue:dict(v) for cue,v in doors.items()},'exception_flow':dict(flow),
                         'numbers':dict(numbers),'unselected':dict(unselected)}
    return aggregate
def fraction(n,d): return f'{n}/{d}（{100*n/d:.2f}%）' if d else '0/0（対象なし）'
def main():
    pops=[]
    for path in (ROOT/'analysis_C').glob('pilot_w2_*.json'):
        if path.name.endswith('.unselected.json'): continue
        if not path.with_name(path.stem+'.unselected.json').exists(): continue
        pops.append(json.loads(path.read_text()))
    pops.sort(key=lambda p:(p['group_seed'],p['mode']))
    for p in pops: publish_run(p)
    aggregate=table_rows(pops);save(DEST/'aggregate.json',aggregate)
    complete={(p['group_seed'],p['mode']) for p in pops}=={(s,m) for s in range(1,21) for m in ('recvA','no_comm')}
    save(DEST/'source_and_scope.json',{'source':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT/'source',text=True).strip(),
         'python':'3.12.13','arm':'C','cf_learn':True,'world':2,'forgetting_price':0.0187,'learning_price':0.0187,
         'f':[0.5,0.5],'send_probability':{'recvA':0.2,'no_comm':0},'group_seeds_requested':list(range(1,21)),
         'completed_populations':len(pops),'complete':complete,'world_seed_offset_second_agent':1000,
         'parallel_populations_max':2,'combined_heavy_jobs_max':3})
    scripts=DEST/'scripts';scripts.mkdir(exist_ok=True)
    for name in ('measure_C_first.py','run_C_after_A.py','analyze_collective20.py','analyze_unselected.py','report_collective_C.py','publish_C_when_finished.py','combined_parallel_C.py'):
        if (ROOT/name).exists(): shutil.copyfile(ROOT/name,scripts/name)
    for name in ('C_first.measurement.json','C_first.health.jsonl','C_first.time_and_stderr.log','A_ready_for_C.json','C_run_health.jsonl','C_stopped.json'):
        if (ROOT/name).exists(): shutil.copyfile(ROOT/name,DEST/name)
    receipt=REPORT.read_text().split(MARKER)[0].rstrip()
    lines=[receipt,'',MARKER,'',f'\n### C（--cf-learn）の一対一\n\n集計時刻：{now()}。完了{len(pops)}/40集団。'+('Cの種1〜20の両条件を終了。' if complete else '完了した集団だけを下表に記載。'),'',
           '土台：codex-collective-strictpc（34667a55a4e68d7cda64614ead95e84a361b0118）。Python 3.12.13。模型・abm/・fに変更なし。',
           '世界2、C（--cf-learn）、忘却と学習の値段はともに0.0187。二体のfはともに0.5。通信ありは受信A・話す確率0.2、なしは0。設定 config/sweep_shop_hide1_s1_2026-10-01.json。Aの旗に--cf-learnを加えた（--answer-gap --strict-pc --cf-value --probe-worldを含む）。',
           '集団の種は1から順に、各種の両条件をそろえて次へ進む。二体目の世界の種は集団の種＋1000。各個体1740試行、各集団3480課題。種21〜40は使用・読取ともなし。8体の集団なし。台帳は全て保持。','']
    measurement=ROOT/'C_first.measurement.json'
    if measurement.exists():
        m=json.loads(measurement.read_text())
        lines+=['Cの最初の一本（通信なし・集団の種1、並列1）：',
                f"所要時間 {m['elapsed_seconds']:.3f}秒。最大常駐メモリ（OSの計測、個別プロセス）{m['time_maximum_resident_bytes']}バイト（{m['time_maximum_resident_bytes']/1024**2:.2f}MiB）。",
                f"まとめ役と二体を含む処理全体の常駐メモリの最大合計（1秒間隔の観測）{m['sampled_tree_peak_rss_kib']/1024:.2f}MiB。合計は共有領域を重ねて数え、観測間の最大値は含まない。",
                f"開始・終了時のスワップ：{m['initial']['swap_used_mib']:.2f}→{m['final']['swap_used_mib']:.2f}MiB。熱・スワップの全観測を保存。",'']
    gate=ROOT/'A_ready_for_C.json'
    assert gate.exists()
    g=json.loads(gate.read_text())
    lines+=['C開始前の関門：Aの40集団（80個体、139200課題）の完了と全件数の突き合わせを確認。Aの種1〜3は前の試しと件数・台帳本体・通信が一致（例外ドアの誤答は通信なし43、あり38）。Cの件数をAと同じとする検査はしていない。','']
    stop=ROOT/'C_stopped.json'
    if stop.exists(): lines+=['停止の記録：'+json.dumps(json.loads(stop.read_text()),ensure_ascii=False),'']
    lines+=['### ドアの課題','',
            '通常／例外は研究者側の場面の印shop_cue=n/e。ドアはheld_out_is_door=true。分母は二体の課題の和。','',
            '| 腕 | 通信 | 日 | 課題（分母） | 正解 | 外れ | 黙り |','|---|---|---|---:|---:|---:|---:|']
    for mode,a in aggregate.items():
        for cue,label in [('e','例外'),('n','通常')]:
            n=a['doors'][cue]
            lines.append(f"| C | {'あり' if mode=='recvA' else 'なし'} | {label} | {n.get('課題',0)} | {n.get('正解',0)} | {n.get('誤答',0)} | {n.get('棄権',0)} |")
    lines+=['','| 集団の種 | 通信 | 例外：課題/正解/外れ/黙り | 通常：課題/正解/外れ/黙り |','|---:|---|---|---|']
    for p in pops:
        vals=['/'.join(str(p['doors'][c].get(k,0)) for k in ('課題','正解','誤答','棄権')) for c in ('e','n')]
        lines.append(f"| {p['group_seed']} | {'あり' if p['mode']=='recvA' else 'なし'} | {vals[0]} | {vals[1]} |")
    lines+=['','### 例外の場面から来た束','',
            '束は、答えた人が送る関係のまとまり。例外由来は送信元の実場面が例外だった束。取り込みは受信結果が同化または誕生。使用は受信先の定義が後の世界の予測で選ばれたこと。回答した割合も別に示す。語り継ぎは同じ定義から後の試行で再び送ったこと。',
            '各受信を一件とし、その後に一回以上あれば一件と数える。同じ定義に複数の束が取り込まれた場合は各受信を別々に数える。定義の名前と生まれた試行で追跡する。','',
            '| 通信 | 例外由来/全送信 | 取り込み/例外由来 | 使用/取り込み | 回答/取り込み | 語り継ぎ/取り込み |',
            '|---|---|---|---|---|---|']
    def flow(label,f):
        n=f.get('例外由来',0);inc=f.get('例外由来の取り込み',0)
        vals=[fraction(n,f.get('送信',0)),fraction(inc,n)]+[fraction(f.get(k,0),inc) for k in ('取り込んだ定義が世界で使われた','取り込んだ定義が世界で回答した','取り込んだ定義が再伝達された')]
        return '| '+label+' | '+' | '.join(vals)+' |'
    for mode,a in aggregate.items(): lines.append(flow('あり' if mode=='recvA' else 'なし',a['exception_flow']))
    lines+=['','| 集団の種・通信 | 例外由来/全送信 | 取り込み/例外由来 | 使用/取り込み | 回答/取り込み | 語り継ぎ/取り込み |','|---|---|---|---|---|---|']
    for p in pops: lines.append(flow(f"{p['group_seed']}・{'あり' if p['mode']=='recvA' else 'なし'}",p['exception_flow']))
    lines+=['','### 例外由来の受信先が残り、選ばれなかった外れ','',
            '受信先は例外由来の束を同化した定義、またはそこから生まれた定義。同じ名前・誕生試行の定義が予測直前の記憶にあり、R_used（選ばれた定義の名）と異なる場合を数える。同じ試行に複数あっても外れ一件と数える。その定義が今正しく答えられるかは、この件数では判定していない。',
            '予測直前の記憶は前試行の終了時（その試行の受信後）の控え。一行ずつ差分を戻し、全行で記憶の指紋sha256（記録の内容から計算する照合用の値）を台帳と一致させる。当該試行で受信した束は、その予測には数えない。受信後に同化して中身が変わっても、名前・誕生試行が同じ間は同じ受信先として追跡。','',
            '| 通信 | 全課題の外れ | 例外由来を取り込んだ後の外れ | 受信先が記憶にある外れ | 受信先が記憶にあり未選択の外れ | 例外ドアで未選択/例外ドアの外れ |','|---|---:|---:|---:|---:|---|']
    for mode,a in aggregate.items():
        u=a['unselected']
        lines.append(f"| {'あり' if mode=='recvA' else 'なし'} | {u.get('誤答',0)} | {u.get('例外由来を取り込んだ後の誤答',0)} | {u.get('例外由来の受信先が記憶にある誤答',0)} | {u.get('例外由来の受信先が記憶にあり未選択の誤答',0)} | {fraction(u.get('例外ドアで受信先が記憶にあり未選択の誤答',0),u.get('例外ドアの誤答',0))} |")
    lines+=['','### 全世界課題と保存','',
            'Fは固定の名前からの答え、Hは席の名前と回数の履歴からの答え、Uは忘れた席の既定値からの答え。','',
            '| 通信 | 課題 | 正解 | 外れ | 黙り | 外れF | 外れH | 外れU |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for mode,a in aggregate.items():
        n=a['numbers'];vals=[str(n.get(k,0)) for k in ('課題','正解','誤答','棄権','誤答_F','誤答_H','誤答_U')]
        lines.append('| '+('あり' if mode=='recvA' else 'なし')+' | '+' | '.join(vals)+' |')
    lines+=['',f"完了した{len(pops)}集団で、個体の課題数＝正解＋誤答＋棄権、誤答の出どころの和、送信＝配達＝受信、束の予測と実際の答えが一致。受信で通常の採点・価値が変わった件と記憶費用の見積りとの差は0。",
            f"保存先：mac/collective20_20261002/C/。全数表、各受信の追跡、未選択の外れ一件ごとの記録、通信と答えごとの元記録、旗・実行引数、メモリ・熱・スワップの観測、台帳の指紋と場所、集計の道具を保存。台帳は{ROOT/'outputs_C'}に全て保持。",'']
    REPORT.write_text('\n'.join(lines)+'\n')
    return {'complete':complete,'populations':len(pops),'tasks':sum(p['common']['数']['課題'] for p in pops)}
if __name__=='__main__': print(json.dumps(main(),ensure_ascii=False))
