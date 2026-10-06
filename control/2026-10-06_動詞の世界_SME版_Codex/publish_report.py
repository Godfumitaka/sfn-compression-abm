"""承認済みの宛先・報告枝だけを検査してpushする。新しいSME枝は送らない。"""
from pathlib import Path
import json
import subprocess
import sys

root=Path(__file__).resolve().parent
sys.path.insert(0,str(root.parent/'source/tools/verb'))
import night
name='2026-10-06_動詞の世界_SME版_Codex'
report=f'control/{name}.md'

def push():
    for _ in range(3):
        night.fetch_report()
        night.scan_range(night.REPORT_REPO,night.REPORT_BRANCH,'origin/'+night.REPORT_BRANCH)
        result=subprocess.run(['git','-c','core.commitGraph=false','push','--no-follow-tags','origin',
              f'refs/heads/{night.REPORT_BRANCH}:refs/heads/{night.REPORT_BRANCH}'],cwd=night.REPORT_REPO)
        if result.returncode==0:
            return night.git(night.REPORT_REPO,'rev-parse','HEAD')
    raise RuntimeError('報告枝のpush不通')

night.fetch_report()
for mode in ((),('--push',)):
    assert night.git(night.SOURCE,'remote','get-url',*mode,'origin')==night.DESTINATION
night.checked_git(night.SOURCE,'fetch','--no-tags','origin',f'refs/heads/{night.WORK_BRANCH}:refs/remotes/origin/{night.WORK_BRANCH}')
assert night.git(night.SOURCE,'status','--porcelain')==''
assert night.git(night.SOURCE,'rev-parse','HEAD')=='7f48b75badd3854616449d9ab6464ccbb5f7b011'
assert night.git(night.SOURCE,'rev-parse','origin/'+night.WORK_BRANCH)==night.git(night.SOURCE,'rev-parse','HEAD')
night.scan_range(night.SOURCE,night.WORK_BRANCH,'origin/'+night.WORK_BRANCH)
night.checked_git(night.REPORT_REPO,'add','--',report,f'control/{name}')
night.checked_git(night.REPORT_REPO,'commit','-m',sys.argv[1])
sha=push()
p=night.REPORT_REPO/report
p.write_text(p.read_text()+f'\n送信確認（{night.now()}）：`{night.REPORT_BRANCH}`の`{sha}`を承認されたGitHub originへpushした。旧作業枝`{night.WORK_BRANCH}`は`7f48b75badd3854616449d9ab6464ccbb5f7b011`でoriginと一致し、今回の送信コミット0・変更ファイル0。新しいSME作業枝は送信していない。この確認の追記も同じ報告枝へpushする。\n')
night.checked_git(night.REPORT_REPO,'add','--',report)
night.checked_git(night.REPORT_REPO,'commit','-m','動詞SMEの報告の送信済みコミットを追記')
last=push()
with (root/'pushes.jsonl').open('a') as out:
    out.write(json.dumps({'time':night.now(),'first':sha,'confirmation':last,'branch':night.REPORT_BRANCH})+'\n')
print(last,flush=True)
