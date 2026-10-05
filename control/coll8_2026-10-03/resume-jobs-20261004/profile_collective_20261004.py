"""研究者の試走一本：まとめ役と全個体をcProfileで測る。模型の計算を変更しない。"""
from pathlib import Path
import cProfile
import json
import os
import resource
import sys

root = Path(__file__).resolve().parent
sys.path[:0] = [str(root / 'source/tools'), str(root / 'source')]
import v311c
import v3_run

original_agent = v311c._agent_main

def profiled_agent(conn, task):
    directory = Path(os.environ['COLL8_PROFILE_DIR'])
    agent = task['v311c']['agent']
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        return original_agent(conn, task)
    finally:
        profiler.disable()
        profiler.dump_stats(str(directory / f'agent{agent}.prof'))
        (directory / f'agent{agent}.resource.json').write_text(json.dumps({
            'agent': agent, 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'platform': sys.platform, 'rss_unit': 'bytes on macOS',
        }) + '\n')

if __name__ == '__main__':
    directory = Path(os.environ['COLL8_PROFILE_DIR'])
    directory.mkdir(parents=True)
    v311c._agent_main = profiled_agent
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        v3_run.main()
    finally:
        profiler.disable()
        profiler.dump_stats(str(directory / 'coordinator.prof'))
        (directory / 'coordinator.resource.json').write_text(json.dumps({
            'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'platform': sys.platform, 'rss_unit': 'bytes on macOS',
        }) + '\n')
