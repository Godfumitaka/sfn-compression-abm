"""記録した最新の確認だけを進み具合へ追記する。fetchとrebaseとpushは別に行う。"""
from pathlib import Path
import json
import shutil


def last(path):
    return json.loads(path.read_text().splitlines()[-1])


def main():
    watch = Path(__file__).resolve().parent
    own = watch.parent
    repo = own.parent / 'codex_worldv4_2026-10-01/results'
    audit = last(watch / 'checks.jsonl')
    resources = last(watch / 'resources.jsonl')
    status = last(watch / 'production_status.jsonl')
    if audit['time'] != status['time']:
        raise SystemExit('確認と走行記録の時刻が違う')
    signal = '有り' if audit['exact_line_present'] else '無し'
    thermal = '無し' if 'No thermal warning level has been recorded' in resources['thermal'] else '有り'
    message = (f"\n{audit['time']} SME本番の合図の定期確認：resultsの{audit['commit'][:8]}、指定の行{signal}。"
               f"w1_D_tau04は出力{status['outputs_existing']}、完了{status['completed_runs']}/20本。"
               f"空き{resources['free_bytes'] / 2**30:.3f}GiB、熱の警告{thermal}。\n")
    with (repo / 'control/2026-09-30_Codex_進み具合.md').open('a') as stream:
        stream.write(message)
    destination = repo / 'mac/sme_fast_20261003/audit_watch_01'
    for name in ('checks.jsonl', 'resources.jsonl', 'production_status.jsonl', 'record_check.py', 'publish_check.py'):
        shutil.copy2(watch / name, destination / name)
    print('監視記録と進み具合を追記')


if __name__ == '__main__':
    main()
