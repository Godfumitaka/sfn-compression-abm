"""受領済みの指示と関門待ちの列の確認だけを通常pushする。"""
from pathlib import Path
from datetime import datetime
import fcntl, hashlib, json, re, shutil, subprocess, sys

R = Path(__file__).resolve().parent
REPO = R.parent / 'codex_worldv4_2026-10-01/results'
LOCK = R.parent / 'codex_sme_light_2026-10-04/control_writer_01.lock'
phase = sys.argv[1]
assert re.fullmatch(r'heartbeat_\d{8}_\d{4}', phase)
snapshot = R / (phase + '.json')
data = json.loads(snapshot.read_text())
assert not any(not x['received'] and not x['held'] for x in data['instructions']), '未受領の指示は先に読む'
ready_rows = [x for x in data['queue_rows'] if x['状態'] == '未着手' and x['版・旗・出力先']
              and x['機械'] in ('マック', 'Mac', 'どちらでも')]
assert ready_rows == data['eligible_mac_rows'], '列の機械表記と確認の抽出が一致しない'
waiting_rows = []
for row in ready_rows:
    cpu_needed = re.search(r'CPU(\d+)枠', row['版・旗・出力先'])
    models_needed = re.search(r'実模型(\d+)枠', row['版・旗・出力先'])
    assert cpu_needed and models_needed, '新しい行の必要枠を先に確認する'
    cpu_needed, models_needed = int(cpu_needed[1]), int(models_needed[1])
    assert data['cpu']['total_compute_count'] + cpu_needed > data['cpu']['cap'] or data['cpu']['total_compute_count'] + models_needed > data['cpu']['cap'], '指定の開始枠が空いた行は先に処理する'
    waiting_rows.append({'row': row['#'], 'cpu_needed': cpu_needed, 'models_needed': models_needed})

assert not (R / (phase + '_reported.json')).exists(), '重複して記録しない'
earlier_snapshot = None
earlier_data = None
if len(sys.argv) > 2:
    earlier_phase = sys.argv[2]
    assert re.fullmatch(r'heartbeat_\d{8}_\d{4}', earlier_phase)
    assert earlier_phase != phase and not (R / (earlier_phase + '_reported.json')).exists()
    earlier_snapshot = R / (earlier_phase + '.json')
    earlier_data = json.loads(earlier_snapshot.read_text())
    assert earlier_data['at'] < data['at']
    assert not earlier_data['eligible_mac_rows']
    # 同じ回の着手時と作業後の読み取りを、元の証拠を変更せず一緒に記録する。
    assert [(x['header'], x['received'], x['done'], x['held']) for x in earlier_data['instructions']] == [
        (x['header'], x['received'], x['done'], x['held']) for x in data['instructions']]
    assert earlier_data['files']['control/受け箱/README.md'] == data['files']['control/受け箱/README.md']
    # 過去の確認の列は保存したまま報告する。最新の列は下のロック内で照合し、
    # 両方とも取得可能行がない場合だけ、列の更新を挟んだ読み取りを一緒に記録する。

def git(*args):
    p = subprocess.run(['git', *args], cwd=REPO, capture_output=True, text=True)
    with (R / (phase + '_git.jsonl')).open('a') as f:
        f.write(json.dumps({'at': datetime.now().astimezone().isoformat(), 'args': args,
                           'exit': p.returncode, 'out': p.stdout, 'err': p.stderr}, ensure_ascii=False) + '\n')
    if p.returncode:
        raise RuntimeError(p.stderr)
    return p.stdout
