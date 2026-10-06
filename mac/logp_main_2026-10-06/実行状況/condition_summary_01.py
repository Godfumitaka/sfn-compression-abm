"""20本の完了記録から、条件の表と全ファイルのsha256を作る。"""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,sys
ROOT=Path(__file__).resolve().parent;arm=sys.argv[1]
plan=[x for x in json.loads((ROOT/'sme.commands.json').read_text()) if x['arm']==arm]
assert [x['seed'] for x in plan]==list(range(1,21))
def rawhash(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b)
    return h.hexdigest()
summaries=[];proofs=[]
for x in plan:
    f=Path(x['folder']);assert json.loads((f/'analysis_complete.json').read_text())['passed']
    summary=json.loads((f/'summary.json').read_text());assert summary['trials']==1740
    assert summary['prediction_and_selection_mismatches']==0
    summaries.append(summary)
    files=sorted(p for p in f.rglob('*') if p.is_file() and p.name!='all_files_sha256.json')
    hashes=json.loads((f/'artifacts_sha256.json').read_text())
    # native/analysisは全ファイル、管理ファイルはこの完了時点の写し。索引自身だけを含めない。
    index={'index_excluded_from_own_hash':True,'ledger_body_sha256':hashes['ledger_body_sha256'],'original_output':hashes['original_output'],'analysis_output':hashes['analysis_output'],'native_all_files':hashes['files'],'analysis_all_files':hashes['analysis_files'],'case_management_files':{str(p.relative_to(f)):rawhash(p) for p in files if 'output' not in p.relative_to(f).parts and 'analysis_output' not in p.relative_to(f).parts}}
    (f/'all_files_sha256.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
rows=[f'{arm}：20本、各1740試行。種1〜20は全部マック。同じ1838256と同じ旗で実行。保存状態の再解析は、全予測・全更新が本物と一致。', '', '|種|日|全課題 正解/外れ/黙り|ドア 正解/外れ/黙り|ドア 選び間違い/区別の喪失|記憶総ビット 平均/最後|定義数 平均/最後|実時間秒|最大常駐MB|','|---:|---|---|---|---|---|---|---:|---:|']
totals={'e':Counter(),'n':Counter()};alltotals={'e':Counter(),'n':Counter()};births=defaultdict(Counter)
for s in summaries:
    for cue,day in [('e','例外'),('n','通常')]:
        d=s['days'][cue];a=s['all_task_days'][cue];totals[cue].update(d);alltotals[cue].update(a)
        triple=lambda c:'/'.join(str(c.get(k,0)) for k in ('正解','外れ','黙り'))
        rows.append(f"|{s['seed']}|{day}|{triple(a)}|{triple(d)}|{d.get('選び間違い',0)}/{d.get('区別の喪失',0)}|{s['memory_bits_mean']:.6f}/{s['memory_bits_final']}|{s['definitions_mean']:.6f}/{s['definitions_final']}|{s['wall_seconds']:.3f}|{s['peak_rss_mb']}|")
    for group in s['birth_groups']:
        births[(group['base_day'],group['current_day'])].update({k:v for k,v in group.items() if k not in ('base_day','current_day')})
rows+=['','|20種合計の日|全課題 正解/外れ/黙り|ドア 正解/外れ/黙り|全課題 選び間違い/区別の喪失|ドア 選び間違い/区別の喪失|','|---|---|---|---|---|']
for cue,day in [('e','例外'),('n','通常')]:
    a=alltotals[cue];d=totals[cue]
    rows.append(f"|{day}|{triple(a)}|{triple(d)}|{a['選び間違い']}/{a['区別の喪失']}|{d['選び間違い']}/{d['区別の喪失']}|")
rows+=['','選び間違いは、予測時点の別の候補が門を通って正しく答えられた外れ。区別の喪失は、そのような候補が無かった外れ。前のL_Bの表と同じtools/selcands_sme.pyの定義。', '', '|材料の二場面（基/今）|誕生数|シール席あり定義数|誕生直後F/H/U|同試行の忘却後F/H/U|同試行に退役したシール席|','|---|---:|---:|---|---|---:|']
for k,c in sorted(births.items()):
    before='/'.join(str(c['登録直後_'+s]) for s in ('F','H','U'));after='/'.join(str(c['同試行の忘却後_'+s]) for s in ('F','H','U'))
    rows.append(f"|{k[0]}/{k[1]}|{c['誕生数']}|{c['シール席ありの定義数']}|{before}|{after}|{c['同試行の忘却後_定義が同じ試行に退役']}|")
rows+=['','eは例外の日、nは通常の日。Fは固定の名、Hは名と回数の履歴、Uは中身を忘れた席。誕生直後はregistration_event、忘却後は同じ試行のpost状態で数える。', '', '全ファイルのsha256は各種のartifacts_sha256.json・all_files_sha256.json。大きな台帳・side・保存状態は記載のマックの出力先に全部保持し、結果枝には試行表・分類と数・命令・sha256を上げる。sha256はファイルの内容を照合する印。索引自身は自分のsha256に含めず、アップロード時のsha256.jsonに残す。実測の時間は一致比較からだけ除外し、値は表に残す。']
(ROOT/(arm+'.md')).write_text('\n'.join(rows)+'\n')
(ROOT/(arm+'_summary.json')).write_text(json.dumps({'arm':arm,'runs':20,'trials':34800,'days':totals,'all_task_days':alltotals,'birth_groups':[{'base_day':k[0],'current_day':k[1],**c} for k,c in sorted(births.items())],'seeds':summaries,'model_changed':False},ensure_ascii=False,indent=2)+'\n')
print(arm,'20本の集計完了',flush=True)
