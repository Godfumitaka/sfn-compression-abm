"""確定したコードの指紋と、各処理の実行版を別々に保存する。"""
import ast
import csv
import hashlib
import json
import shutil
import subprocess
from stage1 import ROOT,SRC

PACKAGE='tools/logp_seals_diag_2026_10_05'
BASE='2ee8eccf1b5c9cf0d7101aa059a1c07b37a80348'

def git(*a):return subprocess.check_output(['git',*a],cwd=SRC)

def main():
    head=git('rev-parse','HEAD').decode().strip();rows=[]
    for path in sorted((SRC/PACKAGE).iterdir()):
        if not path.is_file():continue
        if path.suffix=='.py':ast.parse(path.read_text(),filename=str(path))
        data=path.read_bytes();same=data==(ROOT/path.name).read_bytes();assert same,path
        rows.append({'name':path.name,'workspace_path':str(ROOT/path.name),'archive_path':str(path),
                     'sha256':hashlib.sha256(data).hexdigest(),'same_bytes':same})
    changes=git('diff','--name-status',BASE,'HEAD').decode().splitlines()
    assert all(r.startswith('A\t') for r in changes),changes
    check={'models_match_pre_task_commit':True,'base_commit':BASE,'diagnostic_commit':head,'changed_files':changes,
           'diagnostic_syntax_ok':True,'final_workspace_archive_bytes_equal':True}
    (ROOT/'code_check.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
    shutil.copyfile(ROOT/'code_check.json',ROOT/'public/code_check.json')
    with (ROOT/'public/diagnostic_code_sha256.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    refs={
        'a7e099c67a2af2752d401151a415a5a0d92bda2e':['inspect_records.py','preflight.py','stage1.py','priority.py','stage2.py','silent_candidates.py'],
        'fb501b26d2408a3cb22a7c2ace13a2afddc9663a':['counts14.py','birth_score_conditions.py','append_conditions_report.py'],
        '3c0951b5':['selected_seals.py'],
        head:['aggregate.py','append_complete_report.py','repair_birth_labels.py'],
        '08bd1b3b2e6985550d7c89bbcc671ccc2f1d9732':['publish_report.py','append_priority_report.py']}
    versions=[]
    for ref,names in refs.items():
        commit=git('rev-parse',ref).decode().strip()
        for name in names:
            data=git('show',commit+':'+PACKAGE+'/'+name)
            versions.append({'script':name,'execution_version_commit':commit,'repository_path':PACKAGE+'/'+name,
                             'sha256':hashlib.sha256(data).hexdigest(),
                             'same_as_final_workspace':data==(ROOT/name).read_bytes()})
    info={'versions':versions,'final_archive_commit':head,
          'notes':['初回stage2.pyはa7e099c6で誕生・記憶の表を作成。選択欄はselected_seals.pyで台帳とsideを全件照合して両欄を明示した。',
                   'silent_candidates.pyの初回実行版はa7e099c6。実行後に三つの再現チェックが全件0であることを確認し、summaryの説明だけを条件付きの表現に訂正した。',
                   '最終版のstage2.pyとsilent_candidates.pyの追加検証は保存されている。元の模型、照合、既存分類は変更しない。']}
    (ROOT/'public/execution_code_versions.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
    for name in ('stage1_summary.json','stage2_summary.json','silent_candidates_summary.json','selected_seals_summary.json',
                 'aggregate_summary.json','birth_score_conditions_check.json','birth_label_repair_check.json','birth_label_repair_files.json'):
        shutil.copyfile(ROOT/name,ROOT/'public'/name)
    print(json.dumps({'commit':head,'archived_files':len(rows),'recorded_versions':len(versions),'model_changes':0},ensure_ascii=False))

if __name__=='__main__':main()
