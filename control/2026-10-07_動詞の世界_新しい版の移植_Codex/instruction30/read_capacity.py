"""指示30の容量診断。既存の時間行とstatだけを読み、模型には接続しない。"""
from datetime import datetime
from pathlib import Path
import hashlib, json, math, shutil, time

HERE=Path(__file__).resolve().parent
NR=HERE.parent
save=lambda p,d: p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    assert not (HERE/'capacity_read_completed.json').exists()
    started=time.time()
    save(HERE/'capacity_read_status.json',dict(state='running_readonly',pid=__import__('os').getpid(),model_starts=0))
    rows=[]
    for seed in (1,2):
        case=NR/f'instruction23_production/19_seed{seed:03d}_score_e_off'
        spec=json.loads((case/'spec.json').read_text())
        times=[json.loads(x) for x in (case/'output/timing100.jsonl').read_text().splitlines()]
        assert len(times)>=2
        files=[dict(path=str(p.relative_to(case)),bytes=p.stat().st_size,allocated_bytes=p.stat().st_blocks*512,
                    mtime_ns=p.stat().st_mtime_ns) for p in case.rglob('*') if p.is_file()]
        record_files=[x for x in files if '/records/' in x['path']]
        rows.append(dict(seed=seed,case=str(case),spec_sha256=sha(case/'spec.json'),
            source_commit=spec['source_commit'],driver=spec['command'][1],observer_files=spec['observer_files'],
            all_files=files,logical_bytes=sum(x['bytes'] for x in files),
            allocated_bytes=sum(x['allocated_bytes'] for x in files),
            existing_records_bytes=sum(x['bytes'] for x in record_files),
            timing_rows=times,last_completed_trials=times[-1]['completed_trials'],
            seconds_per_trial_recent_two_intervals=sum(x['interval_seconds'] for x in times[-2:])/200,
            seconds_per_trial_last_interval=times[-1]['interval_seconds']/100,
            result_present=(case/'result.json').exists(),
            m1_at501_present=(case/'output/comparison_checkpoints/m1_at_trial500.json').exists()))
    original=json.loads((NR/'instruction29/baseline19_500_capacity.json').read_text())
    # 前の診断の実数を再利用し、原500履歴の内容読み取り・集計は繰り返さない。
    C=3_873_491_726
    assert str(C) in json.dumps(original)
    free=shutil.disk_usage(HERE).free; reserve=30_000_000_000
    capacity=free-reserve
    anchor=time.time()
    forecasts=[]
    for exponent in (1,2):
        for seed2_ratio in (0.5,1.0,2.0):
            events=[]
            for row in rows:
                last=row['timing_rows'][-1]; n=last['completed_trials']
                rate=row['seconds_per_trial_recent_two_intervals']
                factor=1.0 if row['seed']==1 else seed2_ratio
                next_boundary=(n//500+1)*500
                for boundary in range(next_boundary,5001,500):
                    event_epoch=last['epoch_seconds']+(boundary-n)*rate
                    events.append(dict(seed=row['seed'],completed_trials_projected=boundary,
                        event_epoch_projected=event_epoch,copy_bytes_projected=C*factor*(boundary/500)**exponent))
            events.sort(key=lambda x:x['event_epoch_projected'])
            cumulative=0; crossing=None
            for e in events:
                cumulative+=e['copy_bytes_projected']
                if cumulative>capacity:
                    ep=e['event_epoch_projected']
                    counts={str(r['seed']):min(5000,r['last_completed_trials']+
                        max(0,(ep-r['timing_rows'][-1]['epoch_seconds'])/r['seconds_per_trial_recent_two_intervals'])) for r in rows}
                    crossing=dict(at_projected_jst=datetime.fromtimestamp(ep).astimezone().isoformat(),
                        epoch_projected=ep,trigger=e,both_seeds_trials_projected=counts,
                        additional_records_bytes_projected=cumulative,
                        hours_from_read_anchor_projected=(ep-anchor)/3600)
                    break
            forecasts.append(dict(history_content_growth_power=exponent,
                seed2_to_seed1_500_bytes_assumption=seed2_ratio,
                current_speed_basis='各種の原timing100の最後の2区間（容量停止を含む原値）/200',
                threshold_crossing_projected=crossing))
    code=[]
    paths=[Path(rows[0]['driver']),Path(rows[0]['driver']).parent.parent/'checkpoint_observer.py']
    for p in paths:
        text=p.read_text().splitlines()
        needles=('def worker','with observe','return original_worker','def append','result=native_append',
            'if n%500','copy_confirmed','ledger.append=append','native_append=ledger.append')
        code.append(dict(path=str(p),sha256=sha(p),relevant_lines=[dict(line=i,text=x) for i,x in enumerate(text,1) if any(n in x for n in needles)]))
    result=dict(at=datetime.now().astimezone().isoformat(),instruction=30,scope='原19種1/2、既存観察器の静的読取、原時間、サイズstat',
        model_starts=0,model_stop_resume=0,deletions=0,running_model_or_observer_changes=0,
        read_model_record_content=False,cases=rows,code_evidence=code,
        observer_in_model_worker=True,separate_observer_process=False,
        can_swap_observer_without_touching_running_model_process=False,
        reason='driverのworker内でobserveを取り付け、同じworker内のledger.appendの閉包が固定済みcopy_confirmedを呼ぶ。外部切替旗・再読込・別観察器の過程は無い。ファイルを置き換えても既存のimportと閉包は変わらない。',
        current_free_bytes=free,reserved_free_bytes_decimal=reserve,available_before_30GB=capacity,
        seed1_actual_500_copy_bytes_reused=C,
        forecast_is_conditional_not_measured=True,forecasts=forecasts,
        assumptions=['種1の実500履歴Cを基準に履歴内容が試行数の1乗又は2乗で増えると仮定。',
            '種2の実500コピーがまだなければ同量/半量/2倍を仮定した感度。実測として書かない。',
            '現在の原2区間の秒/試行が保たれ、500境ごとの非圧縮コピーだけが増える。',
            '元gzip・STATE/RNG/cache・他の係・APFSの割当変化の増分は含まないため、安全な下限/上限ではない。',
            'checkpointは完了境の階段として加算し、総時間から未記録区間を作らない。未来の試行数は予測として分ける。'],
        elapsed_seconds=time.time()-started)
    save(HERE/'capacity_read_result.json',result)
    save(HERE/'capacity_read_completed.json',dict(at=result['at'],exit_code=0,model_starts=0,
        result_sha256=sha(HERE/'capacity_read_result.json')))
    save(HERE/'capacity_read_status.json',dict(state='completed_readonly',at=result['at'],model_starts=0))
    central=[x for x in forecasts if x['seed2_to_seed1_500_bytes_assumption']==1]
    print(json.dumps(dict(completed=True,model_starts=0,free_bytes=free,central_forecasts=central),ensure_ascii=False))

if __name__=='__main__': main()
