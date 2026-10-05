"""指定された報告と証拠だけを、他の公開処理と同じロックで保存する。"""
from pathlib import Path
import fcntl
import shutil
import subprocess

ROOT=Path(__file__).resolve().parent
PRIOR=ROOT.parent/'codex_seal_intervention_2026-10-04'
REPO=PRIOR/'github_report'
NAME='2026-10-05_腕Lのシールと記憶の量_Codex'

def git(*args):
    return subprocess.check_output(['git',*args],cwd=REPO,text=True,stderr=subprocess.STDOUT)

with (PRIOR/'publish.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    print(git('pull','--rebase','origin','results-2026-09-27'))
    print(git('sparse-checkout','add','/control/'+NAME+'.md','/control/'+NAME+'/'))
    dest=REPO/'control'/NAME
    dest.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/(NAME+'.md'),REPO/'control'/(NAME+'.md'))
    for path in (ROOT/'public').iterdir():
        assert path.is_file()
        shutil.copyfile(path,dest/path.name)
    print(git('add','--sparse','--','control/'+NAME+'.md','control/'+NAME))
    if git('diff','--cached','--name-only').strip():
        print(git('commit','-m','腕Lのシールと記憶量の記録診断を報告する'))
        for attempt in range(3):
            try:
                print(git('push','origin','results-2026-09-27'))
                break
            except subprocess.CalledProcessError as exc:
                if attempt==2 or not any(x in exc.output for x in ('non-fast-forward','fetch first')):
                    raise
                print(git('pull','--rebase','origin','results-2026-09-27'))
    print(git('rev-parse','HEAD'))
