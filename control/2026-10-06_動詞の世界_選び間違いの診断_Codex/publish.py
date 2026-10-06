"""持ち主が承認したGitHubの二枝を検査し、指定の報告枝だけをpushする。"""
from pathlib import Path
import json
import subprocess
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
sys.path.insert(0, str(ROOT / 'source/tools/verb'))
import night

NAME = '2026-10-06_動詞の世界_選び間違いの診断_Codex'
REPORT = f'control/{NAME}.md'


def push_report():
    for attempt in range(3):
        night.fetch_report()
        night.scan_range(night.REPORT_REPO, night.REPORT_BRANCH, 'origin/' + night.REPORT_BRANCH)
        rc = subprocess.run(['git', '-c', 'core.commitGraph=false', 'push', '--no-follow-tags', 'origin',
                             f'refs/heads/{night.REPORT_BRANCH}:refs/heads/{night.REPORT_BRANCH}'],
                            cwd=night.REPORT_REPO).returncode
        if rc == 0:
            return night.git(night.REPORT_REPO, 'rev-parse', 'HEAD')
    raise RuntimeError('報告のpushが通らない')


def main():
    assert json.loads((BASE / 'result.json').read_text())['state'] == 'complete'
    assert json.loads((BASE / 'verification.json').read_text())['mismatches'] == 0
    assert night.git(night.SOURCE, 'branch', '--show-current') == night.WORK_BRANCH
    assert night.git(night.SOURCE, 'status', '--porcelain') == ''
    for mode in ((), ('--push',)):
        assert night.git(night.SOURCE, 'remote', 'get-url', *mode, 'origin') == night.DESTINATION
    night.checked_git(night.SOURCE, 'fetch', '--no-tags', 'origin',
                      f'refs/heads/{night.WORK_BRANCH}:refs/remotes/origin/{night.WORK_BRANCH}')
    code = night.git(night.SOURCE, 'rev-parse', 'HEAD')
    assert code == '7f48b75badd3854616449d9ab6464ccbb5f7b011'
    assert night.git(night.SOURCE, 'rev-parse', 'origin/' + night.WORK_BRANCH) == code
    night.scan_range(night.SOURCE, night.WORK_BRANCH, 'origin/' + night.WORK_BRANCH)
    night.fetch_report()
    night.checked_git(night.REPORT_REPO, 'add', '--', REPORT, f'control/{NAME}')
    night.checked_git(night.REPORT_REPO, 'commit', '-m', '動詞の選び間違いの記録関門と席の診断を保存')
    first = push_report()
    report = night.REPORT_REPO / REPORT
    report.write_text(report.read_text() + f'\n送信確認（{night.now()}）：`{night.WORK_BRANCH}` = `{code}`、`{night.REPORT_BRANCH}` = `{first}` を承認されたGitHubのoriginで確認。報告枝のこの追記も同じ宛先へpush。\n')
    night.checked_git(night.REPORT_REPO, 'add', '--', REPORT)
    night.checked_git(night.REPORT_REPO, 'commit', '-m', '選び間違いの診断の送信済み枝とコミットを追記')
    final = push_report()
    result = {'time': night.now(), 'work_branch': night.WORK_BRANCH, 'work_commit': code,
              'report_branch': night.REPORT_BRANCH, 'first_report_commit': first, 'report_commit': final}
    night.write_json(BASE / 'last_push.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
