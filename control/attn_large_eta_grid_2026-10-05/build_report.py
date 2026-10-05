"""追加格子の全40種が終わった後、同じ段Cの表と全名の最終重みを報告する。"""
from collections import Counter, defaultdict
import csv
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import resource
from zoneinfo import ZoneInfo

JOB = Path(__file__).resolve().parent
BASE = JOB.parent
SUMMARY = JOB/'summary'
AGG = SUMMARY/'aggregate'
DEST = BASE/'report/control/attn_large_eta_grid_2026-10-05'
REPORT = BASE/'report/control/2026-10-03_注意の選択_Codex2.md'
TITLE = '## 段②の追加：大きな η の格子'
GRID = [(b, e) for b in (5., 20.) for e in (.5, 1., 2., 5.)]


def rows(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, data, fields):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(data)


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            digest.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def table(headers, lines):
    return '\n|'+'|'.join(headers)+'|\n|'+'|'.join(['---']*len(headers))+'|\n'+''.join('|'+ '|'.join(map(str, line))+'|\n' for line in lines)+'\n'


def grouped(data, keys, values):
    result = defaultdict(Counter)
    for row in data:
        for field in values:
            result[tuple(row[k] for k in keys)][field] += int(row[field] or 0)
    return result


def main():
    status = json.loads((JOB/'supervision/status.json').read_text())
    assert status['status'] == 'complete_large_eta_ready_for_report'
    assert status['completed'] == {'1': list(range(1, 21)), '2': list(range(1, 21))}
    check = json.loads((SUMMARY/'all_C.json').read_text())
    assert check['passed'] and check['grid'] == 'large-eta' and check['seeds'] == 40
    assert check['trial_records'] == 1183200 and check['door_trial_records'] == 107202
    assert check['distinction_loss_to_correct'] == check['non_door_answer_mismatches'] == 0
    streamed = json.loads((JOB/'streamed_table_check.json').read_text())
    assert streamed['passed'] and streamed['bytes_identical'] and streamed['seeds'] == 40
    all_csv = json.loads((JOB/'all_csv_streaming_check.json').read_text())
    assert all_csv['passed'] and all_csv['all_bytes_identical'] and len(all_csv['csv_files']) == 16
    old = REPORT.read_text()
    assert TITLE not in old and not DEST.exists() and not (JOB/'report_built.json').exists()
    prefix = old.split('# 注意の選択・初版', 1)[0]
    DEST.mkdir()
    final, manifest, inputs = [], [], []
    for world in (1, 2):
        root = f'n3_w{world}_A_L50'
        for seed in range(1, 21):
            batch_path = JOB/'batches'/f'w{world}_seed{seed:03d}.json'
            batch = json.loads(batch_path.read_text())
            assert batch['passed'] and batch['inputs_unchanged'] and len(batch['replays']) == 16
            assert all(r['non_door_answers_match'] and r['full_census'] and r['mismatch'] is None for r in batch['replays'])
            inputs.extend(batch['inputs'])
            folder = SUMMARY/root/f'seed{seed:03d}'
            finals = rows(folder/'final_weights.csv')
            assert fingerprint(folder/'final_weights.csv') == batch['final_weights']
            expected = {(r['arm'], r['beta'], r['eta'], name): value for r in batch['replays'] for name, value in r['weights_final'].items()}
            assert len(finals) == len(expected)
            for row in finals:
                assert float(row['weight']) == expected[(int(row['arm']), float(row['beta']), float(row['eta']), row['name'])]
            final.extend(finals)
            paths = [batch_path] + [folder/name for name in ('check.json', 'final_weights.csv', 'trial_metrics.csv.gz', 'votes.jsonl.gz')]
            for arm in (1, 2):
                for beta, eta in GRID:
                    stem = f'seed{seed:03d}.arm{arm}.b{beta:g}_e{eta:g}'
                    paths += [JOB/'replay'/root/(stem+'.'+suffix) for suffix in ('attn.jsonl.gz', 'check.json')]
            manifest.extend(fingerprint(path) for path in paths)
    final_fields = ('world', 'seed', 'arm', 'beta', 'eta', 'name', 'weight')
    write_csv(DEST/'seed_final_weights.csv', final, final_fields)
    weight_groups = defaultdict(list)
    for row in final:
        weight_groups[(row['world'], row['arm'], row['beta'], row['eta'], row['name'])].append(float(row['weight']))
    weights = [{**dict(zip(('world', 'arm', 'beta', 'eta', 'name'), key)), 'seed_count': len(v),
                'mean': statistics.mean(v), 'minimum': min(v), 'maximum': max(v)}
               for key, v in sorted(weight_groups.items())]
    write_csv(DEST/'final_weights.csv', weights, ('world', 'arm', 'beta', 'eta', 'name', 'seed_count', 'mean', 'minimum', 'maximum'))
    # 値は維持し、配布用のCSVの改行をLFへ統一。大きな推移表だけgzipにする。
    copied = []
    for path in sorted(AGG.glob('*.csv')):
        if path.stat().st_size > 2*1024*1024:
            target = DEST/(path.name+'.gz')
            with path.open(encoding='utf-8') as source, gzip.open(target, 'wt', encoding='utf-8', newline='') as out:
                for line in source:
                    out.write(line)
        else:
            target = DEST/path.name
            target.write_text(path.read_text())
        copied.append(target.name)
    for name, path in [('all_C.json', SUMMARY/'all_C.json'),
                       ('pre_result_decisions.json', JOB/'pre_result_decisions.json'),
                       ('reservation_update.json', JOB/'reservation_update.json'),
                       ('wrapper_fix.json', JOB/'wrapper_fix.json'),
                       ('streamed_table_check.json', JOB/'streamed_table_check.json'),
                       ('aggregation_handoff.json', JOB/'aggregation_handoff.json'),
                       ('all_csv_streaming_check.json', JOB/'all_csv_streaming_check.json'),
                       ('verify_and_report.py', JOB/'verify_and_report.py'),
                       ('finish_grid.py', JOB/'finish_grid.py'),
                       ('run_grid.py', JOB/'run_grid.py'), ('build_report.py', JOB/'build_report.py')]:
        shutil.copy2(path, DEST/name)
    for path in (JOB/'supervision').glob('*.jsonl'):
        shutil.copy2(path, DEST/path.name)
    shutil.copy2(JOB/'supervision/status.json', DEST/'supervision_status.json')
    shutil.copytree(JOB/'reservation2GB_waiting', DEST/'reservation2GB_waiting')
    shutil.copytree(JOB/'wrapper_key_error_before_learning', DEST/'wrapper_key_error_before_learning')
    (DEST/'input_manifest.json').write_text(json.dumps(inputs, ensure_ascii=False, indent=2)+'\n')
    (DEST/'raw_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    machine = [json.loads(line) for line in (JOB/'supervision/machine_registered.jsonl').read_text().splitlines()]
    assert not any(r['thermal_warnings'] for r in machine)
    assert min(r['disk_free_gib'] for r in machine) >= 18.5
    swaps = [r['swap_mb'] for r in machine if r['swap_mb'] is not None]
    assert all(b <= a for a, b in zip(swaps, swaps[1:]))
    outcomes = [r for r in rows(AGG/'outcomes.csv') if r['task'] == 'door' and r['availability'] == 'all']
    totals = grouped(outcomes, ('world', 'arm', 'beta', 'eta', 'day'), ('correct', 'wrong', 'silent', 'total'))
    assert all(v['total'] == (612 if key[-1] == 'exception' else 2541) for key, v in totals.items())
    for key, v in totals.items():
        assert sum(v[x] for x in ('correct', 'wrong', 'silent')) == v['total']
    moment = datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
    text = '\n\n'+TITLE+'（'+moment+'）\n\n'
    text += ('アストラ承認の追加格子：腕1・腕2 × β={5,20} × η={0.5,1,2,5}、世界1・2、種1〜20。'
             '各条件の重みを1から学習し、記憶・場面・開示前の候補の回答・門・試行別の実開示は段Cと同じ保存済みのものを使った。'
             '元の走行、照合、候補の回答、門を外す分類は作り直していない。腕0は保存済みの元N3を比較用に一度だけ読む。'
             '通常日の正解から外れ・黙りへの変化も残し、本番のβ・ηを選ばない。\n\n'
             '腕1＝ドア課題だけ注意・全名、腕2＝ドア課題だけ注意・hold/hold_bは点で1、勾配0。'
             '本人にドア課題の指示が伝えられるとみなし、held_out_is_doorを使う仮定を維持。'
             '更新は台帳のf_realized・f_firedだけに従い、今の回答は更新前、次の試行から更新後。'
             '平均1の範囲、Hの自己点の最大値、同点の勾配の等分も段Cと同じ。\n\n')
    text += ('コード **b40a6d4ec0213b0377a2144821273e73f296511d**。'
             '点・注意・門・N3・模型のコードを変えず、集計器に `--attn-grid large-eta` を追加。'
             '既定の格子は元の九点のまま。注意の旗は `--attn-select --attn-door-only --attn-beta β --attn-eta η`、'
             '腕2に `--attn-fix-door-names`。N3・注意・ドア・測度の33検査合格。\n\n')
    text += ('CSV結合の省メモリ化は **0e40feb53745d375ea36038bcf71200843076805**。'
             '追加格子の重み推移表だけを一行ずつ結合し、既定の格子は元の経路を維持。'
             'この変更も含む34検査合格。全40種の結合後のCSVも、元の欄・行の順のDictReader→DictWriterによる'
             '別の検算とsha256が一致した。注意・N3・門・損失・集計の数式は無変更。\n\n')
    text += ('最終コード **cb27282a89c5f8aee302577d9b6f90cb747c194c** は全表を逐次読みへ拡張。'
             '種・行の順と合算の式を維持し、34検査合格。模型・注意を再実行せず、保存済みの種別CSVだけで'
             '検算した全16個の集計CSVが、先に完了した集計と全バイト一致した。\n\n')
    text += ('起動スクリプトは一度、分類控えに無いpassed欄を参照してKeyErrorで停止した。'
             'この時点の新しい注意計算の出力は0件。控えの実際の判定欄full_census、trials_compared、mismatch、'
             'memory_state_hash_changes、existing_rng_consumedを確認するよう直してから開始した。'
             'この欄名の修正で模型・注意の計算を変えていない。停止と修正の原記録も同フォルダに残す。\n\n')
    text += ('新しい注意学習は640本・1,113,600試行の記録。比較用腕0を含めると680条件・1,183,200行、'
             'ドア107,202行。物理的には各世界の同じ3,153ドア試行（通常2,541、例外612）を各条件で比較した。'
             '非ドア1,012,704件の新しい注意あり回答が元と一字一句一致。'
             '正解の実候補が無い試行から正解への変化は全条件0件。保存済みの入力240ファイルのsha256は実行前後で一致。\n')
    text += '\n### 正解・外れ・黙り（ドア課題、日別）\n'
    lines = []
    for world in ('1', '2'):
        for arm, beta, eta in [(0, 5., .05)]+[(a, b, e) for a in (1, 2) for b, e in GRID]:
            for day in ('normal', 'exception'):
                key = world, str(arm), str(beta), str(eta), day
                v = totals[key]
                lines.append([world, arm, beta, eta, day, v['total'],
                              *[f"{v[x]} ({v[x]/v['total']:.1%})" for x in ('correct', 'wrong', 'silent')]])
    text += table(['世界', '腕', 'β', 'η', '日', '試行数', '正解', '外れ', '黙り'], lines)
    errors = grouped(rows(AGG/'original_errors.csv'), ('world', 'arm', 'beta', 'eta', 'day', 'error_type'), ('total', 'correct', 'wrong', 'silent'))
    error_lines = []
    for world in ('1', '2'):
        for arm in (1, 2):
            for beta, eta in GRID:
                for day in ('normal', 'exception'):
                    for why in ('selection_error', 'distinction_loss'):
                        v = errors[(world, str(arm), str(beta), str(eta), day, why)]
                        error_lines.append([world, arm, beta, eta, day, why, *[v[x] for x in ('total', 'correct', 'wrong', 'silent')]])
    write_csv(DEST/'original_error_destinations.csv',
              (dict(zip(('world', 'arm', 'beta', 'eta', 'day', 'error_type', 'baseline_count', 'correct', 'wrong', 'silent'), line)) for line in error_lines),
              ('world', 'arm', 'beta', 'eta', 'day', 'error_type', 'baseline_count', 'correct', 'wrong', 'silent'))
    text += '\n### 腕0の例外ドアの外れ：選び間違い・区別の喪失からの移り先\n'
    text += table(['世界', '腕', 'β', 'η', '日', '元の分類', '元の件数', '正解へ', '外れのまま', '黙りへ'],
                  [line for line in error_lines if line[4] == 'exception'])
    text += ('選び間違い＝門・黙りまで含む固定候補に正解の回答がある元の外れ、区別の喪失＝それが無い元の外れ。'
             '門下を含む後者から正解への変化は0件。通常日を含む全件と種別はCSVに保存。\n')
    transitions = rows(AGG/'transitions.csv')
    changes = defaultdict(Counter)
    for row in transitions:
        if row['source_arm'] == '0' and row['task'] == 'door' and row['day'] == 'normal':
            key = row['world'], row['target_arm'], row['beta'], row['eta']
            changes[key][(row['before'], row['after'])] += int(row['count'])
    damage = []
    for world in ('1', '2'):
        for arm in ('1', '2'):
            for beta, eta in GRID:
                v = changes[(world, arm, str(beta), str(eta))]
                before_correct = sum(v[('correct', after)] for after in ('correct', 'wrong', 'silent'))
                assert sum(v.values()) == 2541
                damage.append([world, arm, beta, eta, before_correct, v[('correct', 'wrong')], v[('correct', 'silent')],
                               v[('wrong', 'correct')], v[('wrong', 'silent')]])
    text += '\n### 通常日の元の正解・外れからの変化（ドア課題）\n'
    text += table(['世界', '行先腕', 'β', 'η', '元の正解数', '正解→外れ', '正解→黙り', '外れ→正解', '外れ→黙り'], damage)
    write_csv(DEST/'normal_day_changes.csv', (dict(zip(('world', 'arm', 'beta', 'eta', 'baseline_correct', 'correct_to_wrong', 'correct_to_silent', 'wrong_to_correct', 'wrong_to_silent'), line)) for line in damage),
              ('world', 'arm', 'beta', 'eta', 'baseline_correct', 'correct_to_wrong', 'correct_to_silent', 'wrong_to_correct', 'wrong_to_silent'))
    text += '\n### 全名の最終の重みと段Cと同じ原表\n\n'
    text += ('[全名の最終重み：世界・腕・β・η・名前ごとの平均／最小／最大／見た種数](attn_large_eta_grid_2026-10-05/final_weights.csv) と'
             ' [種別・全名の最終重み](attn_large_eta_grid_2026-10-05/seed_final_weights.csv) を保存。'
             '見ていない名前を0として埋めず、見た種の最終値だけを数える。腕2のhold/hold_bは全件1。'
             '全名の100試行ごとの推移と毎試行の更新前後の値も残す。\n\n')
    text += ('回答四区分とhold/hold_b、正解・外れ・黙り、正解候補が門上／門下／無し、'
             '腕間の全移行、選び間違いと区別の喪失からの移り先、更新理由、Lの推移、'
             'd′・c、名前を初めて見た試行を、店・日・種・条件別の同じ段CのCSVに保存した。'
             '大きな種別推移表はCSV.gz。割合の分母は各行の全ドア試行。\n\n'
             '世界1は店ごとの通常／例外のドア名が同じで、独立な例外ドア列は適用不能、d′・cは算出しない。'
             '世界2のd′・cは二つのドア回答だけの補助値。その他・黙りを除外し別記、'
             '率0又は1では全4セルに0.5を足し、回答が無い場合は算出不能。押す／引くへの対応は未確認なのでコード名のまま。\n\n'
             '腕0の学習記録のLはnull。開示されたドア試行で正解候補がある場合だけβ=5の事後診断Lを表示し、更新しない。'
             '非開示ではこの診断Lも計算しない。注意ありの学習は新格子の記録を使う。'
             '全候補のQによる投票は記録だけで、回答や学習に使わない。追加の段Dの介入は行っていない。\n\n')
    text += ('[原記録のパス・容量・sha256](attn_large_eta_grid_2026-10-05/raw_manifest.json)、'
             '[再利用した入力のパス・容量・sha256](attn_large_eta_grid_2026-10-05/input_manifest.json)、'
             '[全40種の集計の検査](attn_large_eta_grid_2026-10-05/all_C.json)、'
             '[集計前の条件の記録](attn_large_eta_grid_2026-10-05/pre_result_decisions.json)。'
             '原side・試行ごとのf・開示・更新理由・L・重みの前後・投票の記録は削除していない。\n\n')
    text += f"機械の記録：開始時空き{machine[0]['disk_free_gib']:.2f}GiB、稼働中の最小空き{min(r['disk_free_gib'] for r in machine):.2f}GiB、スワップ{min(swaps):.2f}〜{max(swaps):.2f}MB、熱・性能の警告0件。開始前・各種の重い計算前・稼働中の空き、メモリ、スワップ、他の計算と予約、未登録の重いPython、本人のRSS標本をJSONLに保存。各種はjobs.py run --wait --mem 0.5 --disk-path実出力先、受付に通ったものだけ最大4本。全集計は重み表を逐次結合し、0.5GB予約で1本。集計・全バイトの検算の本人の最大RSSは{streamed['peak_rss_self_bytes']/1024**2:.2f}MiB。最初は2GB予約で受付待ちだったが、元の同じ段C/Dの127標本の最大RSS151.8MBを根拠に種別予約を0.5GBへ見直した。実計算の開始前に自分の待機処理だけを止め、待機記録を保存して再登録した。受付条件を変えず、他セッションには介入していない。稼働中のRSS標本は真のピークではない。\n\n"
    text += ('確かめた数は、同じ固定記憶の指定の全条件・種1〜20の回答、注意学習、分類表、最終重みである。'
             '記憶への間接効果と本番の設定値は確かめていない。結果の良し悪しは記していない。段③には進まない。\n')
    current = old.replace('現在のコミット **`697c0259`**', '段C・D完了時のコミット **`697c0259`**', 1)+text
    summary_line = '段Bの全関門を通過し、両世界・種1〜20の固定記憶の三腕・九点の段Cと段Dを完了。'
    assert summary_line in current
    current = current.replace(summary_line, summary_line+' 追加の大きなηの8点×2腕も、同じ保存済み候補と記憶で完了（追加のコードb40a6d4e）。', 1)
    assert current.startswith(prefix)
    REPORT.write_text(current)
    (DEST/'README.md').write_text('# 大きなηの格子の保存物\n\n本人にドア課題の指示が伝えられるとみなしheld_out_is_doorを使う。\n\n'
                                '全表・種別表は段Cと同じ列。大きなCSVはgzip。追加格子の全名の最終重みはfinal_weights.csvとseed_final_weights.csv。\n\n'
                                +''.join('- '+name+'\n' for name in copied))
    save = {'time': moment, 'report': str(REPORT), 'evidence': str(DEST), 'raw_files': len(manifest),
            'inputs': len(inputs), 'seed_final_weights_rows': len(final), 'final_weights_rows': len(weights),
            'all_tables_saved': True, 'report_pushed': False,
            'peak_rss_self_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (JOB/'report_built.json').write_text(json.dumps(save, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(save, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
