"""限定範囲の段2承認を受けた集計を、元の停止報告に追記する。"""
from __future__ import annotations
import csv
import hashlib
import json
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
import audit

BASE = Path(__file__).resolve().parent
DATA = BASE/'stage2'
ROOT = BASE.parent
REPO = ROOT/'report-results'
NAME = '2026-10-05_動詞の世界_Hの式の引っ張り_Codex'
MARKER = '## 追加承認後の段2：有回答を中心にした既存記録の集計'


def rows(name):
    with (DATA/name).open() as f:
        yield from csv.DictReader(f)


def number(row, key):
    return int(row.get(key) or 0)


def main():
    result = json.loads((DATA/'result.json').read_text())
    assert result['state'] == 'complete' and result['runs'] == 30 and result['model_reruns'] == 0
    assert result['gate1_mismatches'] == result['H_answer_formula_mismatches'] == 0
    verification = json.loads((DATA/'verification.json').read_text())
    assert verification['state'] == 'verified' and verification['mismatches'] == 0
    code = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT/'source', text=True).strip()
    assert code == '7f48b75badd3854616449d9ab6464ccbb5f7b011'
    totals = defaultdict(Counter)
    for row in rows('coverage.csv'):
        for phase in ('training', 'probe'):
            totals[(row['arm'], row['U'], phase)].update({k.split(':', 1)[1]: int(v) for k, v in row.items() if k.startswith(phase+':') and v})
    pulls = defaultdict(Counter)
    for row in rows('H_transitions.csv'):
        if row['category'] == 'H-引っ張り':
            pulls[(row['arm'], row['U'], row['phase'])][row['subtype']] += number(row, 'count')
    ors = defaultdict(Counter)
    for row in rows('overregularization_breakdown.csv'):
        ors[(row['arm'], row['U'], row['phase'])][row['category']] += number(row, 'REG')
    cf = defaultdict(Counter)
    for row in rows('counterfactual.csv'):
        cf[(row['arm'], row['U'], row['phase'])].update({k: number(row, k) for k in (
            'changed', 'overREG_to_correct', 'correct_to_wrong', 'correct_to_silence', 'regular_changed', 'silence_to_seat_answer_lower_bound')})
    rc = defaultdict(Counter)
    for row in rows('rates_per_verb.csv'):
        if row['verb_class'] == 'irregular':
            rc[(row['arm'], row['U'], row['phase'])].update({k: number(row, k) for k in ('queries', 'REG', 'correct', 'abstain', 'other')})
    mixed = defaultdict(list)
    for row in rows('mixed_history_definitions.csv'):
        if row['t'] == '5000':
            mixed[(row['arm'], row['U'])].append(row)
    command = {
        'stage2_authorization': '2026-10-05：有回答と対象席が記録された黙りに限定し、未特定は別欄。再走行しない。',
        'model_original_commit': json.loads((ROOT/'stage3_night/plan.json').read_text())['commit'],
        'read_environment_work_commit': code, 'model_reruns': 0,
        'analysis_command': 'python3.12 ~/jobs/jobs.py run --wait --owner Codex-動詞H式段2既存記録 --mem 0.4 --disk-path ./h_formula_2026-10-05/stage2 -- /usr/bin/time -l python3.12 ./h_formula_2026-10-05/stage2.py',
        'corrected_analysis_command': 'python3.12 ~/jobs/jobs.py run --wait --owner Codex-動詞H式段2区分修正 --mem 0.4 --disk-path ./h_formula_2026-10-05/stage2 -- /usr/bin/time -l python3.12 ./h_formula_2026-10-05/stage2.py',
        'initial_read_only_pass': {'elapsed_seconds_time': 1150.0, 'peak_rss_bytes_time': 178896896,
            'unidentified_training_initial': 735, 'unidentified_training_required': 740,
            'reason_for_repeat': '学習中のno_projectable_relationを理由名だけで席なしに分けた5件。候補分布が非空の件を未特定へ戻し、30本の記録を再読。模型再走行0。',
            'initial_script_sha256': hashlib.sha256((BASE/'stage2_partial_first/stage2.py').read_bytes()).hexdigest()},
        'report_command': 'python3.12 ~/jobs/jobs.py run --wait --owner Codex-動詞H式段2報告 --mem 0.4 --disk-path ./h_formula_2026-10-05/stage2 -- python3.12 ./h_formula_2026-10-05/report_stage2.py',
        'verification_command': 'python3.12 ~/jobs/jobs.py run --wait --owner Codex-動詞H式段2全件照合 --mem 0.4 --disk-path ./h_formula_2026-10-05/stage2 -- python3.12 ./h_formula_2026-10-05/verify_stage2.py',
        'publish_command': f'python3.12 ~/jobs/jobs.py run --wait --owner Codex-動詞H式段2報告送信 --mem 0.4 --disk-path ./report-results/control/{NAME} -- python3.12 ./h_formula_2026-10-05/publish_stage2.py',
        'working_directory': 'codex_verb_2026-10-04', 'probe_expected_arguments': '原コードの固定試験の種 probe\\x1f<seed>、試行0、entity:a と entity:b の opaque_id。予測・照合・世界抽選は呼ばず、固定IDだけ照合。',
        'training_selection_error_or_distinction_loss': '原走行のanalysis/cases.jsonl.gzからtrialでそのまま結合。分類の再計算0。',
        'probe_selection_error_or_distinction_loss': '元のprobe記録に分類が無い。not_recorded_probeとして保持し推定しない。'}
    audit.dump(DATA/'commands_and_commits.json', command)
    manifests = list(rows('input_manifest.csv'))
    for p in (BASE/'report_stage2.py', BASE/'publish_stage2.py', ROOT/'stage3_night/plan.json',
              ROOT/'stage3_night/aggregate/overregularization_per_verb.csv', ROOT/'source/tools/verb/U-011_seed_verb.json'):
        manifests.append(audit.fingerprint(p))
    audit.csv_out(DATA/'input_manifest.csv', list({r['path']: r for r in manifests}.values()))
    md = ['', MARKER, '',
          '2026-10-05の追加指示により、段1の記録不足を推定で埋めず、段2を限定範囲で実施した。上の停止報告はその時点の記録として残す。既存30本のみを読み、模型の再走行0本。模型・照合・式・既存の分類コードの変更0。種21〜40は読まず、走らせていない。別の二軸下見は継続している。結果の良し悪しは評価しない。', '',
          '### 対象と区分', '',
          '学習中の過去形質問13,650件、非学習試験72,000件を全件表に保存した。Hの有回答49,178件（学習中8,240・試験40,938）は、予測直前の履歴とp̂から式を再確認して全件一致。既存の語別・腕別・時点別の質問数とREG件数も480行すべて再一致した。', '',
          'Fは実際に固定名を答えた席。H-一致は同じ階の履歴最多が一つで式の答えと一致する件。H-引っ張りは最多への置き換えで答えが変わる件で、`unique_majority`（単独の最多名から別名へ）と`history_maximum_tie`（最多同点の黙りから式が一名を選ぶ）を分けた。後者を「不規則名の単独多数がREGへ変わった件」と数えない。H-黙りは対象席が特定され、その席の式の最大重みが同点だった件だけ。Uは対象席がUと確定した件。他の理由は既存のabstain_reasonを残す。対象席が決まらない黙りは別の区分にし、履歴や席状態を推定していない。', '',
          '過剰な規則化の学習中の分類は、既存の`analysis/cases.jsonl.gz`の`selection_error`／`distinction_loss`をそのまま結合した。試験には同じ分類が記録されていないため、`not_recorded_probe`（既存分類なし）とした。分類を補う予測・照合は行っていない。', '',
          f"H有回答のうち **{verification['counts']['H_zero_history_total']}件** は履歴表に名前の欄が残るが、同じ階の回数の合計が0だった。現行の`_weights`は合計0のときp̂だけを使う。この既存分岐も厳密に再現した。履歴最多の検算では記録に残る0回の欄も保持し、同じ名前だけが残れば最多はその名前。同点なら反実仮想は黙りとする。例はverification.jsonに保存。式を変更していない。", '',
          '|保持|U|段階|全質問|有回答|F|H-一致|H-引っ張り（単独最多）|H-引っ張り（最多同点）|H-黙り|U|その他|席未特定の黙り|',
          '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for k, c in sorted(totals.items()):
        p = pulls[k]
        md.append(f"|{k[0]}|{k[1]}|{k[2]}|{c['queries']}|{c['answered']}|{c['F']}|{c['H-一致']}|{p['unique_majority']}|{p['history_maximum_tie']}|{c['H-黙り']}|{c['U']}|{c['その他']}|{c['席が未特定の黙り']}|")
    md += ['', '学習中740件・試験8,260件の席未特定の黙りは、腕×U×種×500試行区間×既存理由の別表にした。定義が使われなかった件、no_projectable_relationで答える席が無いと分かる件は「その他」であり、未特定に混ぜない。', '',
           '### 過剰な規則化の内訳', '',
           '|保持|U|段階|REG合計|F|H-一致|H-引っ張り|H-黙り|U|その他|', '|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for k in sorted(totals):
        c = ors[k]
        md.append(f"|{k[0]}|{k[1]}|{k[2]}|{sum(c.values())}|{c['F']}|{c['H-一致']}|{c['H-引っ張り']}|{c['H-黙り']}|{c['U']}|{c['その他']}|")
    md += ['', '細表は区分×既存分類×腕×U×種×V33〜V40×時点×学習／試験で、REG件数を数えた。各成分の率の分母は、同じ腕・U・種・語・時点・段階の全区分を合わせたMarcus分母、及び全質問数。分類はREG事例だけの記録なので、正答を選び間違い等に推定分類して分母を作っていない。', '',
           '### 履歴最多に替えた反実仮想', '',
           '実際に答えたHの席だけを履歴の同じ階の最多名に替え、最多が同点なら黙りとした。選ばれた定義・写像・引数・以後の履歴を固定した、その質問一回の記録上の計算である。実際の正答及び正答に変わる件は、述語と引数の両方を照合した。新語には正誤の基準が無いので、答えの遷移だけを残す。', '',
           '|保持|U|段階|答えが変わる全件|REG誤答→正答|正答→外れ|正答→黙り|規則動詞の答えが変わる|特定したHの黙り→席の答え（下限）|',
           '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for k in sorted(totals):
        c = cf[k]
        md.append(f"|{k[0]}|{k[1]}|{k[2]}|{c['changed']}|{c['overREG_to_correct']}|{c['correct_to_wrong']}|{c['correct_to_silence']}|{c['regular_changed']}|{c['silence_to_seat_answer_lower_bound']}|")
    md += ['', '「黙り→答え」は対象席が確定したHの同点黙りだけを対象にした下限。対象席が未特定の9,000件はこの反実仮想に含めない。対象席以外の門・候補・同点を変えた全予測の反実仮想は行わない。全問への効果、学習し直した後の効果をこの表から推定しない。', '',
           '### 二つの分母', '',
           '|保持|U|段階|不規則の全質問|正答|REG|黙り|その他の誤答|Marcus分母|REG／Marcus分母|REG／全質問|',
           '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for k, c in sorted(rc.items()):
        den = c['correct'] + c['REG']
        mr = f"{c['REG']/den:.9f}" if den else '欠測'
        qr = f"{c['REG']/c['queries']:.9f}" if c['queries'] else '欠測'
        md.append(f"|{k[0]}|{k[1]}|{k[2]}|{c['queries']}|{c['correct']}|{c['REG']}|{c['abstain']}|{c['other']}|{den}|{mr}|{qr}|")
    md += ['', 'Marcus分母は正しいIRR_k＋REG。全質問の分母は黙り・他の誤答・席未特定も含む。語別の500試行区間表と種を合わせた表を併記した。問いが0回だった不規則語の区間も明示し、率は欠測とした。規則語・新語の行は反実仮想と件数の材料として残し、Marcus率は適用外（空欄）。学習中のbinはt//500（tは0始まり）、試験は100試行ごとの完了時点なのでbin=(t−1)//500（500試行終了の試験は0番区間）。最終t=5000は9番区間。', '',
           '### 混ざった履歴の定義数', '',
           '各500試行が終わった状態を読み、誕生時の関係IDが過去形の位置0.0.0だった席を数えた。定義ごとに一回だけ数え、Hで履歴表に名前の欄が二つ以上ある定義、そのうちREGとIRR名の両方を含む定義を残した。0回の欄も記録どおり保持する。予測に使われた定義だけに限定していない。300行（30本×10時点）のCSVが全時点の値である。', '',
           '|保持|U|最終時点の個体数|過去形Hを持つ定義の合計|二名以上の合計|REGとIRR両方の合計|',
           '|---|---|---:|---:|---:|---:|']
    for k, rs in sorted(mixed.items()):
        assert len(rs) == 5
        sums = [sum(number(r, key) for r in rs) for key in ('past_H_definitions', 'past_H_multiple_names_definitions', 'past_H_REG_and_IRR_definitions')]
        md.append(f'|{k[0]}|{k[1]}|5|{sums[0]}|{sums[1]}|{sums[2]}|')
    md += ['', '上表の合計は5個体が別々に持つ定義の数を足した値で、個体をまたぐ定義の同一視はしていない。', '',
           '### CSVと再現証跡', '',
           f'[全過去形質問]({NAME}/stage2/past_questions.csv)、[区分別件数]({NAME}/stage2/categories.csv)、[過剰な規則化の内訳]({NAME}/stage2/overregularization_breakdown.csv)、[Hの変化前後]({NAME}/stage2/H_transitions.csv)、[反実仮想]({NAME}/stage2/counterfactual.csv)、[席未特定の黙り]({NAME}/stage2/unidentified_silence.csv)、[混合履歴の定義数]({NAME}/stage2/mixed_history_definitions.csv)、[種別の率]({NAME}/stage2/rates_per_verb.csv)、[種を合わせた率]({NAME}/stage2/rates_pooled_seeds.csv)。', '',
           f'[段2の結果と照合件数]({NAME}/stage2/result.json)、[全85,650行の独立照合]({NAME}/stage2/verification.json)、[480行の再照合]({NAME}/stage2/gate1_recheck.csv)、[入力パス・sha256]({NAME}/stage2/input_manifest.csv)、[命令・コミット]({NAME}/stage2/commands_and_commits.json)、[読取台本]({NAME}/stage2.py)・[独立照合台本]({NAME}/verify_stage2.py)。入力台帳・answers・ambig・probeは、段1で保存したsha256と再一致。既存分類のcasesのsha256も今回記録した。', '',
           f"読取環境の作業コミット `{code}`、原走行コミット `{command['model_original_commit']}`。台本は模型の作業枝の外に置き、報告枝に証跡として保存。jobs.py run --wait、mem=0.4、disk-pathは実出力先。段2の読取と集計は **{result['elapsed_seconds']:.3f}秒、最大常駐 {result['peak_rss_bytes']:,} bytes**。予測・照合・学習・分類の再計算は0回。", '']
    md += [f"全件CSVを別の台本で読み直し、履歴最多・保存したp̂の回数からの重み・反実仮想・内訳の合計を検算した。不一致{verification['mismatches']}件。独立照合は{verification['elapsed_seconds']:.3f}秒、最大常駐{verification['peak_rss_bytes']:,} bytes。", '',
           '最初の記録読み取りでは、学習中のno_projectable_relationを理由名だけで「席なし」に分け、候補分布が非空の5件を未特定から落としていた。未特定735件と段1の740件の照合で止まり、この読取区分だけを直して既存30本を読み直した。上の表は修正後。最初の読取1150.00秒・最大常駐178,896,896 bytesを別に要した。H回答の式とREG／質問件数の再現の不一致ではなく、黙りを分ける読取台本の区分のずれであり、模型・既存分類の変更や模型再走行は行っていない。最初の出力・台本・終了記録はローカルに保存した。', '']
    md += [f"最初の全件表と修正後の表も比較し、差はこの5件のcategory欄だけで、答え・履歴・重みは全件同じ。具体的な試行はverification.jsonのrepair_examplesに保存した。", '']
    report = REPO/'control'/(NAME+'.md')
    assert MARKER not in report.read_text()
    report.write_text(report.read_text()+'\n'.join(md))
    evidence = REPO/'control'/NAME
    shutil.copytree(DATA, evidence/'stage2', dirs_exist_ok=True, ignore=shutil.ignore_patterns('*_partial.csv'))
    for p in (BASE/'stage2.py', BASE/'report_stage2.py', BASE/'publish_stage2.py', BASE/'verify_stage2.py'):
        shutil.copy2(p, evidence/p.name)
    print(json.dumps({'report': str(report.relative_to(REPO)), 'H_checked': result['counts']['H_answer_checked'],
                      'model_reruns': 0, 'stage2_complete': True}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
