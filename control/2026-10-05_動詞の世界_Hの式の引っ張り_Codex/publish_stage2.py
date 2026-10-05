"""承認された報告枝へ、H式の限定範囲の段2を送信する。"""
from pathlib import Path
import json
import sys
import publish

BASE = Path(__file__).resolve().parent
night = publish.night


def main():
    result = json.loads((BASE/'stage2/result.json').read_text())
    assert result['state'] == 'complete' and result['model_reruns'] == 0
    assert night.git(night.SOURCE, 'branch', '--show-current') == night.WORK_BRANCH
    assert night.git(night.SOURCE, 'status', '--porcelain') == ''
    for mode in ((), ('--push',)):
        assert night.git(night.SOURCE, 'remote', 'get-url', *mode, 'origin') == night.DESTINATION
    night.checked_git(night.SOURCE, 'fetch', '--no-tags', 'origin',
                      f'refs/heads/{night.WORK_BRANCH}:refs/remotes/origin/{night.WORK_BRANCH}')
    code = night.git(night.SOURCE, 'rev-parse', 'HEAD')
    assert code == '7f48b75badd3854616449d9ab6464ccbb5f7b011'
    assert night.git(night.SOURCE, 'rev-parse', 'origin/'+night.WORK_BRANCH) == code
    night.scan_range(night.SOURCE, night.WORK_BRANCH, 'origin/'+night.WORK_BRANCH)
    night.fetch_report()
    night.checked_git(night.REPORT_REPO, 'add', '--', publish.REPORT, f'control/{publish.NAME}')
    night.checked_git(night.REPORT_REPO, 'commit', '-m', '動詞Hの式の限定範囲の段2集計と反実仮想を追記')
    first = publish.push_report()
    report = night.REPORT_REPO/publish.REPORT
    report.write_text(report.read_text()+f'\n段2送信確認（{night.now()}）：`{night.WORK_BRANCH}` = `{code}`、`{night.REPORT_BRANCH}` = `{first}` を承認されたGitHubのoriginで確認。報告枝のこの追記も同じ宛先へpush。\n')
    night.checked_git(night.REPORT_REPO, 'add', '--', publish.REPORT)
    night.checked_git(night.REPORT_REPO, 'commit', '-m', 'Hの式の段2の送信済み枝とコミットを追記')
    final = publish.push_report()
    night.write_json(BASE/'stage2_last_push.json', {'time': night.now(), 'work_branch': night.WORK_BRANCH,
        'work_commit': code, 'report_branch': night.REPORT_BRANCH, 'report_commit': final, 'first_report_commit': first})
    print(json.dumps(json.loads((BASE/'stage2_last_push.json').read_text()), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
