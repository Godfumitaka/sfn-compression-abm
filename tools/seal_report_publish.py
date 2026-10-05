"""完了した分類と介入の報告を、指定された一つのGitHubファイルへ追記する。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,csv,fcntl,hashlib,json,shutil,subprocess,time

ROOT=Path(__file__).resolve().parents[2]
EX=ROOT.parent/'codex_explore3_2026-10-04'
REPO=ROOT/'github_report'
NAME='2026-10-05_探索の腕と介入_Codex'
CONTROL=REPO/'control';DOCUMENT=CONTROL/(NAME+'.md');EVIDENCE=CONTROL/(NAME+'_証拠')
CHECKPOINT=ROOT/'published_checkpoint.json'

def read(path):return json.loads(path.read_text()) if path.exists() else {}
def git(*args):return subprocess.check_output(['git',*args],cwd=REPO,text=True,stderr=subprocess.STDOUT)
def copy(path,name):
    shutil.copyfile(path,EVIDENCE/name)
    return f'[{name}]({NAME}_証拠/{name})'

def publish(note=None):
    with (ROOT/'publish.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        memo=read(CHECKPOINT) or {'arms':read(EX/'status.json').get('completed',[])[:8],'worlds':[],'rebuild':[],'initial':False}
        status=read(EX/'status.json');arms=[x for x in status.get('completed',[]) if x not in memo['arms']]
        worlds=[w for w in (1,2) if (ROOT/f'attention_2026-10-05/w{w}/summary.json').exists() and w not in memo['worlds']]
        comparisons=sorted((ROOT/'memory_rebuild_2026-10-05').glob('*/seed*.comparison.json'))
        comparisons=[p for p in comparisons if str(p) not in memo['rebuild']]
        failure=str(status.get('error',''))
        if memo['initial'] and not (arms or worlds or comparisons or note or failure!=memo.get('explore_error','')):return False
        git('pull','--rebase','origin','results-2026-09-27')
        stamp=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
        lines=['',f'## 追記 {stamp}','']
        if note:lines+=[note,'']
        if not memo['initial']:
            commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT/'source',text=True).strip()
            lines += [f'全ドア用の診断と再作成の道具を作業枝へ追加した（{commit}）。構造の13検証とCSV・厳密な照合の3検証が通過。模型本体の3380344との差分はない。', '',
                      '全ドアの(iii-a/b)は当該完全場面の全Fの一本を使う。通常の日には通常の当該場面を使い、反実仮想の例外場面を作らない。(iii-c)は全課題で、その店の過去の例外の日の最新二経験を使う。追加した定義はその課題の答え直しだけに用いる。','',
                      '世界2・種1の全157ドア課題で元の予測・状態の再現と原状態の保持を確認し、注意の追加診断の鍵と分類が一致した。入力11ファイルの指紋も解析前後で一致。これは40種の完了ではなく、残りを並列4・各0.6 GBで受付後に処理中。', '',
                      'CSVの鍵はworld・seed・trial（trialは0始まり）。元の答え・分類、condition_birth（10月4日の(i)）、研究者の選び直し、iii_a/b/cの答え・選択・材料不足を記録する。「3b」の名称の対応の確認は引き続き待っている。','']
            for path,name in [(ROOT/'gates/unit_tests_2026-10-05.log','介入_1005_13検証.txt'),(ROOT/'gates/batch_tests_2026-10-05.log','介入_1005_CSVと関門3検証.txt'),
                              (ROOT/'attention_2026-10-05/w2/seed001.join_check.json','介入_1005_種1結合確認.json'),(ROOT/'source/control/seal_intervention_diag_2026-10-04.md','介入_1005_仕様.md')]:
                lines.append('- '+copy(path,name))
            memo['initial']=True
        lines += ['',f'L/Tの分類まで完了した条件：{len(status.get("completed",[]))}/19。現在の段：{status.get("phase")}、腕：{status.get("arm") or "—"}。','']
        if failure:lines += ['走行または分類の停止理由：`'+failure+'`。','']
        for arm in arms:
            d=read(EX/'classification'/arm/'summary.json')
            assert d['seeds']==list(range(1,21)) and len(d['checks'])==20
            for c in d['checks']:
                assert c['対象']==c['作った試行']
                assert all(c[k]==0 for k in ('予測が本物と違う','一位が本物の選びと違う','一位でやり直した答えが本物と違う'))
            lines += [f'### {arm}','', '| 日 | 正解 | 外れ | 黙り | 選び間違い | 区別の喪失 |','|---|---:|---:|---:|---:|---:|']
            for cue,label in [('e','例外の日'),('n','通常の日')]:
                day=d['days'][cue];assert day['外れ']==day['選び間違い']+day['区別の喪失']
                lines.append('| '+label+' | '+' | '.join(str(day.get(k,0)) for k in ('正解','外れ','黙り','選び間違い','区別の喪失'))+' |')
            lines += ['',copy(EX/'classification'/arm/'summary.json','探索_'+arm+'_分類.json'),'']
            memo['arms'].append(arm)
        for world in worlds:
            dest=ROOT/f'attention_2026-10-05/w{world}';d=read(dest/'summary.json');c=d['counts']
            assert d['seeds']==list(range(1,21)) and d['input_files_unchanged'] and d['attention_keys_and_classifications_match']
            if world==2:assert d['exception_wrong_classes']=={'selection_mistake':136,'distinction_loss':43}
            lines += [f'### 注意の固定材料 世界{world} 全20種','',f'全ドア{d["all_door_rows"]}件。元の予測・記憶・原状態の保持、注意の段②・追加診断との鍵・外れの分類が全件一致。入力原本の指紋も全20種で一致。','',
                      '| 方法 | 正解 | 外れ | 黙り | 材料なし | 誕生なし | 追加定義を選択 | 追加定義を選ばず外れ |',
                      '|---|---:|---:|---:|---:|---:|---:|---:|']
            for method in ('iii_a','iii_b','iii_c'):
                ks=[method+'_'+x for x in ('正解','外れ','黙り','no_material','no_birth','added_selected','added_not_selected_wrong')]
                lines.append('| '+method+' | '+' | '.join(str(c.get(k,0)) if method!='iii_a' or i<3 else '—' for i,k in enumerate(ks))+' |')
            lines += ['', '| 元の条件と答え | 条件復元で正解 | 外れ | 黙り | 未復元 |','|---|---:|---:|---:|---:|']
            for day,label in [('e','例外'),('n','通常')]:
                for outcome in ('正解','外れ','黙り'):
                    lines.append('| '+label+'・'+outcome+' | '+' | '.join(str(c.get('i_'+day+'_'+outcome+'_to_'+x,0)) for x in ('正解','外れ','黙り','未復元'))+' |')
            lines += ['',f'例外ドアの元の外れ：{d["exception_wrong_rows"]}件、分類：{d["exception_wrong_classes"]}。','']
            lines += ['| 元の外れの分類 | 方法 | 対象 | 正解 | 外れ | 黙り | 材料なし | 誕生なし | 未復元 |',
                      '|---|---|---:|---:|---:|---:|---:|---:|---:|']
            with (dest/'exception_wrong.csv').open(newline='') as stream:focused=list(csv.DictReader(stream))
            for cls,label in [('selection_mistake','選び間違い'),('distinction_loss','区別の喪失')]:
                subset=[r for r in focused if r['classification']==cls]
                for method in ('condition_birth','iii_a','iii_b','iii_c'):
                    tallies={x:0 for x in ('正解','外れ','黙り','材料なし','誕生なし','未復元')}
                    for r in subset:
                        status=r[method+'_status']
                        value=status if status in ('材料なし','誕生なし','未復元') else r[method+'_outcome']
                        tallies[value]+=1
                    assert sum(tallies.values())==len(subset)
                    lines.append('| '+label+' | '+method+' | '+str(len(subset))+' | '+' | '.join(map(str,tallies.values()))+' |')
            lines.append('')
            for name in ('all_doors.csv','exception_wrong.csv','summary.json'):lines.append('- '+copy(dest/name,f'介入_w{world}_'+name))
            memo['worlds'].append(world)
        for p in comparisons:
            d=read(p)
            lines += ['',f'### 他腕の記憶の照合 {d["arm"]} 種{d["seed"]}','',
                      f'11列表の一致：{d["table_match"]}、異なる行：{d["different_table_rows"]}。台帳本体sha256の一致：{d["body_hash_match"]}。','',
                      f'再作成した本体：`{d["body_sha256"]}`。公開済みの本体：`{d["reference_body_sha256"]}`。','']
            if not (d['table_match'] and d['body_hash_match']):lines += ['両方の一致という関門を満たさないため、この再作成の続きは停止した。残りの種と他腕をこの材料で解析しない。原因はこの照合だけでは特定していない。','']
            lines.append(copy(p,'材料_'+p.parent.name+'_'+p.name));memo['rebuild'].append(str(p))
        DOCUMENT.write_text(DOCUMENT.read_text()+'\n'.join(lines)+'\n')
        git('add','--sparse','control/'+NAME+'.md','control/'+NAME+'_証拠')
        git('commit','-m','探索と介入の完了した分類・CSVと材料照合を追記する')
        for attempt in range(4):
            try:git('push','origin','HEAD:results-2026-09-27');break
            except subprocess.CalledProcessError:
                if attempt==3:raise
                git('pull','--rebase','origin','results-2026-09-27')
        memo['explore_error']=failure;memo['last_time']=stamp;memo['report_commit']=git('rev-parse','HEAD').strip()
        CHECKPOINT.write_text(json.dumps(memo,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(memo,ensure_ascii=False),flush=True);return True

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--watch',action='store_true');ap.add_argument('--note');a=ap.parse_args()
    publish(a.note)
    while a.watch:
        time.sleep(45)
        try:publish()
        except Exception as exc:print(repr(exc),flush=True)
        if (read(EX/'status.json').get('phase')=='complete_L_T'
            and read(ROOT/'attention_2026-10-05/status.json').get('phase')=='complete'
            and read(ROOT/'memory_rebuild_2026-10-05/status.json').get('phase') in ('complete_checks','failed')):break
