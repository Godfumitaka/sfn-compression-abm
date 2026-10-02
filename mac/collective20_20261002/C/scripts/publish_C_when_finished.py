"""指定した有限の走行が終了・停止したら、保存済みの数表を結果の枝へ送る。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, subprocess, time, traceback

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT.parent/'codex_worldv4_2026-10-01/results'
PATHS=['control/2026-10-02_集団化の一対一_Codex.md','control/2026-09-30_Codex_進み具合.md','mac/collective20_20261002/C']
def now(): return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
def command(argv):
    p=subprocess.run(['git',*argv],cwd=RESULTS,capture_output=True,text=True)
    if p.returncode: raise RuntimeError({'argv':argv,'returncode':p.returncode,'output':(p.stdout+p.stderr)[-6000:]})
    print(json.dumps({'time':now(),'command':argv,'output':(p.stdout+p.stderr)[-1000:]},ensure_ascii=False),flush=True)
    return p.stdout
def main():
    while not (ROOT/'C_finished.json').exists() and not (ROOT/'C_failure.json').exists():
        changed=subprocess.run(['git','diff','--quiet','--',PATHS[1]],cwd=RESULTS).returncode
        if changed:
            command(['add','--',PATHS[1]])
            command(['commit','-m','集団化Cの進み具合を記録'])
            command(['fetch','origin','results-2026-09-27'])
            command(['merge','--no-edit','--no-stat','origin/results-2026-09-27'])
            command(['push','origin','HEAD:results-2026-09-27'])
        time.sleep(25)
    # 停止した場合の表の保存が終わるのを待つ。
    if (ROOT/'C_failure.json').exists(): time.sleep(25)
    command(['add','--',*PATHS])
    changed=subprocess.run(['git','diff','--cached','--quiet'],cwd=RESULTS).returncode
    if changed: command(['commit','-m','集団化Cの種1〜20の数表と通信の追跡を保存'])
    for attempt in range(3):
        command(['fetch','origin','results-2026-09-27'])
        command(['merge','--no-edit','--no-stat','origin/results-2026-09-27'])
        p=subprocess.run(['git','push','origin','HEAD:results-2026-09-27'],cwd=RESULTS,capture_output=True,text=True)
        if p.returncode==0:
            sha=command(['rev-parse','HEAD']).strip()
            (ROOT/'C_published.json').write_text(json.dumps({'time':now(),'commit':sha,'complete':(ROOT/'C_finished.json').exists(),'push_output':p.stdout+p.stderr},ensure_ascii=False,indent=1)+'\n')
            print(json.dumps({'published':sha},ensure_ascii=False),flush=True);return
        if 'fetch first' not in p.stderr and 'non-fast-forward' not in p.stderr: raise RuntimeError(p.stderr)
    raise RuntimeError('共有枝が3回続けて更新されたため、未反映のまま保存。')
if __name__=='__main__':
    try: main()
    except BaseException as e:
        (ROOT/'C_publish_failure.json').write_text(json.dumps({'time':now(),'error':repr(e),'traceback':traceback.format_exc()},ensure_ascii=False,indent=1)+'\n')
        raise
