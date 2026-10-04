"""追加診断の全表・件別CSV・検算根拠をresults枝へ一度だけ保存する。"""
import csv
import gzip
import hashlib
import json
import shutil
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

JOB = Path(__file__).resolve().parent
BASE = JOB.parent
REPORT = BASE/'report'
DEST = REPORT/'control/attn_seal_diagnostic_2026-10-05'
MAIN = REPORT/'control/2026-10-03_注意の選択_Codex2.md'


def read_csv(name):
    with (JOB/name).open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def table(fields, values):
    return ['| '+' | '.join(fields)+' |', '| '+' | '.join(['---']*len(fields))+' |'] + [
        '| '+' | '.join(str(v).replace('|', '／') for v in row)+' |' for row in values]


def main():
    if DEST.exists():
        raise RuntimeError('既存の診断報告を上書きしない')
    validation = json.loads((JOB/'score_verification.json').read_text())
    assert validation['passed']
    audit = json.loads((JOB/'tabulation_check.json').read_text())
    trials, pairs, improvements = read_csv('cases.csv'), read_csv('all_correct_pairs.csv'), read_csv('online_wrong_to_correct.csv')
    assert len(trials) == 235 and len({(r['seed'], r['trial']) for r in trials}) == 235
    assert Counter(r['day'] for r in trials) == {'exception': 136, 'normal': 99}
    assert len(pairs) == 506 and sum(bool(r['correct_R']) for r in pairs) == 488
    assert sum(not r['correct_R'] for r in trials) == 18
    assert Counter(r['availability'] for r in trials if not r['correct_R']) == {'below': 13, 'absent': 5}
    assert Counter(r['arm'] for r in improvements if r['day'] == 'exception') == {'1': 4, '2': 3}
    assert all(r['best_correct_is_actual_selection'] == 'True' for r in improvements)
    extracted = [json.loads(line) for line in (JOB/'extracted_cases.jsonl').read_text().splitlines()]
    input_lookup = {(str(c['seed']), str(c['trial'])): c for c in extracted}
    for row in trials:
        c = input_lookup[(row['seed'], row['trial'])]
        assert row['selected_R'] == c['selected_R']
        assert row['selected_seal_seats'] == json.dumps(c['selected_seal']['seats'], ensure_ascii=False, separators=(',', ':'))
        best = c['correct_candidates'][0] if c['correct_candidates'] else None
        assert row['correct_R'] == (best['R'] if best else '')
        assert int(row['seed']) in range(1, 21)
    prefix = MAIN.read_bytes()
    assert '段②の追加診断：シールの席の状態'.encode() not in prefix
    DEST.mkdir()
    for name in ('cases.csv', 'all_correct_pairs.csv', 'online_wrong_to_correct.csv', 'state_counts.csv', 'class_counts.csv',
                 'all_correct_class_counts.csv', 'gap_by_class.csv', 'extraction_check.json', 'tabulation_check.json',
                 'score_verification.json', 'input_manifest.json', 'verification_input_manifest.json',
                 'machine_registered.jsonl', 'registration_registered.jsonl', 'commands.jsonl', 'status.json',
                 'extract_records.py', 'verify_score_arithmetic.py', 'tabulate_records.py', 'write_report.py',
                 'run_registered.py', 'run_verification_registered.py', 'run_tables_registered.py'):
        shutil.copy2(JOB/name, DEST/name)
    for day, name in [('exception', 'exception_selection_errors_136.csv'), ('normal', 'normal_errors_99.csv')]:
        with (DEST/name).open('x', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(trials[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(r for r in trials if r['day'] == day)
    with (DEST/'extracted_cases.jsonl.gz').open('xb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as output:
            output.write((JOB/'extracted_cases.jsonl').read_bytes())
    with gzip.open(DEST/'extracted_cases.jsonl.gz', 'rb') as stream:
        assert stream.read() == (JOB/'extracted_cases.jsonl').read_bytes()
    machine = [json.loads(line) for line in (JOB/'machine_registered.jsonl').read_text().splitlines()]
    assert all(not m['thermal_warnings'] and m['swap_window_ok'] and m['disk_free_gib'] >= 18.5 for m in machine)
    assert len({m['swap_mb'] for m in machine}) == 1
    approval = {'human_authorization': '2026-10-05 アストラ承認の返信。保存係数と最終重みからのQの算術だけを許可。照合・回答・勾配・学習は呼ばない。',
                'verification_required': ['試行時重みから全候補Qと保存Qの浮動小数まで全件一致', '最終重みから段Dの腕1選択候補Qと保存Qの浮動小数まで全件一致'],
                'normalization': '最終値のまま、再正規化なし。腕2はhold/hold_bを1。',
                'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=BASE/'source', text=True).strip(),
                'received_date_jst': '2026-10-05', 'report_written_at': datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()}
    (DEST/'authorization_and_scope.json').write_text(json.dumps(approval, ensure_ascii=False, indent=2)+'\n')
    lines = ['', '', '## 段②の追加診断：シールの席の状態', '',
        f'2026-10-05朝のアストラ承認による追加診断。世界2・種1〜20、主の仮の一組β=5・η=0.05を対象とする。腕0の例外ドアの選び間違い136件と通常ドアの外れ99件、計235件を保存記録から抽出した。模型・注意の走行、照合・回答・勾配・学習は呼んでいない。科学コードは`{approval["source_commit"][:8]}`のまま。段③には進んでいない。', '',
        '**最終重みでの全候補の Q は、保存済みの係数からの事後の算術計算。** 初めの記録だけという指示では全候補の最終Qが不足していたため、2026-10-05の返信でこの算術だけが追加承認された。各種の最終試行（1739、0始まり）の後の重みをそのまま代入し、正規化し直さない。腕2は三つの点のすべてでhold・hold_bを1に固定する。新たな回答は出していない。', '',
        '### 席・候補・点差の決め方', '',
        '- シール席は元の`seedNNN.shop.jsonl`の`shop_seat`・`which=sig`に記録された定義名・登録試行・席番号で判定する。これは既存`sealmem.py`の`shopworld.IDS[relation_id]==sig`と同じ席を記録したもの。世界の再生成や対応づけは行わない。',
        '- 試行tの予測前の記憶は、元台帳の試行t−1のfull/deltaから、定義と履歴の記録だけを展開する。Fはaliveの名前、Hは履歴にある名前と回数、Uは名前なし、席が無ければ「席が無い」。元のshop sideの状態遷移とも全対象席で照合した。Uの消去前の名前は読まない。対象の選択定義と門上正解候補には、シールが複数ある定義は0件。',
        '- 門上の正解候補は、段Bで開示前に固定した門・投影・穴埋め込みの候補の回答が、保存正解の名前と引数に一致する定義。正解候補が複数ある試行では、元N3の`rank_n3`が最小の候補を代表とする（元の同点順を含む）。全正解候補との488組も別CSVに残した。注意ありの点を見て代表を選び直していない。',
        '- 点差は **Δ=Q(正解候補)−Q(腕0で選ばれた誤った定義)**。両定義を固定して注意なしΔ0と最終重みΔ1・Δ2を比べ、変化はΔ1−Δ0・Δ2−Δ0。正の変化は正解候補の相対点が上がったことだけを表す。門上候補が無い18件では点差は算出不能とし、空欄を0に置き換えない。',
        '- ドア課題の指示が本人に伝えられるとみなし`held_out_is_door`を使う承認済みの仮定は維持。以下の「正解への変化」は試行時の保存済みのオンライン回答であり、最終重みの点差とは別時点の記録。', '',
        '### 事前の全件検算', '',
        '保存係数リストと同じ足す順、`Fraction(str(重み))`による同じ分数算術で三つの点を加え、最後にfloatへ変換した。照合等の部品はimportせず、保存データだけを使った。float.hexで全ビット一致を検査し、段Dは保存分数も厳密一致。許容は入れていない。', '']
    lines += table(['検算（世界2・種1〜20・β=5・η=0.05）', '件数', '不一致', '最大絶対差'], [
        ['腕1・全ドア試行の全候補の試行時Q', 91897, 0, 0],
        ['腕2・全ドア試行の全候補の試行時Q', 91897, 0, 0],
        ['腕1・段Dの最終重みの選択候補Q', 3153, 0, 0],
        ['対象の腕0の選択定義235＋全正解候補488の注意なしQ', 723, 0, 0]])
    lines += ['', '検算根拠：[score_verification.json](attn_seal_diagnostic_2026-10-05/score_verification.json)。すべて一致した後にだけ、最終重みの候補間の点差を算出した。', '',
        '### 区分ごとの試行数（門上正解候補は元N3の代表）', '',
        'F・Hの角括弧内は名前。Hの回数を含む履歴は件別CSVに保存。以下の各行は試行を重複して数えない。0件の区分は表に行を作らず、合計の確認に含めた。', '']
    class_rows = []
    for entry in audit['class_counts']:
        day, availability, selected, correct = entry['key']
        matching = [r for r in trials if (r['day'], r['availability'], r['selected_seal_class'], r['correct_seal_class']) == tuple(entry['key'])]
        assert len(matching) == entry['count']
        class_rows.append(['例外' if day == 'exception' else '通常', {'above': '門上', 'below': '門下のみ', 'absent': '無し'}[availability],
                           selected, correct, entry['count'], sum(r['arm1_online_outcome'] == 'correct' for r in matching),
                           sum(r['arm2_online_outcome'] == 'correct' for r in matching)])
    lines += table(['日', '正解候補', '誤った選択定義のシール', '代表正解候補のシール', '件数', '腕1で正解へ', '腕2で正解へ'], class_rows)
    lines += ['', '例外136件：誤った選択定義はH84・U52・F0・席なし0。代表の正解候補はF102・H34・U0・席なし0。通常99件：選択定義はH98・F1・U0・席なし0。門上正解候補は81件（代表F71・H9・席なし1）で、残りは門下のみ13件・正解候補無し5件。', '',
        '### 全門上正解候補との組数（試行数と区別する）', '',
        '同一試行に正解候補が複数あれば複数組になる。代表表には出ない「シール席が無い」正解候補も省略しない。', '']
    lines += table(['日', '誤った選択定義', '門上正解候補', '候補の組数'], [
        ['例外' if r['day'] == 'exception' else '通常', r['selected_class'], r['correct_class'], r['candidate_pairs']]
        for r in read_csv('all_correct_class_counts.csv')])
    lines += ['', '例外271組、通常217組、合計488組。候補が無い通常18件は組数に含めない。', '',
        '### 区分別の点差（代表候補、各欄は試行平均）', '',
        '**最終重みでの全候補の Q は、保存済みの係数からの事後の算術計算。** Δの向きは正解−誤選択。表示は小数9桁、件別CSVと区分CSVには丸め前の値、区分CSVには最小・最大も保存。', '']
    lines += table(['日', '誤選択／代表正解のシール', '件数', 'Δ0 注意なし', 'Δ1 最終', 'Δ1−Δ0', 'Δ2 最終', 'Δ2−Δ0'], [
        ['例外' if r['day'] == 'exception' else '通常', r['selected_class']+' ／ '+r['best_correct_class'], r['trials'],
         *[f'{float(r[k]):.9f}' for k in ('gap0_correct_minus_selected_mean', 'gap1_final_mean', 'gap_change_arm1_mean', 'gap2_final_mean', 'gap_change_arm2_mean')]]
        for r in read_csv('gap_by_class.csv')])
    lines += ['', '通常18件の点差は算出不能。選択定義だけの最終Qは件別CSVに残し、正解候補のQ・点差・変化は空欄とした。', '',
        '### 例外で正解へ変わった4件／3件の所在', '',
        '両腕に共通する3試行を重複した7試行として数えない。4試行とも、実際に選ばれた正解候補は代表候補と同じ。 4試行とも注意なしでは両定義のQが同点（Δ0=0）。', '']
    repaired = [r for r in trials if r['day'] == 'exception' and (r['arm1_online_outcome'] == 'correct' or r['arm2_online_outcome'] == 'correct')]
    lines += table(['種', '試行（0始まり）', '店', '誤選択／正解のシール', '腕1の保存回答', '腕2の保存回答', 'Δ0', 'Δ1 最終', 'Δ2 最終'], [
        [r['seed'], r['trial'], r['shop'], r['selected_seal_class']+' ／ '+r['correct_seal_class'],
         r['arm1_online_outcome'], r['arm2_online_outcome'],
         *[f'{float(r[k]):.9f}' for k in ('gap0_correct_minus_selected', 'gap1_final', 'gap2_final')]] for r in repaired])
    lines += ['', '腕1の4件はU／H[sig_e]の3件とH[sig_e]／H[sig_e]の1件。腕2の3件はU／H[sig_e]の3件。定義名・席番号・履歴・試行別の点差はCSVに保存した。', '',
        '### 保存先・機械の記録', '',
        '- [例外の136件](attn_seal_diagnostic_2026-10-05/exception_selection_errors_136.csv)、[通常の99件](attn_seal_diagnostic_2026-10-05/normal_errors_99.csv)、[235件の統合CSV](attn_seal_diagnostic_2026-10-05/cases.csv)。候補の全一覧は統合CSVの`all_correct_seals`、代表以外の点差は[全候補との組のCSV](attn_seal_diagnostic_2026-10-05/all_correct_pairs.csv)（488組＋門上候補の無い18行）。',
        '- [名前を含む区分表](attn_seal_diagnostic_2026-10-05/class_counts.csv)、[F/H/Uの区分表](attn_seal_diagnostic_2026-10-05/state_counts.csv)、[区分別の点差](attn_seal_diagnostic_2026-10-05/gap_by_class.csv)、[全候補の組の区分表](attn_seal_diagnostic_2026-10-05/all_correct_class_counts.csv)、[保存回答の外れ→正解](attn_seal_diagnostic_2026-10-05/online_wrong_to_correct.csv)。',
        '- [抽出原記録](attn_seal_diagnostic_2026-10-05/extracted_cases.jsonl.gz)には定義の席・点の係数・最終重みを含む。[入力ファイルのsha256](attn_seal_diagnostic_2026-10-05/input_manifest.json)と[検算に追加した段Dのsha256](attn_seal_diagnostic_2026-10-05/verification_input_manifest.json)には明示した種1〜20のパスだけを保存。元の記録は無変更。抽出・算術・表の解析スクリプトも同フォルダに保存した。',
        f'- 抽出・検算・点差表は各々受付表で2GBを予約し、並列1、実出力先を指定して実行。[機械記録](attn_seal_diagnostic_2026-10-05/machine_registered.jsonl)の空き最小{min(m["disk_free_gib"] for m in machine):.2f}GiB、スワップ{machine[0]["swap_mb"]:.2f}MBで増加なし、熱・性能警告なし、未登録の重いPythonなし。抽出の最大RSS{json.loads((JOB/"extraction_check.json").read_text())["peak_rss_bytes"]/1024**2:.2f}MiB、検算の最大RSS{validation["peak_rss_bytes"]/1024**2:.2f}MiB。メモリと他の処理の受付状況も各時点に記録。',
        '- 確認したのは保存された席・回答・点の係数と重みの算術である。この診断から結果の良し悪しや因果関係を判断していない。新しい走行、段③、種21〜40は実施していない。自動継続は停止したまま。', '']
    addition = '\n'.join(lines).encode()
    MAIN.write_bytes(prefix+addition)
    assert MAIN.read_bytes()[:len(prefix)] == prefix
    review = {'passed': True, 'cases': 235, 'exception': 136, 'normal': 99, 'candidate_pairs': 488,
              'no_above_candidate': 18, 'score_validation_passed': True, 'baseline_Q_checks': 723,
              'forecast_and_existing_report_unchanged': True, 'report_prefix_sha256': hashlib.sha256(prefix).hexdigest(),
              'new_mapping_prediction_gradient_learning_calls': 0, 'phase3_started': False,
              'experimental_seeds_read': list(range(1,21)), 'created_at': approval['report_written_at']}
    (DEST/'report_review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2)+'\n')
    manifest = {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in sorted(DEST.iterdir())}
    (DEST/'artifact_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    (JOB/'report_written.json').write_text(json.dumps({'report': str(MAIN), 'evidence': str(DEST), **review}, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(review, ensure_ascii=False))


if __name__ == '__main__':
    main()