try:
    with LOCK.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert not git('status', '--porcelain').strip()
        git('fetch', 'origin', 'results-2026-09-27')
        git('rebase', 'origin/results-2026-09-27')
        current = git('rev-parse', 'origin/results-2026-09-27').strip()
        for path in ('control/受け箱/README.md', 'control/受け箱/SMEの係.md', 'control/走行の列_2026-10-08.md'):
            assert git('show', current + ':' + path) == data['files'][path], '受け箱または列が更新された。読み直す'
        pending = json.loads((R / 'pending_01.json').read_text())
        memory_root = R.parent / 'codex_cstar_profile_2026-10-08/deep_memory_instruction12_01'
        analysis_preparation = data.get('instruction12_deep_memory_status', {}).get('analysis_prepared_01')
        analysis_to_report = analysis_preparation and not (memory_root / 'reported_analysis_preparation_01.json').exists()
        if analysis_to_report:
            assert analysis_preparation['model_runs_for_analysis_preparation'] == 0
            assert not analysis_preparation['analysis_started'] and not analysis_preparation['model_code_or_observer_changed']
            for name, sha in analysis_preparation['scripts_sha256'].items():
                assert hashlib.sha256((memory_root / name).read_bytes()).hexdigest() == sha
        at = data['at']
        cpu = data['cpu']
        cases = data['status'].get('cases', {})
        instructions = '、'.join(x['header'].removeprefix('## ') + '：' +
                                  ('保留' if x['held'] else '済み' if x['done'] else '受領済み・未完了')
                                  for x in data['instructions']) or '指示なし'
        lines = ['\n### 継続確認：' + at + '\n\n',
                 '取り込み' + data['fetched_commit'] + '。' + instructions + '。新規の未受領0件、取得可能行0件。\n\n',
                 '機械全体の模型の過程' + str(cpu['total_compute_count']) + '本（自分' +
                 str(cpu['own_compute_count']) + '、他の係' + str(cpu['external_count']) + '、上限8）。'
                 '小さい待機中の模型の子も数え、親の二重計上とSIGSTOP中の過程を除いた。\n\n']
        if earlier_data:
            initial_cpu = earlier_data['cpu']
            received = [re.search(r'指示 (\d+)', x['header'])[1] for x in earlier_data['instructions'] if x['received']]
            done = [re.search(r'指示 (\d+)', x['header'])[1] for x in earlier_data['instructions'] if x['done']]
            held = [re.search(r'指示 (\d+)', x['header'])[1] for x in earlier_data['instructions'] if x['held']]
            lines.append('同じ回の着手時の確認：' + earlier_data['at'] + '、取り込み' + earlier_data['fetched_commit'] +
                         '。受領済み指示' + '・'.join(received) + '、済み' + '・'.join(done) +
                         '、受け箱で指示全体を保留とした番号' + ('・'.join(held) if held else 'なし') +
                         '、新規未受領0、取得可能行0。模型の過程は自分' + str(initial_cpu['own_compute_count']) +
                         '・他' + str(initial_cpu['external_count']) + '・計' + str(initial_cpu['total_compute_count']) +
                         '本。旧診断3欄の省略の仕様確認1件は保留を維持。\n\n')
            queue_path = 'control/走行の列_2026-10-08.md'
            if earlier_data['files'][queue_path] != data['files'][queue_path]:
                lines.append('二つの確認の間に走行の列の文面が更新された。両時点で取得可能行0件。'
                             '各時点の列の原文を別々の確認記録に保存し、行を取得していない。\n\n')
        for name, row in cases.items():
            label = 'お店' if name.startswith('shop_') else '動詞'
            lines.append(label + 'は' + str(row['completed_trials']) + '/' + str(row['measured_trials']) +
                         '、段は' + row['stage'] + '、' + ('完了・報告済み' if row['stage'] == 'complete' and row['reported'] else
                         '過程の上限で停止中' if row['cpu_paused'] else '処理中') +
                         '。受付は' + str(row['claim_pid']) + '。\n\n')
        if waiting_rows:
            lines.append('未着手のマック用行' + str(len(waiting_rows)) + '件。\n\n')
            for waiting in waiting_rows:
                lines.append('列' + waiting['row'] + 'は資源待ち。指定はCPU' + str(waiting['cpu_needed']) +
                             '枠・実模型' + str(waiting['models_needed']) + '枠。現在の模型の過程' +
                             str(cpu['total_compute_count']) + '本。開始時の空き枠は' +
                             str(max(0, cpu['cap'] - cpu['total_compute_count'])) + 'で、指定のCPU' +
                             str(waiting['cpu_needed']) + '枠を確保できない。指定の実模型を足した数は' +
                             str(cpu['total_compute_count'] + waiting['models_needed']) +
                             '本。上限8本と行の開始枠を維持し、取得0件、受付と模型の新規起動0件。\n\n')
            if phase == 'heartbeat_20261010_0101':
                lines.append('機械欄のMacをマックとして読む確認の別版を保存。原版の抽出では対象行を拾わなかったため、'
                             '最新の列を別の確認で読み直し、元の確認と過去の記録は保持した。\n\n')
            row_spec_path = R / (phase + '_row19p_spec.json')
            if row_spec_path.exists():
                row_spec = json.loads(row_spec_path.read_text())
                assert row_spec['cpu_start_slots'] == 6 and row_spec['model_start_slots'] == 5
                assert row_spec['memory_reservation_gb'] == 10 and row_spec['source_commit'] == '6e4bcba94874a4f49c5a1bae11d385534504e2e5'
                lines.append('列19pの指定仕様を取り込みコミットから読むだけで確認。cpu_start_slotsは6、'
                             'model_start_slotsは5、memory_reservation_gbは10、ready_to_startは' +
                             ('真' if row_spec['ready_to_start'] else '偽') + '。仕様・版・旗・出力先を変更していない。\n\n')
        elif not cpu['own_compute_count'] and not cpu['own_reserved_slots']:
            lines.append('空き（' + at + '）。列に取得できる行なし。\n\n')
        queue_case = data.get('queue19p_status', {})
        if queue_case:
            claim = queue_case.get('queue_claim_published', {})
            state = queue_case.get('status', {})
            result = queue_case.get('result', {})
            launch = queue_case.get('launcher_pid', {})
            lines.append('列19pはSMEの係が' + str(claim.get('at')) + 'に取得、通常push' + str(claim.get('commit')) +
                         'と最新での取得を確認した。元の版6e4bcba・種1・試行5000・horizon5000・全旗と観察器・10GiB・CPU6枠・実模型5枠を維持。' +
                         '受付PID' + str(launch.get('pid')) + 'を一度だけ作成。保存した状態：' + str(state.get('state', '受付待ち又は開始前')) +
                         '、模型の群' + str(queue_case.get('pid', {}).get('pgid', '未開始')) + '、原終了' + str(result.get('exit_code', '未終了')) +
                         '。既存の受付・模型・比較を重複しない。元の他係の仕様と開始待ち、旗なしの手本は変更していない。' +
                         '全5000の旗あり結果とλはまだ仮。小さい取得証拠mac/cstar_2026-10-10/queue19p_claim_01。\n\n')
            if queue_case.get('warnings_tail'):
                lines.append('列19pの資源の警告の記録あり。自分の記録を読み、本番を止めず新規走行を始めない。小さい原警告は確認JSONに保存。\n\n')
                warning_path = R / (phase + '_resource_warning_small_01.json')
                if warning_path.exists():
                    warning_summary = json.loads(warning_path.read_text())
                    lines.append('資源の警告' + str(warning_summary['warning_count']) + '件。\n')
                    for warning in warning_summary['warnings']:
                        lines.append('原標本' + warning['at'] + '、模型の群' + str(warning['own_group']) +
                                     '、理由' + warning['reason'] + '。群RSS' + str(warning['own_rss_bytes']) +
                                     'バイト（' + str(round(warning['rss_gib'], 6)) + 'GiB）、受付見込み' +
                                     str(warning_summary['memory_reservation_bytes']) + 'バイト（10GiB）、超過' +
                                     str(warning['excess_bytes']) + 'バイト。原標本の空き' + str(warning['free_disk_bytes']) +
                                     'バイト、本番の停止0件、今回の新規模型0本。版・旗・入力・観察器・受付の見込みを変更せず、後続を始めない。\n')
                    lines.append('原警告SHA256 ' + warning_summary['original_warning_sha256'] + '。小さい表' + phase + '_resource_warning_small_01.json。\n\n')
            if queue_case.get('STOP') or (result and result.get('exit_code') != 0):
                lines.append('列19pに停止又は原終了の失敗あり。直そうとせず、後続を始めない。原記録を保存。\n\n')
        completion = None
        if data['completion_record'] and data['proposals_reported']:
            time_root = R.parent / 'codex_sme_time_evict_2026-10-06'
            completion = json.loads((time_root / 'all_complete_priority25.json').read_text())
            assert completion['passed'] and completion['measured_trials'] == [1740, 1000]
            assert completion['reported']['reported']
            comparisons = [json.loads((time_root / name / 'comparison.json').read_text())
                           for name in ('shop_profile1740_02', 'verb_profile1000_01')]
            assert all(x['passed'] for x in comparisons)
            lines.append('25′は' + completion['at'] + 'に完了。お店1740試行と動詞の先頭1000試行を計測し、'
                         '台帳本体・全side・保存状態を基準の記録と比較して一致した。動詞はtrial-count 5000・horizon 5000を保ち、'
                         '1001番目の入力を評価する前に計測専用の処理を終えた。時間の内訳と二つの案は'
                         'control/2026-10-06_SMEの一本の時間の内訳_Codex.mdへ報告し、コミット' +
                         completion['reported']['commit'] + 'でpush済み。案(a)は未実装。案(b)は受け箱の指示3・8の範囲で進める。\n\n')
        resource = data['resources']
        lines.append('空き容量' + str(round(resource['free_bytes']/2**30,2)) + 'GiB。スワップの直接確認：' +
                     data['diagnostics']['swap']['out'].strip() + '。熱の直接確認は添付。'
                     '既存の模型と受付の状態を確認。古いlog P主160本の新規走行と再生分類の停止を維持。\n')
        sampler_snapshot = R / (phase + '_sampler.json')
        if sampler_snapshot.exists():
            sampler = json.loads(sampler_snapshot.read_text())
            assert sampler['ps_exit'] == 0 and '/Users/tatsu-admin/jobs/jobs.py sampler' in sampler['ps']
            sampler_lines = [line.split(None, 3) for line in sampler['ps'].splitlines() if '/Users/tatsu-admin/jobs/jobs.py sampler' in line]
            assert len(sampler_lines) == 1 and len(sampler_lines[0]) == 4
            sampler_pid = int(sampler_lines[0][0])
            assert sampler.get('pid', sampler_pid) == sampler_pid
            lines.append('samplerは' + sampler['at'] + 'のpsでPID' + str(sampler_pid) +
                         'の存続を確認。命令はjobs.py sampler。重複起動0件。\n')
        if pending.get('state') == 'await_material_scope_specification':
            lines.append('41番の未接続の部品16項目は通過。予測とEの逐語の材料選びの回答待ちで、本番への接続とその関門は保留。'
                         '41′番は本文未受領。較正の部品の接続は未着手。\n')
        elif pending.get('state') == 'stopped_native_gate_reader_error':
            lines.append('41・41′は作業版7774b60の小検査23項目まで通過。材料選び②は承認済み。'
                         'native_preflight_01の比較台本が完了印seed001.doneをgzipとして読んだエラーで、比較は未判定のまま停止中。'
                         '停止への新しい指示は無い。台本を再起動せず、関門の先・較正・案(b)・指示4には進まない。\n')
        elif pending.get('state') == 'stopped_native_gate_byte_mismatch':
            lines.append('指示5による比較台本の修正と既存二本の再判定は完了。旗なし20試行の台帳本体は一致したが、'
                         '全sideの照合記録の試行1のleft_nodes[0].keyが不一致で関門不合格。'
                         '保存状態は最初の不一致で停止したため未判定。新しい対応の指示を待ち、模型や比較を再起動せず、'
                         'log P・C*の関門の続き・較正・案(b)・指示4・本番には進まない。\n')
        elif pending.get('state') == 'running_full_cstar_gates':
            native=data.get('native_full_status',{})
            lines.append('指示6の小走行：固定ハッシュ環境で旗なし保持A・log PとC*の①②の20試行が、'
                         '台帳本体・全side・保存状態の各全7ファイルで一致。模型のコードは7774b60のまま。\n')
            lines.append('全1740試行の既存の関門の監督を確認。現在の条件：'+str(native.get('current',{}).get('case'))+
                         '、書き出した回答の行数の下限'+str(native.get('written_answer_rows_lower_bound','未記録'))+
                         '。終了した条件：'+str(list(native.get('finished_cases',{})))+
                         '。完了印：'+str(bool(native.get('complete')))+'、停止の印：'+str(bool(native.get('STOP')))+
                         '。同じ処理を重複して始めない。較正・案(b)・指示4・本番にはまだ進まない。\n')
        elif pending.get('state') == 'running_parallel_full_cstar_gates':
            native=data.get('native_full_status',{})
            parallel=data.get('parallel_full_status',{})
            lines.append('指示7により未着手のC*①・②は個別の受付へ分けた。各8GB、PYTHONHASHSEED=0、命令と関門を維持。'
                         '完了した条件：'+str(list(native.get('finished_cases',{})))+'。途中の書き出した回答の行数の下限：'+
                         str(native.get('incomplete_case_written_rows',{}))+'。比較の状態：'+str(native.get('comparisons',{}))+'。\n')
            lines.append('個別の監督の完了印：'+str(bool(parallel.get('complete')))+'、不通の印：'+str(bool(parallel.get('STOP')))+
                         '。既存の直列監督のSTOPが予約したon_ownのFileExistsErrorなら、指示7で分割するための重複起動防止であり、'
                         '関門不一致とは扱わない。較正・案(b)・指示4・本番にはまだ進まない。並列の実時間は指示4の内訳に使わない。\n')
        elif pending.get('state') == 'running_components_full_gate':
            component = data.get('component_full_status', {})
            lines.append('C*材料①②と旗なし保持A・log Pの全1740試行の関門は通過・報告済み。'
                         '候補記録の20試行は保持A・log P・C*の再生と、答え・正誤・門・分類・源で一致。'
                         '作業版'+str(pending.get('component_commit'))+'を変更せず、既存受付'+
                         str(pending.get('component_full_claim_pid'))+'（12GB）で全長の旗なしA・log Pと'
                         'C*候補記録・再生比較を直列に継続。現在の条件：'+
                         str(component.get('current', {}).get('case'))+'、終了した条件：'+
                         str(list(component.get('finished_cases', {})))+'、完了印：'+
                         str(bool(component.get('complete')))+'、不通の印：'+str(bool(component.get('STOP')))+
                         '。新しい較正は合わせた版の関門と列#00の条件を満たすまで始めない。\n')
        elif pending.get('state') == 'running_instruction9_profile':
            profile = data.get('instruction9_profile_status', {})
            lines.append('指示9のC*のCPU内訳の計測を優先。受付'+str(pending.get('profile_claim_pid'))+'（11GB）、土台7774b60、材料②。'
                         '20試行の計測の全バイト一致を確かめてから、全1740試行のうち序盤300・後半200のCPU時間を測る。'
                         '既存のC*全長・旗なし二組は完了済みで再起動しない。案(b)の未完了の全長は優先変更の管理上の停止で、'
                         'STOP_instruction9_administrative.jsonを保全。途中を合格とは扱わない。\n')
            for case in ('preflight20_01','profile1740_01'):
                item=profile.get(case,{})
                lines.append('計測'+case+'：書き出した計測行'+str(item.get('measured_rows_written',0))+
                             '、最後の計測の試行番号'+str(item.get('last_measured_trial_number','未記録'))+
                             '、完了'+str(bool(item.get('complete')))+'、比較'+str(item.get('comparison',{}).get('passed','未判定'))+'。\n')
            if pending.get('instruction11_received'):
                lines.append('指示11で自分の他の模型との並行だけを避け、他係だけでは保留しない。'
                             '同じ模型65065・受付64925へ補助監督を接続。旧監督のpaused_secondsは論理上の保留の秒で、'
                             '再開中を含みうる一方、最後の未清算の保留を含まないため、実際の停止秒の上限と断定しない。'
                             '実際のT状態の2秒標本を別記。受付・空き・熱・スワップ・機械全体8本の条件は維持。\n')
            if pending.get('instruction12_received'):
                lines.append('指示12を受領し、指定資料の§2・§6を読了。計測後に試行内の再利用・点に依らない土台・'
                             'メモリの生存と構造制約の四項を調べる。四項は未実施。\n')
        elif pending.get('state') == 'waiting_or_running_instruction10_match_timing':
            item=data.get('instruction10_match_timing_status',{})
            lines.append('指示9のC*全1740試行の計測と7ファイルの全バイト一致、序盤300・後半200のCPU内訳の集計を完了。43c4472で通常push。既存の模型・集計を再起動しない。\n\n')
            lines.append('指示10・11の個別の照合時間の受付'+str(pending.get('match_timing_claim_pid'))+'（見込み11GB）。'+
                         ('監督を開始済み。' if 'started' in item else '受付の条件で待機。模型は未起動。')+
                         '20試行と全1740試行の全バイト一致の関門は'+('完了。' if item.get('complete',{}).get('passed') else '未完了。')+
                         '同じ受付と保存から続け、二重起動しない。旧log Pと再生分類を再開しない。\n')
            if item.get('STOP'):
                lines.append('個別計測の停止の記録：'+str(item['STOP'].get('reason'))+'。後続を始めず指定の報告へ原因を記録する。\n')
            if pending.get('fast_gates_prepared'):
                lines.append('指示13のGCとencodeの旗は作業版'+str(pending.get('fast_source_commit'))+'へ準備。'
                             'encodeの269小例と非対応型3例は一致、模型の全長関門は未着手。'
                             '旧診断3欄の省略で保存状態が変わる小例1件を報告し、その省略旗は仕様確認待ち。関門は変更しない。\n')
        elif pending.get('state') == 'instruction10_match_timing_complete':
            lines.append('指示10・11の個別観測は全1740試行と20試行の7ファイルで全バイト一致し、CPU・呼び出し元・控えの読み取り集計を完了。'
                         '模型・受付・集計は終了済みで再起動しない。指示10・11は済み。'
                         '指示12の点に依らない土台の新しい使い回しと深いメモリの内訳は未完了。'
                         'GC・encodeの全長はデスクトップ係の結果待ち、旧診断3欄の省略は仕様確認1件で保留。'
                         'Macの旧gates_01を自動起動しない。\n')
        elif pending.get('state') == 'running_instruction12_structure_gates':
            item=data.get('instruction12_structure_status',{}).get('full1740_01',{})
            completed=[name for name,row in item.get('cases',{}).items() if row.get('complete',{}).get('passed')]
            lines.append('指示10・11の全長の個別観測・7ファイルの一致・CPUと控えの集計は完了し、済み。'
                         '指示12の索引と高さだけの旗は別の自分の枝'+str(pending.get('structure_source_commit'))+'で部品18組と各20試行4条件の7ファイル一致を確認。'
                         '全長の新しい関門の既存受付'+str(pending.get('structure_full_claim_pid'))+'（11GB）を一度だけ起動。'
                         '現在の条件：'+str(item.get('current',{}).get('case','受付待ち'))+'、済んだ条件：'+str(completed)+'。'
                         '全長は'+('完了。' if item.get('complete',{}).get('passed') else '未完了。')+
                         '途中と完成の条件を再起動せず、不通・不一致なら原因を報告し後続を止める。'
                         '点・候補・乱数・最終対応は再計算し、CPU削減は全長の関門と同じ測り方の比較の後に判定する。'
                         'GC・encodeのデスクトップ全長とMacの旧gates_01は別。旧診断省略1件は保留。\n')
            for name, row in item.get('cases', {}).items():
                if row.get('complete', {}).get('passed'):
                    comparison = row.get('comparison', {})
                    files = comparison.get('files', [])
                    assert comparison.get('passed') and files and all(x.get('equal') for x in files)
                    lines.append('索引と高さの全長の条件' + name + '：' + row['complete']['at'] +
                                 'に比較完了、対象' + str(len(files)) + 'ファイルが全バイト一致。\n')
            if item.get('STOP'):
                lines.append('図の土台の関門の停止：'+str(item['STOP'].get('reason'))+'。直そうとせず指定の報告へ小例と件数を残す。\n')
            if pending.get('deep_memory_prepared'):
                lines.append('指示12の深いメモリの別出力の観測部品は、模型なしの1GB受付76755で小例7件が通過・準備報告済み。'
                             '同じ実体のsys.getsizeof合計を現在の常駐と過去最大から分ける。'
                             '模型へは未接続で、実測と観測の全バイト関門は未完了。現在の全長の模型・コード・入力を変更していない。\n')
                prepared=data.get('instruction12_deep_memory_status',{}).get('reported_execution_preparation_01')
                if prepared:
                    lines.append('別のメモリ観測の起動前の確認と二重起動防止は'+prepared['commit']+
                                 'で準備報告済み。原版・観測のSHAは不変。20試行の全バイト一致と完全な参照集計、'
                                 '固定した11GBへ収まる見込みの確認後に全長へ進む。今は受付と模型を起動していない。\n')
        elif pending.get('state') == 'waiting_or_running_instruction12_deep_memory':
            item=data.get('instruction12_deep_memory_status',{})
            current=item.get(pending.get('deep_memory_phase'),{})
            lines.append('索引と高さの4条件の全長の全ファイル一致を確認し、その受付は終了。'
                         '別出力の深いメモリ観測の既存受付'+str(pending.get('deep_memory_claim_pid'))+
                         '、現在の段'+str(pending.get('deep_memory_phase'))+'。模型は'+
                         ('開始済み。' if current.get('started') else '受付の許可待ちで未開始。')+
                         '比較は'+str(current.get('comparison',{}).get('passed','未判定'))+'、参照集計は'+
                         str(current.get('observation_check',{}).get('complete','未判定'))+'。'
                         '同じ受付と観測を重複しない。原版7774b60・観測のSHA・元の旗と値を維持し、'
                         '20試行の完全な参照集計と7ファイル一致と11GBへ収まる見込みを満たすまで全長を始めない。'
                         '現在の常駐・過去最大・到達するPythonの実体・観測の控えを分け、CPU速度の比較に使わない。'
                         '指示12は未完了。旧診断省略1件は保留、GC・encodeの全長はデスクトップ係の結果待ち。\n')
            if current.get('STOP'):
                lines.append('メモリ観測の停止：'+str(current['STOP'].get('reason'))+
                             '。小例と件数を報告して後続を始めず、直そうとしない。\n')
            if analysis_to_report:
                lines.append('全長の観測の後の集計台本analyze_memory_01.pyとlaunch_analysis_01.pyを準備。'
                             '模型なしで構文と固定SHAだけを確認し、完成した部品検査を繰り返していない。'
                             '全長の完全な固定6箇所の参照集計・7ファイルの全バイト一致・既存受付の終了後にだけ、'
                             '1GBの読み取り受付で小さい観測表と資源標本を一度集計する。'
                             '模型・大きい保存状態を再生せず、速度の比較に使わない。今は集計を開始していない。\n')
        elif pending.get('state') == 'instruction12_deep_memory_complete':
            lines.append('指示12の四項は完了・報告済み。別出力の深いメモリ全1740試行・固定6箇所の参照集計は完全、不完全0件、原版7ファイルが全バイト一致。'
                         '既存11GB受付98780と模型は終了後、1GB受付51199で小さい観測表を一度集計し終了した。'
                         '終了時のPython到達量9057815644バイトは現在常駐・過去最大・番地の控えと分ける。'
                         '完成した模型・観測・比較・集計は再起動しない。索引と高さの旗は全長一致だがCPU削減を確認できず、既定オフを維持。'
                         '指示9・13・案(b)・較正・4は未完了。旧診断省略1件は保留、GC・encode全長はデスクトップ係の結果待ち、Macの旧gates_01は始めない。\n')
        elif pending.get('state') == 'waiting_or_running_instruction13_fast_gates':
            item=data.get('instruction13_fast_status',{})
            lines.append('指示13のGC・同じ記録のencodeの関門の受付'+str(pending.get('fast_gate_claim_pid'))+'（11GB）。'+
                         ('監督開始済み。' if item.get('started') else '受付の条件で待機、模型未起動。')+
                         '現在の条件：'+str(item.get('current',{}).get('case','未開始'))+'。\n')
            completed=[name for name,case in item.get('cases',{}).items() if case.get('complete',{}).get('passed')]
            lines.append('完了した条件：'+str(completed)+'。全長の全バイト関門は'+
                         ('完了。' if item.get('complete',{}).get('passed') else '未完了。')+
                         '既存の監督と途中・完成の条件を再起動しない。\n')
            if item.get('STOP'):
                lines.append('関門の停止：'+str(item['STOP'].get('reason'))+'。後続を始めず指定の報告へ原因を記録する。\n')
            lines.append('OLD_MAPの診断3欄の省略は保存状態を変える実例1件があり、新しい対応の指示待ち。'
                         '省略旗は未実装、本番の旗は変更しない。\n')
        else:
            lines.append('41番の保存済みの状態：' + pending.get('state', '未記録') + '。既存の保存から続け、重複起動しない。\n')
        if pending.get('instruction15_received'):
            small=data.get('instruction15_small_status',{})
            completed=[name for name,item in small.get('cases',{}).items() if item.get('complete',{}).get('passed')]
            lines.append('指示15の200試行の受付'+str(pending.get('instruction15_small_claim_pid'))+'（4GB）。現在の条件：'+
                         str(small.get('current',{}).get('case','未開始'))+'、完了した条件：'+str(completed)+'。200試行の関門は'+
                         ('完了。' if small.get('complete',{}).get('passed') else '未完了。')+'全1740試行のGC・encodeの関門はデスクトップ係の結果待ち。'+
                         ('200試行の模型・受付・集計・公開・報告は終了済みで再実行しない。'
                          if pending.get('instruction15_done') else
                          '元の個別時間の11GBの受付は維持し、入れば200試行側を保留して自分の模型を並べない。')+
                         '旧診断省略は仕様確認待ち。\n')
            if small.get('STOP'):
                lines.append('200試行の停止：'+str(small['STOP'].get('reason'))+'。後続を始めず原因を報告する。\n')
        swap_growth_path = R / (phase + '_swap_growth_small_01.json')
        if swap_growth_path.exists():
            swap_growth = json.loads(swap_growth_path.read_text())
            before = swap_growth['previous_confirmation']
            after = swap_growth['current_confirmation']
            assert swap_growth['at'] == at and after['resources'] == data['resources']
            assert after['resources']['swap_mb'] > before['resources']['swap_mb']
            assert swap_growth['new_followup_models_on_hold']
            assert not swap_growth['production_stopped'] and swap_growth['new_models_started'] == 0
            lines.append('スワップ増加の確認1件。前の標本' + before['at'] + 'は' +
                         str(before['resources']['swap_mb']) + 'MB、今回の標本' + after['at'] + 'は' +
                         str(after['resources']['swap_mb']) + 'MB、二つの標本の差は' + swap_growth['increase_mb'] +
                         'MB。sysctlの原表示を小さい表へ保存。機械全体の増加で、原因を特定した記録はない。' +
                         '今回の空き' + str(after['resources']['free_bytes']) + 'バイト、熱警告なし、模型の過程' +
                         str(cpu['total_compute_count']) + '本（自分' + str(cpu['own_compute_count']) + '、他' +
                         str(cpu['external_count']) + '）。列19pの受付49493・監督49499・群49509は継続中、' +
                         '既報の群RSS警告の記録は前回と同じ。本番の停止0件、今回の模型の新規起動0本、' +
                         '後続の新規走行の保留を維持。版・旗・入力・観察器・10GiBの受付見込みと規則は変更しない。' +
                         '小さい表' + swap_growth_path.name + '。\n\n')
            if swap_growth.get('measurement_note'):
                lines.append(swap_growth['measurement_note'] + '\n\n')
        report = 'control/2026-10-07_C星の照合とディリクレ_実装_Codex.md'
        with (REPO / report).open('a') as f:
            f.write(''.join(lines))
        progress = 'control/2026-09-30_Codex_進み具合.md'
        with (REPO / progress).open('a') as f:
            f.write('\n- ' + at + '：SMEの30分確認。未受領0、取得可能行0。機械全体の模型の過程' +
                    str(cpu['total_compute_count']) + '本。' + ('25′の二本・一致検査・内訳と案の報告の完了を確認。'
                    if completion else '25′の既存処理を確認。') + '重複起動なし。\n')
        proof = 'mac/cstar_2026-10-07/' + phase
        dest = REPO / proof
        dest.mkdir(parents=True, exist_ok=False)
        assert snapshot.stat().st_size < 10 * 2**20
        shutil.copy2(snapshot, dest / snapshot.name)
        if sampler_snapshot.exists():
            assert sampler_snapshot.stat().st_size < 2**20
            shutil.copy2(sampler_snapshot, dest / sampler_snapshot.name)
        warning_path = R / (phase + '_resource_warning_small_01.json')
        if warning_path.exists():
            assert warning_path.stat().st_size < 2**20
            shutil.copy2(warning_path, dest / warning_path.name)
        if swap_growth_path.exists():
            assert swap_growth_path.stat().st_size < 2**20
            shutil.copy2(swap_growth_path, dest / swap_growth_path.name)
        if earlier_snapshot:
            assert earlier_snapshot.stat().st_size < 10 * 2**20
            shutil.copy2(earlier_snapshot, dest / earlier_snapshot.name)
        cpu_report = 'control/2026-10-08_C星の一本の時間の内訳_Codex.md'
        if analysis_to_report:
            for name in ('analysis_prepared_01.json', 'analyze_memory_01.py', 'launch_analysis_01.py'):
                assert (memory_root / name).stat().st_size < 2**20
                shutil.copy2(memory_root / name, dest / name)
            with (REPO / cpu_report).open('a') as f:
                f.write('\n### 指示12の全長のメモリ観測と集計の準備（' + at + '）\n\n'
                        '既存11GB受付98780の全長の観測は09:47:33.158271に監督7390・模型7396で開始。'
                        '原版7774b60・観測SHA14e49a1d3d7b0a364026f907b00e447a2e6dd1b944a6aa69c7b16c98a56c207a・'
                        '元の旗・値・固定6箇所・11GBの見込みを維持。全長の関門は未完了。'
                        '全長の参照集計が完全で7ファイルの全バイト一致が通り、同じ受付が終了した後にだけ、'
                        '新しいlaunch_analysis_01.pyで1GBの読み取り受付を一度作り、analyze_memory_01.pyを実行する。'
                        'analysis_claim_01.json・analysis.json・3つのCSV・analysis_STOP_01.jsonの存在を確認し、'
                        '受付待ち・途中・完成を重複しない。今回は構文と固定SHAの確認だけで集計は未開始。'
                        '現在常駐・過去最大・Pythonの到達量・番地の控えを分け、共通実体は根の順で先に数える。'
                        '独立所有量や常駐との差の候補への帰属、型の本体の量とその型が持つ全データの量を混ぜない。'
                        '未観測の山を排除せず、速度の比較に使わない。'
                        '模型・大きい保存状態を再生していない。指示12は未完了。小さい台本とSHA：' + proof + '。\n')
        for helper_name in ('collect_heartbeat_03.py', 'report_confirmation_07.py'):
            shutil.copy2(R / helper_name, dest / helper_name)
        row_spec_path = R / (phase + '_row19p_spec.json')
        if row_spec_path.exists():
            assert row_spec_path.stat().st_size < 2**20
            shutil.copy2(row_spec_path, dest / row_spec_path.name)
        original_snapshot = R / 'heartbeat_20261010_0056.json'
        if phase == 'heartbeat_20261010_0101':
            assert original_snapshot.stat().st_size < 10 * 2**20
            shutil.copy2(original_snapshot, dest / original_snapshot.name)
            original_sampler = R / 'heartbeat_20261010_0056_sampler.json'
            shutil.copy2(original_sampler, dest / original_sampler.name)
        if completion:
            (dest / '25prime_completion.json').write_text(json.dumps(completion, ensure_ascii=False, indent=2) + '\n')
        (dest / 'sha256.json').write_text(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                                     for p in dest.iterdir() if p.is_file()}, indent=2) + '\n')
        git('sparse-checkout', 'add', proof)
        git('add', '--sparse', report, progress, proof, *([cpu_report] if analysis_to_report else []))
        git('commit', '-m', 'SMEの30分確認と25番の進みを記録')
        git('fetch', 'origin', 'results-2026-09-27')
        git('rebase', 'origin/results-2026-09-27')
        p = subprocess.run(['git', 'push', 'origin', 'HEAD:results-2026-09-27'], cwd=REPO, capture_output=True, text=True)
        if p.returncode and any(x in p.stderr for x in ['fetch first', 'fetch-first', 'non-fast-forward']):
            git('fetch', 'origin', 'results-2026-09-27')
            git('rebase', 'origin/results-2026-09-27')
            git('push', 'origin', 'HEAD:results-2026-09-27')
        elif p.returncode:
            raise RuntimeError(p.stderr)
        result = {'at': datetime.now().astimezone().isoformat(), 'confirmation_at': at,
                  'reported': True, 'commit': git('rev-parse', 'HEAD').strip()}
        (R / (phase + '_reported.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        if analysis_to_report:
            prepared_result = dict(result, report=cpu_report, proof=proof, analysis_started=False, models_started=0)
            (memory_root / 'reported_analysis_preparation_01.json').write_text(json.dumps(prepared_result, ensure_ascii=False, indent=2) + '\n')
            private_path = R / 'pending_01.json'
            private = json.loads(private_path.read_text())
            private.update(deep_memory_analysis_prepared=True, deep_memory_analysis_preparation_report=prepared_result)
            private_path.write_text(json.dumps(private, ensure_ascii=False, indent=2) + '\n')
        if earlier_snapshot:
            (R / (earlier_phase + '_reported.json')).write_text(json.dumps(dict(
                result, confirmation_at=earlier_data['at'], included_in=phase), ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False), flush=True)
except Exception as e:
    (R / (phase + '_report_stop.json')).write_text(json.dumps({'at': datetime.now().astimezone().isoformat(),
                                                            'reason': str(e), 'conflicts_not_resolved': True},
                                                           ensure_ascii=False, indent=2) + '\n')
    raise
