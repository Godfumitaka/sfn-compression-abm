"""完了した一本の時間と常駐から、条件つきの本数と時間を計算する。"""
from pathlib import Path
import csv
import json
import math

ROOT = Path(__file__).resolve().parent


def main():
    old = json.loads((ROOT.parent / 'codex_sme_fast_2026-10-03/exact_full_01/full.summary.json').read_text())
    new = json.loads((ROOT / 'proof_rng_share_01/full.summary.json').read_text())
    assert new['all_requested_bytes_equal']
    runs = []
    for row in old['measurements']:
        runs.append({'code': row['code_commit'][:7], 'seconds': row['manifest_elapsed_sec'],
                     'peak_gib': row['peak_rss_mb'] * 10**6 / 2**30})
    row = new['measurements'][1]
    runs.append({'code': row['source_commit'][:7], 'seconds': row['manifest_elapsed_seconds'],
                 'peak_gib': row['peak_rss_mb'] * 10**6 / 2**30})
    # 独立点検の実測。新しい版のデスクトップの速さを実測した値ではない。
    desktop_baseline_seconds = 4 * 3600 + 31 * 60 + 34
    desktop_ratio = desktop_baseline_seconds / runs[0]['seconds']
    rows = []
    for run in runs:
        for machine, total, cpu_cap in (('desktop', 23, 16), ('mac', 32, 4)):
            for reserve in (0, 2, 4):
                for per_run_overhead in (0, 0.1):
                    count = min(cpu_cap, math.floor((total - reserve) / (run['peak_gib'] + per_run_overhead)))
                    waves = math.ceil(160 / count)
                    rows.append({'code': run['code'], 'machine': machine, 'total_gib': total,
                                 'reserve_gib': reserve, 'per_run_overhead_gib': per_run_overhead,
                                 'measured_mac_peak_gib': run['peak_gib'], 'parallel_upper': count,
                                 'waves_for_160': waves, 'mac_measured_seconds_per_run': run['seconds'],
                                 'hours_160_same_speed_as_mac': waves * run['seconds'] / 3600,
                                 'hours_160_desktop_baseline_ratio': (waves * run['seconds'] * desktop_ratio / 3600
                                                                     if machine == 'desktop' else None)})
    summary = {'scope': '世界2・A・種1の一本と同じ負荷を160回行う仮定。ほかの腕と種の所要・並列時の速度は未測定。',
               'runs': runs, 'desktop_baseline_seconds': desktop_baseline_seconds,
               'desktop_baseline_peak_gib': 4286704 * 1024 / 2**30,
               'desktop_baseline_to_mac_time_ratio': desktop_ratio,
               'desktop_source': 'control/2026-10-03_SME版の独立点検_走行の係.md 点検4',
               'mac_global_concurrency_cap': 4, 'rows': rows}
    (ROOT / 'capacity_estimates.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    with (ROOT / 'capacity_estimates.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({key: summary[key] for key in ('runs', 'desktop_baseline_to_mac_time_ratio')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
