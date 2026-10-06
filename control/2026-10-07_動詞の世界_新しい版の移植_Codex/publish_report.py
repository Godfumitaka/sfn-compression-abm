"""承認済みの報告枝へ、動詞移植の計画と受け箱確認を通常pushする。"""
from pathlib import Path
import fcntl
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'source/tools/verb'))
import night
NAME='2026-10-07_動詞の世界_新しい版の移植_Codex'
REPORT='control/'+NAME+'.md'
PATHS=[REPORT,'control/'+NAME,'control/2026-10-06_動詞の世界_SME版_Codex.md',
       'control/受け箱/動詞の世界の係.md','control/走行の列_2026-10-08.md']

def push():
    for _ in range(3):
        night.fetch_report()
        night.scan_range(night.REPORT_REPO,night.REPORT_BRANCH,'origin/'+night.REPORT_BRANCH)
        r=subprocess.run(['git','-c','core.commitGraph=false','push','--no-follow-tags','origin',
                          'refs/heads/results-2026-09-27:refs/heads/results-2026-09-27'],cwd=night.REPORT_REPO)
        if r.returncode==0:
            return night.git(night.REPORT_REPO,'rev-parse','HEAD')
    raise RuntimeError('通常pushが通らなかった')

lockpath=ROOT.parent.parent/'codex_sme_light_2026-10-04/control_writer_01.lock'
with lockpath.open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    night.fetch_report()
    for mode in ((),('--push',)):
        assert night.git(night.SOURCE,'remote','get-url',*mode,'origin')==night.DESTINATION
    night.checked_git(night.SOURCE,'fetch','--no-tags','origin',
                      'refs/heads/'+night.WORK_BRANCH+':refs/remotes/origin/'+night.WORK_BRANCH)
    assert night.git(night.SOURCE,'status','--porcelain')==''
    assert night.git(night.SOURCE,'rev-parse','HEAD')=='7f48b75badd3854616449d9ab6464ccbb5f7b011'
    assert night.git(night.SOURCE,'rev-parse','origin/'+night.WORK_BRANCH)==night.git(night.SOURCE,'rev-parse','HEAD')
    night.scan_range(night.SOURCE,night.WORK_BRANCH,'origin/'+night.WORK_BRANCH)
    night.checked_git(night.REPORT_REPO,'add','--',*PATHS)
    night.checked_git(night.REPORT_REPO,'commit','-m',sys.argv[1])
    sha=push()
    report=night.REPORT_REPO/REPORT
    report.write_text(report.read_text()+f'\n送信確認（{night.now()}）：`results-2026-09-27`の`{sha}`を承認済みのGodfumitaka/sfn-compression-abmへ通常pushした。旧作業枝`codex/verb-world-2026-10-04`は`7f48b75badd3854616449d9ab6464ccbb5f7b011`でoriginと一致し、送信コミット0・変更ファイル0。新しいSME作業枝は送信していない。この確認の追記も同じ報告枝へpushする。\n')
    night.checked_git(night.REPORT_REPO,'add','--',REPORT)
    night.checked_git(night.REPORT_REPO,'commit','-m','動詞の新しい版の準備報告の送信済みコミットを追記')
    final=push()
    with (ROOT/'pushes.jsonl').open('a') as out:
        out.write(json.dumps({'at':night.now(),'first':sha,'confirmation':final,'branch':night.REPORT_BRANCH})+'\n')
    print(final,flush=True)
