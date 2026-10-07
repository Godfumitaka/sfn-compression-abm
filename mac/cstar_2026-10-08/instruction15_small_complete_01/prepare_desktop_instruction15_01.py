"""デスクトップの作業場所に合わせて全長5条件の命令を作る。模型は起動しない。"""
from pathlib import Path
from datetime import datetime
import argparse, hashlib, json, shlex, subprocess

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--original-source',required=True,type=Path)
parser.add_argument('--fast-source',required=True,type=Path)
parser.add_argument('--output-root',required=True,type=Path)
parser.add_argument('--python',required=True,type=Path)
parser.add_argument('--helpers',required=True,type=Path)
a=parser.parse_args()
HERE=Path(__file__).resolve().parent
plan=json.loads((HERE/'desktop_plan_instruction15_01.json').read_text())
assert a.python.exists() and a.helpers.is_dir()
assert not a.output_root.exists(), '途中・完了の出力先を上書きしない'
for source,commit in ((a.original_source,plan['original_commit']),(a.fast_source,plan['fast_commit'])):
    assert source.is_dir()
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==commit
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=source).strip(), '汚れた作業場所。解決しない'
for name,digest in plan['helpers_sha256'].items():
    assert hashlib.sha256((a.helpers/name).read_bytes()).hexdigest()==digest, '観測又は比較の台本の版が異なる'
a.output_root.mkdir(parents=True)
commands=[]
for item in plan['cases']:
    case=a.output_root/item['name'];case.mkdir()
    source=a.original_source if item['name']=='original_C' else a.fast_source
    native=[str(a.python),*plan['native_arguments']]
    native[3]=str(case/'output')
    native+=item['flags']
    command_json=case/'native_command.json'
    command_json.write_text(json.dumps(native,ensure_ascii=False,indent=2)+'\n')
    invoke=['env','-u','LC_ALL','-u','LANG','-u','LC_CTYPE','PYTHONHASHSEED=0',
            'SME_EXACT_SOURCE='+str(source),str(a.python),str(a.helpers/'observe_cpu_01.py'),str(command_json)]
    commands.append(dict(case=item['name'],cwd=str(source),command=invoke,native_command=native,
                         memory_claim_gb=11,disk_path=str(case),receipt_required=True,
                         deadline='2026-10-09T09:00:00+09:00'))
manifest=dict(at=datetime.now().astimezone().isoformat(),commands=commands,models_started=0,
              order='原版、作業版の旗なし、GCだけ、encodeだけ、両方の順。各本をデスクトップの受付と資源監督に通し、一つでも不通・不一致なら次を始めない。',
              cpu_method='同じ外付けworker CPUとGC callback。cProfileは使わず、GCは総CPUの内訳。',
              deadline_rule='各模型の開始前に期限を確認。期限を理由に既に動く本を止めない。')
(a.output_root/'commands.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('模型は起動していない。各行をデスクトップの受付と資源監督に通す。')
for c in commands:
    print(c['case']+'：cwd='+str(c['cwd'])+'、見込み11GB、出力先='+c['disk_path'])
    print(shlex.join(c['command']))
print('各本の終了後、原版のoutputと各旗のoutputをcompare_cli_instruction15_01.pyで全バイト比較。CPUは各条件のwhole_cpu.json。')
