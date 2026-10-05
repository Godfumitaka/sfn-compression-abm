"""承認済みマック再作成の進捗・完了CSVを、既報へ追記する。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
import csv,fcntl,json,shutil,subprocess,time
import seal_mac_intervention as diag

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'mac_rebuild_approved_2026-10-05'
REPO=ROOT/'github_report'
NAME='2026-10-05_探索の腕と介入_Codex'
DOC=REPO/'control'/(NAME+'.md')
EVIDENCE=REPO/'control'/(NAME+'_証拠')/'マックでの作り直し_1005'

def read(path):return json.loads(path.read_text()) if path.exists() else {}
def git(*args):return subprocess.check_output(['git',*args],cwd=REPO,text=True,stderr=subprocess.STDOUT)
def copy(path,name):
    target=EVIDENCE/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    return f'[{name}]({NAME}_証拠/マックでの作り直し_1005/{name})'

def append_arm(lines,relative,entry):
    name=Path(relative).name;dest=Path(entry['analysis_root']);d=read(dest/'summary.json');c=d['counts']
    if not d['all_seeds_passed'] or not d['input_files_unchanged']:raise RuntimeError('完了材料・入力保持の証拠が無い')
    lines += [f'### {name} — {diag.LABEL}','',
              f'世界{d["world"]}・保持{d["mode"]}・λ={d["lambda_"]}・選び方={d["selector"]}。種1〜20の全34800試行で新しい二関門を通過。全ドア{d["all_door_rows"]}件の予測と元の記憶の保持を照合。元の台帳本体は未照合。','',
              f'| 日 — {diag.LABEL} | 正解 | 外れ | 黙り | 選び間違い | 区別の喪失 |',
              '|---|---:|---:|---:|---:|---:|']
    for cue,label in [('e','例外の日'),('n','通常の日')]:
        values=[c.get('door_'+cue+'_'+k,0) for k in ('正解','外れ','黙り')]
        values += [c.get(k+'_'+cue,0) for k in ('selection_mistake','distinction_loss')]
        if values[1]!=values[3]+values[4]:raise RuntimeError('外れの分類の和が一致しない')
        lines.append('| '+label+' | '+' | '.join(map(str,values))+' |')
    lines += ['',f'| 元の条件と答え — {diag.LABEL} | 条件復元で正解 | 外れ | 黙り | 未復元 |','|---|---:|---:|---:|---:|']
    for day,label in [('e','例外'),('n','通常')]:
        for outcome in ('正解','外れ','黙り'):
            lines.append('| '+label+'・'+outcome+' | '+' | '.join(str(c.get('i_'+day+'_'+outcome+'_to_'+x,0)) for x in ('正解','外れ','黙り','未復元'))+' |')
    lines += ['',f'| 方法（全ドア）— {diag.LABEL} | 正解 | 外れ | 黙り | 材料なし | 誕生なし | 追加定義を選択 | 追加定義を選ばず外れ |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for method in ('iii_a','iii_b','iii_c'):
        keys=[method+'_'+x for x in ('正解','外れ','黙り','no_material','no_birth','added_selected','added_not_selected_wrong')]
        lines.append('| '+method+' | '+' | '.join(str(c.get(k,0)) if method!='iii_a' or i<3 else '—' for i,k in enumerate(keys))+' |')
    with (dest/'exception_wrong.csv').open(newline='') as stream:focused=list(csv.DictReader(stream))
    lines += ['',f'| 例外の外れの分類 — {diag.LABEL} | 方法 | 対象 | 正解 | 外れ | 黙り | 材料なし | 誕生なし | 未復元 | 未適用 |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for cls,label in [('selection_mistake','選び間違い'),('distinction_loss','区別の喪失')]:
        subset=[r for r in focused if r['classification']==cls]
        for method in ('condition_birth','researcher_selection','iii_a','iii_b','iii_c'):
            tallies=Counter()
            for row in subset:
                status=row[method+'_status'];value=status if status in ('材料なし','誕生なし','未復元') else row[method+'_outcome']
                if not value:value='未適用'
                tallies[value]+=1
            if sum(tallies.values())!=len(subset):raise RuntimeError('介入表の分母が不一致')
            lines.append('| '+label+' | '+method+' | '+str(len(subset))+' | '+' | '.join(str(tallies[k]) for k in ('正解','外れ','黙り','材料なし','誕生なし','未復元','未適用'))+' |')
    lines += ['', '研究者の選び直しは正解候補がある外れにだけ適用し、候補がない行の空欄は未適用である。iii-a/b/cの全ドア集計と、例外の外れに限った表は分母を区別する。','']
    for filename in ('all_doors.csv','exception_wrong.csv','summary.json','material_gates.csv','input_sha256.csv','mac_checks.json'):
        lines.append('- '+copy(dest/filename,name+'/'+filename))
    if entry.get('R_root'):
        rdest=Path(entry['R_root']);r=read(rdest/'summary.json')
        lines += ['',f'#### 腕R — {diag.LABEL}','',f'| 日・選び方 — {diag.LABEL} | 正解 | 外れ | 黙り | 選び間違い | 区別の喪失 |','|---|---:|---:|---:|---:|---:|']
        for day,label in [('e','例外の日'),('n','通常の日')]:
            for rule in ('今の規則','N3','r'):
                values=r['days'][day][rule]
                lines.append('| '+label+'・'+rule+' | '+' | '.join(str(values.get(k,0)) for k in ('正解','外れ','黙り','選び間違い','区別の喪失'))+' |')
        lines += ['', '- '+copy(rdest/'all_doors.csv',name+'/R/all_doors.csv'),'- '+copy(rdest/'summary.json',name+'/R/summary.json')]
    lines.append('')

def comparison(lines,state):
    rows=[]
    targets=('f_grid/fg_f050_A_L50','f_grid/fg_f050_C_L50','lambda_grid/lg_w2_A_lam0.065')
    for arm in targets:
        entry=state['arms'].get(arm,{})
        if entry.get('phase')!='complete':continue
        dest=Path(entry['analysis_root']);d=read(dest/'summary.json');c=d['counts'];loss=Counter()
        with (dest/'exception_wrong.csv').open(newline='') as stream:
            for row in csv.DictReader(stream):
                if row['classification']!='distinction_loss':continue
                for method in ('iii_a','iii_b','iii_c'):
                    status=row[method+'_status'];value=status if status in ('材料なし','誕生なし') else row[method+'_outcome']
                    loss[method+'_'+value]+=1
        denominator=c.get('exception_wrong',0)-c.get('exception_unrestored',0)
        row={'arm':Path(arm).name,'world':d['world'],'mode':d['mode'],'lambda':d['lambda_'],'selector':d['selector'],
             'exception_wrong':c.get('exception_wrong',0),'i_usable_wrong':denominator,'i_correct':c.get('i_正解',0),
             'i_correct_fraction':c.get('i_正解',0)/denominator if denominator else None,
             'i_correct_selection_mistake':c.get('i_correct_selection_mistake',0),
             'i_correct_distinction_loss':c.get('i_correct_distinction_loss',0),
             'i_unrestored':c.get('exception_unrestored',0),'normal_correct':c.get('normal_correct',0),
             'normal_changed_wrong':c.get('normal_changed_外れ',0),'normal_changed_silent':c.get('normal_changed_黙り',0),
             'distinction_loss_wrong':c.get('distinction_loss_e',0),'iii_a_correct_in_loss':loss['iii_a_正解'],
             'iii_b_correct_in_loss':loss['iii_b_正解'],'iii_c_correct_in_loss':loss['iii_c_正解'],
             'iii_c_no_material_in_loss':loss['iii_c_材料なし'],'iii_c_no_birth_in_loss':loss['iii_c_誕生なし'],'material':diag.LABEL}
        rows.append(row)
    if not rows:return
    with (OUT/'intervention_comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines += ['',f'### 当初の介入3腕の比較 — {diag.LABEL}','',
              f'| 腕・世界・保持・λ — {diag.LABEL} | 例外の外れ | (i)適用可能 | (i)正解 | 適用可能外れに対する割合 | 正解になった選び間違い | 正解になった区別の喪失 | 通常の正解から外れ・黙り |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        frac='—' if r['i_correct_fraction'] is None else f'{r["i_correct_fraction"]:.6f}'
        lines.append('| '+r['arm']+f'・世界{r["world"]}・{r["mode"]}・{r["lambda"]} | '+
                     ' | '.join(map(str,[r['exception_wrong'],r['i_usable_wrong'],r['i_correct'],frac,r['i_correct_selection_mistake'],r['i_correct_distinction_loss'],r['normal_changed_wrong']+r['normal_changed_silent']]))+' |')
    lines += ['', '割合の分母は未復元を除く例外の日の外れ。未復元件数、通常の日の変化の外れ／黙り内訳、区別の喪失に限ったiii-a/b/cと材料不足はCSVに併記。Aのλ主と0.065は同じ世界・選び方で並べ、Cは保持方法の異なる条件として表示する。未完了の腕はこの表に入れない。','',
              '- '+copy(OUT/'intervention_comparison.csv','介入3腕の比較.csv'),'']

def publish():
    with (ROOT/'publish.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        memo=read(OUT/'published.json') or {'initial':False,'arms':[],'errors':{},'final':False}
        state=read(OUT/'status.json')
        done=[arm for arm,entry in state['arms'].items() if entry['phase']=='complete' and arm not in memo['arms']]
        errors={arm:e['error'] for arm,e in state['arms'].items() if e.get('error')}
        final=state['phase'] in ('complete','stopped') and not memo['final']
        if memo['initial'] and not (done or errors!=memo['errors'] or final):return
        git('pull','--rebase','origin','results-2026-09-27')
        stamp=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
        lines=['',f'## マック再作成の承認後の追記 {stamp}','',diag.LABEL+'。元の台帳本体との一致は主張しない。デスクトップの160本終了後の別依頼による本体照合は未実施。','']
        if not memo['initial']:
            lines += ['委任者の新指示に従い、従来の本体SHA256不一致で止まった9腕を再開する。新関門は公開11列試行表との全行一致と、台帳のfull/deltaを当て直した状態指紋の全試行内部一致。旧関門の停止記録・欠測表は履歴として残し、以後はこの承認に基づく材料を使う。','',
                      '既存の完了種は新関門で検証して再利用し、残りの種だけ3380344・元の旗で作る。種1〜20だけ。各腕の全20種が関門を通ったら、全ドアの条件復元・研究者選び直し・iii-a/b/cを読むだけで解析する。入力材料は解析前後の指紋で保持を確認する。模型本体・照合・分類・L-BEの進行を変えない。','',
                      '重い処理はすべて jobs.py run --wait --mem --disk-path で受付に通す。材料は各0.4 GB、介入は各0.6 GB、集計は0.25 GB。旧実測（材料の種1の約8分）による全体の目安は数時間から半日で、受付・CPU競合により変動する。','',
                      'コード版：`'+state['code_commit']+'`。CSVの鍵はarm・world・seed・trial（trialは0始まり）。全行に材料の表示を付ける。','']
            lines.append(copy(ROOT/'source/control/seal_intervention_diag_2026-10-04.md','仕様.md'))
            lines.append(copy(ROOT/'gates/mac_gate_tests_2026-10-05.log','構造17検証.txt'))
            if (ROOT/'gates/mac_pilot_2026-10-05.log').exists():lines.append(copy(ROOT/'gates/mac_pilot_2026-10-05.log','lg種1_接続確認.txt'))
            memo['initial']=True
        for arm in done:
            append_arm(lines,arm,state['arms'][arm]);memo['arms'].append(arm)
        if done or final:comparison(lines,state)
        if errors:
            for arm,error in errors.items():
                if memo['errors'].get(arm)!=error:lines += [f'新関門または解析の停止：{arm}、`{error}`。当該腕の後続は停止。','']
        lines += [f'| 腕 — {diag.LABEL} | 新関門を通過した種 | 解析した種 | 状態 |','|---|---:|---:|---|']
        from seal_memory_rebuild import ARMS
        for arm in ARMS:
            e=state['arms'].get(arm,{})
            lines.append('| '+arm+' | '+str(len(e.get('gate_seeds',[])))+'/20 | '+str(len(e.get('analysis_seeds',[])))+'/20 | '+e.get('phase','待機')+' |')
        lines += ['', '- '+copy(OUT/'status.json','進捗.json')]
        if (OUT/'commands.jsonl').exists():lines.append('- '+copy(OUT/'commands.jsonl','実行コマンド.jsonl'))
        if final:lines += ['', '再作成・介入の処理の最終状態：'+state['phase']+'。結果の良し悪しの評価は記載しない。'];memo['final']=True
        DOC.write_text(DOC.read_text()+'\n'.join(lines)+'\n')
        git('add','--sparse','control/'+NAME+'.md','control/'+NAME+'_証拠/マックでの作り直し_1005')
        git('commit','-m','マック再作成の承認後の関門・介入の進捗を追記する')
        for attempt in range(4):
            try:git('push','origin','HEAD:results-2026-09-27');break
            except subprocess.CalledProcessError:
                if attempt==3:raise
                git('pull','--rebase','origin','results-2026-09-27')
        memo.update(errors=errors,last_time=stamp,report_commit=git('rev-parse','HEAD').strip())
        (OUT/'published.json').write_text(json.dumps(memo,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(memo,ensure_ascii=False),flush=True)

if __name__=='__main__':publish()
