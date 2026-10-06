"""自分の段の報告を共通の結果枝へ通常pushする。"""
from pathlib import Path
from datetime import datetime
import fcntl,hashlib,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parent
RESULTS=ROOT.parent/'codex_worldv4_2026-10-01/results'
LOCK=ROOT.parent/'codex_sme_light_2026-10-04/control_writer_01.lock'
phase=sys.argv[1]
def git(*args):
    row=subprocess.run(['git',*args],cwd=RESULTS,capture_output=True,text=True)
    with (ROOT/'report_git.jsonl').open('a') as f:
        f.write(json.dumps({'at':datetime.now().astimezone().isoformat(),'args':args,'exit':row.returncode,'out':row.stdout,'err':row.stderr},ensure_ascii=False)+'\n')
    assert row.returncode==0,row.stderr
    return row.stdout
try:
    with LOCK.open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        marker=ROOT/f'reported_{phase}.json'
        assert not marker.exists()
        assert not git('status','--porcelain').strip()
        git('fetch','origin','results-2026-09-27')
        git('rebase','origin/results-2026-09-27')
        now=datetime.now().astimezone().isoformat()
        report='control/2026-10-06_SMEの一本の時間の内訳_Codex.md'
        path=RESULTS/report
        if not path.exists():path.write_text('# SMEの一本の時間の内訳\n\n数と事実だけを記録する。\n')
        with path.open('a') as out:out.write(f'\n## {phase}：{now}\n\n'+(ROOT/f'{phase}.md').read_text()+'\n')
        proof_rel='mac/sme_time_evict_2026-10-06/'+phase
        proof=RESULTS/proof_rel;proof.mkdir(parents=True,exist_ok=False)
        for p in json.loads((ROOT/f'{phase}_proofs.json').read_text()):
            src=ROOT/p;assert src.stat().st_size<10*2**20,'大きな状態は写さない';dest=proof/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
        (proof/'sha256.json').write_text(json.dumps({str(p.relative_to(proof)):hashlib.sha256(p.read_bytes()).hexdigest() for p in proof.rglob('*') if p.is_file()},indent=2)+'\n')
        progress='control/2026-09-30_Codex_進み具合.md'
        with (RESULTS/progress).open('a') as out:out.write(f'\n- {now}：SMEの一本の時間の内訳の{phase}を記録。25番を優先。お店1740試行と動詞の先頭1000試行を、自分の別の出力先で計測。log Pの新規走行と再生分類は、再開の指示まで停止。\n')
        git('sparse-checkout','add',proof_rel)
        git('add','--sparse',report,progress,proof_rel);git('commit','-m','SMEの一本の時間の内訳の'+phase+'を記録')
        git('fetch','origin','results-2026-09-27');git('rebase','origin/results-2026-09-27')
        row=subprocess.run(['git','push','origin','HEAD:results-2026-09-27'],cwd=RESULTS,capture_output=True,text=True)
        if row.returncode and any(x in row.stderr for x in ('fetch first','fetch-first','non-fast-forward')):
            git('fetch','origin','results-2026-09-27');git('rebase','origin/results-2026-09-27');git('push','origin','HEAD:results-2026-09-27')
        else:assert row.returncode==0,row.stderr
        marker.write_text(json.dumps({'at':now,'commit':git('rev-parse','HEAD').strip(),'reported':True},indent=2)+'\n')
        print(phase,'通常push',json.loads(marker.read_text())['commit'],flush=True)
except Exception as e:
    (ROOT/'report_stop.json').write_text(json.dumps({'phase':phase,'reason':str(e),'at':datetime.now().astimezone().isoformat(),'conflicts_not_resolved':True},ensure_ascii=False,indent=2)+'\n');raise
