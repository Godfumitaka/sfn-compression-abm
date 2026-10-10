"""既知の模型workerから同じ命令でforkした子だけを実workerとして加える。"""
from pathlib import Path
import sys
from model_count import count_models as original_count_models


def count_models(rows):
    models, unknown, paused, paused_models = original_count_models(rows)
    known = {row['pid'] for row in models + paused_models}
    # forkした子はspawn_mainの命令を継承する。親が実workerで命令も同じことを確かめる。
    while True:
        added = []
        for row in unknown + paused:
            if row['pid'] in known:
                continue
            parent = rows.get(row['ppid'], {})
            if row['ppid'] in known and row['command'] == parent.get('command') and 'spawn_main' in row['command']:
                added.append(row['pid'])
                item = {**row, 'worker_kind':'fork_birth', 'parent_command':parent['command']}
                if 'T' in row['state'] or 'Z' in row['state']:
                    paused_models.append(item)
                else:
                    models.append(item)
        if not added:
            break
        known.update(added)
        unknown = [row for row in unknown if row['pid'] not in known]
    return models, unknown, paused, paused_models
