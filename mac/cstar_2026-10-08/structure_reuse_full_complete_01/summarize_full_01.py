"""済んだ全長の比較と軽いCPU観測を、模型を起動せず一度だけ集計する。"""
from pathlib import Path
from datetime import datetime
from collections import Counter
import csv, hashlib, json

ROOT = Path(__file__).resolve().parent
WORK = ROOT/'full1740_01'
TARGET = ROOT/'full_summary_01.json'
assert not TARGET.exists() and not (ROOT/'full_cpu_01.csv').exists(), '済んだ集計は再実行しない'
complete = json.loads((WORK/'complete.json').read_text())
assert complete['passed'] and not (WORK/'STOP.json').exists()
names = ['off_A','off_L','off_Cstar','structure_Cstar']
assert complete['completed'] == names
result = dict(at=datetime.now().astimezone().isoformat(), complete=complete, cases={},
              source_commit='e05f990516bc2d45568854f02e97699be40155db', original_commit='7774b60709656446a352f3b43e25b67f4b6fc2fa',
              measurement='同じ軽いworker CPUとGC callback。cProfileなし。GCの秒は総CPUに含まれ足さない。',
              scope='お店世界2・種1・C*②・1740試行・horizon1740・PYTHONHASHSEED=0の一回ずつ。ほかの種・世界へ一般化しない。')
rows = []
for name in names:
    root = WORK/name
    comparison = json.loads((root/'comparison.json').read_text())
    assert comparison['passed'] and all(x['equal'] for x in comparison['files'])
    finished = json.loads((root/'finished.json').read_text())
    timing = json.loads((root/'whole_cpu.json').read_text())
    started = json.loads((root/'started.json').read_text())
    assert finished['exit'] == 0 and timing['configured_trials'] == 1740
    resource_file = root/'resources.jsonl'
    counters = Counter()
    samples = peak = held = swap = thermal = 0
    minimum_disk = None
    with resource_file.open() as stream:
        for line in stream:
            sample = json.loads(line)
            samples += 1
            counters[sample['cpu']['external_count']] += 1
            peak = max(peak,sample['rss_bytes'])
            held += bool(sample['held'])
            swap += bool(sample['resources']['swap_grew'])
            thermal += bool(sample['resources']['thermal_warning'])
            free = sample['resources']['free_bytes']
            minimum_disk = free if minimum_disk is None else min(minimum_disk,free)
    result['cases'][name] = dict(comparison_passed=True, comparison_file_count=len(comparison['files']),
        complete_at=json.loads((root/'complete.json').read_text())['at'], finished=finished, whole_cpu=timing,
        flags=started['native_command'][-1:] if name=='structure_Cstar' else [],
        resources=dict(samples=samples, external_model_counts=dict(sorted(counters.items())),
                       held_samples=held, swap_growth_samples=swap, thermal_warning_samples=thermal,
                       maximum_sampled_model_tree_rss_bytes=peak, minimum_disk_free_bytes=minimum_disk,
                       sha256=hashlib.sha256(resource_file.read_bytes()).hexdigest()))
    rows.append([name,len(comparison['files']),timing['callback_adjusted_worker_cpu_seconds'],
                 timing['gc_seconds'],finished['wall_seconds'],peak,samples])
off = result['cases']['off_Cstar']['whole_cpu']['callback_adjusted_worker_cpu_seconds']
on = result['cases']['structure_Cstar']['whole_cpu']['callback_adjusted_worker_cpu_seconds']
result['Cstar_cpu_comparison'] = dict(off_seconds=off, structure_seconds=on, difference_seconds=on-off,
                                     increase_percent=(on/off-1)*100, cpu_reduction_observed=on<off)
with (ROOT/'full_cpu_01.csv').open('x') as stream:
    writer=csv.writer(stream)
    writer.writerow(['条件','全バイト比較のファイル数','補正worker_CPU秒','総CPU内のGC秒','模型の実時間秒','2秒標本の模型の木の最大常駐バイト','標本数'])
    writer.writerows(rows)
with TARGET.open('x') as stream:
    stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result['Cstar_cpu_comparison'],ensure_ascii=False),flush=True)
