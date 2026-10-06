"""既存記録の診断を、指定された報告と同名のCSVフォルダへ保存する。"""
import csv
import hashlib
import json
import re
import shutil
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
import read_records as rec

BASE = Path(__file__).resolve().parent
NAME = '2026-10-06_動詞の世界_選び間違いの診断_Codex'
REPORT = rec.ROOT / 'report-results'
DEST = REPORT / 'control' / NAME
PATH = REPORT / 'control' / (NAME + '.md')


def git(repo, *args):
    return subprocess.check_output(['git', '-c', 'core.commitGraph=false', *args], cwd=repo, text=True).strip()


def main():
    g = json.loads((BASE / 'gate_result.json').read_text())
    r = json.loads((BASE / 'result.json').read_text())
    v = json.loads((BASE / 'verification.json').read_text())
    def timing(name):
        log = (BASE / name).read_text()
        return float(re.search(r'([0-9.]+) real', log)[1]), int(re.search(r'(\d+)  maximum resident set size', log)[1])
    sample_seconds, sample_rss = timing('sample.log')
    read_seconds, read_rss = timing('read.log')
    tables_seconds, tables_rss = timing('tables.log')
    assert g['state'] == v['state'] == 'passed' and r['state'] == 'complete'
    assert git(rec.ROOT / 'source', 'rev-parse', 'HEAD') == '7f48b75badd3854616449d9ab6464ccbb5f7b011'
    assert git(rec.ROOT / 'source', 'status', '--porcelain') == ''
    assert not PATH.exists(), '既存の同名報告を上書きしない'
    DEST.mkdir(exist_ok=True)
    for p in (BASE / 'tables').iterdir():
        if p.is_file():
            shutil.copy2(p, DEST / p.name)
    for name in ('scope.json', 'gate_result.json', 'result.json', 'verification.json', 'read_records.py',
                 'tabulate.py', 'verify.py', 'write_report.py', 'publish.py', 'sample.log', 'read.log', 'tables.log', 'verify.log'):
        shutil.copy2(BASE / name, DEST / name)
    with (DEST / 'input_manifest.csv').open('a', newline='') as f:
        w = csv.DictWriter(f, ['path', 'bytes', 'sha256'])
        w.writerow(rec.fingerprint(rec.ROOT / 'h_formula_2026-10-05/input_manifest.csv'))
    commands = {'working_directory_relative_to_workspace': 'codex_verb_2026-10-04', 'commands': [
        'python3 ~/jobs/jobs.py run --wait --owner Codex-verb-selection-diagnostic --mem 0.4 --disk-path selection_diagnostic_2026-10-06 -- /usr/bin/time -l /opt/homebrew/opt/python@3.12/bin/python3.12 -u selection_diagnostic_2026-10-06/read_records.py --sample',
        'python3 ~/jobs/jobs.py run --wait --owner Codex-verb-selection-diagnostic --mem 0.4 --disk-path selection_diagnostic_2026-10-06 -- /usr/bin/time -l /opt/homebrew/opt/python@3.12/bin/python3.12 -u selection_diagnostic_2026-10-06/read_records.py',
        'python3 ~/jobs/jobs.py run --wait --owner Codex-verb-selection-tables --mem 0.1 --disk-path selection_diagnostic_2026-10-06/tables -- /usr/bin/time -l /opt/homebrew/opt/python@3.12/bin/python3.12 -u selection_diagnostic_2026-10-06/tabulate.py',
        'python3 ~/jobs/jobs.py run --wait --owner Codex-verb-selection-verify --mem 0.1 --disk-path selection_diagnostic_2026-10-06 -- /usr/bin/time -l /opt/homebrew/opt/python@3.12/bin/python3.12 -u selection_diagnostic_2026-10-06/verify.py',
        'python3 selection_diagnostic_2026-10-06/write_report.py',
        'python3 ~/jobs/jobs.py run --wait --owner Codex-verb-selection-publish --mem 0.2 --disk-path report-results/control/2026-10-06_動詞の世界_選び間違いの診断_Codex -- python3 selection_diagnostic_2026-10-06/publish.py'],
        'stdout_stderr_logs': ['sample.log', 'read.log', 'tables.log', 'verify.log'],
        'model_run_commit': '9e4bdea37573f2772ee1dcbb1c9d6babbff1787e',
        'work_branch': 'codex/verb-world-2026-10-04', 'work_commit': '7f48b75badd3854616449d9ab6464ccbb5f7b011',
        'report_branch': 'results-2026-09-27', 'report_before_commit': git(REPORT, 'rev-parse', 'HEAD')}
    rec.dump(DEST / 'commands.json', commands)
    primary = list(csv.DictReader((BASE / 'tables/primary_candidates.csv').open()))
    count_names = Counter((x['world'], x['classification'], x['side'], x['name_class']) for x in primary)
    text = [f'# 動詞の世界：選び間違いの診断（Codex、{datetime.now().astimezone().isoformat(timespec="seconds")}）', '',
        'この会話とoriginの報告枝に同じ診断の既存報告は見当たらなかったため、依頼に従って実施した。段1は通過し、段2を既存記録だけで完了した。模型の再走行は0本。模型・照合・既存の分類コードは変更していない。結果の良し悪しは記述しない。', '',
        '動詞は既定40動詞、A/C/D（Dのτ=0.4）×U global/abstain×種1〜5、N3、λ=0.01873710622997919、5,000試行の既存30本から、学習中の不規則過去形へのREG回答1,490件を対象とした。試験の回答は含めない。お店は指定された公開済み136件を対象とし、その抽出元の種1〜20の既存記録で席の総数を補った。種21〜40は読んでいない。', '',
        '記録の模型コミットは`9e4bdea37573f2772ee1dcbb1c9d6babbff1787e`。作業枝は`codex/verb-world-2026-10-04`、確認したHEADは`7f48b75badd3854616449d9ab6464ccbb5f7b011`のまま。新しい読み取り・集計台本は、この報告と同じフォルダに収録する。', '',
        '## 数え方と段1の関門', '',
        '- 予測前の記憶は、台帳の直前行の更新後スナップショット（full/delta）の`definitions`と`slot_history`から展開した。予測・照合・学習・分類の関数は呼んでいない。Fはaliveの行、Hはaliveでなく履歴欄がある行、Uは残り。空の履歴欄もHとする。',
        '- 席の総数は`constituents`の行数（F＋H＋U）。`n_FH`はF＋Hの行数。同じslot_indexの行をまとめない。各候補のF/H/Uの件数をCSVに残した。',
        '- 正しい候補は、保存された候補記録で`correct=true`かつ`gate=true`のもの。比較の代表は、保存されたN3の順位でそのうち最上位の候補。正しい候補が複数ある場合も全候補の行を別表に保存した。語の名前が一致することを候補の条件には追加していない。',
        '- 動詞の定義の誕生試行、材料に使った過去の場面の試行`base_written_at`、その場面と現在の場面の動詞名を、台帳とsideのbirth記録から結びつけた。誕生時の構成素の名前も残した。',
        '- 既存の`classification.csv`の腕・U別の件数、および1,490件すべての分類を一致で再現した。選び間違い397件、区別の喪失1,093件。不一致0件、必要欄の欠落0件。',
        '- 選択候補と門を通る正答候補の2,497行で、予測前のF/H/U、n_FH、誕生試行、名前の席の状態・名前・履歴、保存された支持数とN3を照合した。不一致0件。お店のシールの記録も元の予測前の記憶と一致した。',
        '- 別の検算で元のcasesと出力CSVを全1,490件、お店の元CSVと全136件照合した。入力164ファイルの現在のsha256が読み取り時と一致し、そのうち90ファイルは前のH式監査のsha256とも一致した。', '',
        '四分位は、並べた値の位置`(N−1)×p`を線形補間する方式（p=0.25,0.5,0.75）。各統計は事例ごとに重み1で数え、同じ定義が再び選ばれた場合も別の事例とする。', '',
        '## 大きさとN3', '',
        '| 世界・既存分類 | 候補 | 件数 | 席の総数 中央値［Q1, Q3］ | n_FH 中央値［Q1, Q3］ | N3平均 |',
        '|---|---|---:|---:|---:|---:|']
    labels = {'selection_error': '選び間違い', 'distinction_loss': '区別の喪失'}
    for s in r['pooled_sizes']:
        world = '動詞' if s['world'] == 'verb' else 'お店'
        side = '選ばれた定義' if s['side'] == 'selected' else '代表の正答候補'
        text.append(f'| {world}・{labels[s["classification"]]} | {side} | {s["cases"]} | {s["total_seats_median"]:g}［{s["total_seats_q1"]:g}, {s["total_seats_q3"]:g}］ | {s["n_FH_median"]:g}［{s["n_FH_q1"]:g}, {s["n_FH_q3"]:g}］ | {s["N3_mean"]:.6f} |')
    text += ['', '| 世界 | 席の総数：選択候補＞正答候補 | n_FH：選択候補＞正答候補 | N3：選択候補＞正答候補 | N3同点 |',
             '|---|---:|---:|---:|---:|']
    for s in r['pooled_pair_signs']:
        world = '動詞' if s['world'] == 'verb' else 'お店'
        values = [f'{s[m + "_selected_larger"]}/{s["cases"]}（{100*s[m + "_selected_larger_fraction"]:.2f}%）' for m in ('total_seats', 'n_FH', 'N3')]
        text.append(f'| {world} | ' + ' | '.join(values) + f' | {s["N3_equal"]} |')
    text += ['', '差の正・零・負の全件数と割合をCSVに保存した。腕・U・種・語（V33〜V40）の個別組と、腕×U、腕×U×種、腕×U×語の集約表も同じCSVに含めた。', '',
        '## 名前の席の四分類', '',
        '(a)は名前の席の行自体が無い、(b)はF/Hの名前の席があるが問われた名前を含まない、(c)はU、(d)は問われた名前を含むF/H。Fは固定述語、Hは正の回数を持つ履歴名で判定した。ゼロ回のキーを含む元の履歴もCSVに保存した。今回の対象候補には名前の席が複数ある定義は0行で、四分類の重なりは無い。お店では問われた名前をsig_eとして同じ分類をした。', '',
        '| 世界・既存分類 | 候補 | (a) 席無し | (b) 別の名前 | (c) U | (d) 問われた名前を含む |',
        '|---|---|---:|---:|---:|---:|']
    for world, cls, side in [('verb', 'selection_error', 'selected'), ('verb', 'selection_error', 'correct'),
                              ('verb', 'distinction_loss', 'selected'), ('shop', 'selection_error', 'selected'), ('shop', 'selection_error', 'correct')]:
        text.append(f'| {"動詞" if world == "verb" else "お店"}・{labels[cls]} | {"選ばれた定義" if side == "selected" else "代表の正答候補"} | ' +
                    ' | '.join(str(count_names[(world, cls, side, x)]) for x in ('a_no_name_seat', 'b_other_name', 'c_U', 'd_contains_query')) + ' |')
    text += ['', '**従来のno_definition 1,489件の内訳**：名前の席そのものが無い1,401件、別の動詞名のHの席がある47件、Uの席がある41件。残る1件はV35を含むHの席がある区別の喪失。', '',
        '(b)の選択定義47件はすべてHで、履歴は規則動詞だけ。V01が27件、V02が10件、V03が3件、V04が5件、V09が2件。Fの別名0件、不規則動詞を含むH0件。選び間違いの24件はV01=17・V02=5・V03=2、区別の喪失の23件はV01=10・V02=5・V03=1・V04=5・V09=2。', '',
        'この47件の`maps_to_this_verb`はすべてfalse。これは問われた動詞の名前の関係に対応づいた名前の席が無いことを表す。親attachの個別の写像はこの候補記録には無いため、親linkごとの脱落まではこの表から判定しない。', '',
        '代表の正答候補397件では、問われた動詞の名前を含むF/Hが364件、別の名前が22件、Uが9件、名前の席が無いものが2件。保存された正答・門通過の条件をそのまま使っており、当該語の名前の一致を追加していない。', '',
        'お店の選択定義はH[sig_n] 68件＝(b)、U 52件＝(c)、H[sig_e] 16件＝(d)。代表の正答候補はF[sig_e] 102件・H[sig_e] 34件で、全136件が(d)。名前の席の無い選択定義は、動詞の選び間違い368件、お店0件。', '',
        '## 名前の席が無い定義の誕生記録', '',
        '動詞の(a)に入る選択定義1,401事例は、重複を除くと180定義（run・定義名・誕生試行の組）。全事例で、誕生の二つの材料の動詞名が異なり、誕生時の構成素にも動詞の名前の関係が無い。誕生時には名前の席があり後から行を失った事例0件、誕生の材料を分けられない事例0件。同じ語どうしの誕生で名前の席が無かった事例も0件。', '',
        '| 既存分類・側 | 異なる動詞の材料で誕生、名前の席無し：事例 | 定義数 | 後で名前の行を失った事例 | 未特定の事例 |',
        '|---|---:|---:|---:|---:|',
        '| 選び間違い・選択定義 | 368 | 133 | 0 | 0 |',
        '| 区別の喪失・選択定義 | 1,033 | 130 | 0 | 0 |',
        '| 選び間違い・代表の正答候補 | 2 | 1 | 0 | 0 |', '',
        '選択定義の133と130には両分類で使われた同じ定義が重なるため、合計は180定義。CSVでは事例数と定義数を分け、各定義の出生試行・材料の試行・二つの動詞名も保存した。', '',
        '## 入力・台本・時間', '',
        f'入力のパスはワークスペースを基準にした相対パスで、[{NAME}/input_manifest.csv]({NAME}/input_manifest.csv)にbytesとsha256を保存した。主な動詞の入力は`codex_verb_2026-10-04/stage3_night/<A/C/D>_<global/abstain>_s01〜s05/analysis/cases.jsonl.gz`、同runの`ledgers/cells/*/seed001〜005.jsonl.gz`、`side/*/seed001〜005.select.jsonl.gz`とbirthの`seed001〜005.jsonl`。', '',
        'お店は`codex_verb_2026-10-04/report-results/control/attn_seal_diagnostic_2026-10-05/extracted_cases.jsonl.gz`と`exception_selection_errors_136.csv`、その抽出元の`codex_attn_2026-10-03/material_rebuild_2026-10-04/n3_w2_A_L50/ledgers/cells/f0.5000_th2.1000_vt0.3842_first_order/seed001〜020.jsonl.gz`、同セルの`*.shop.jsonl`。模型は走らせていない。', '',
        f'読み取り・集計・検算はすべて`~/jobs/jobs.py run --wait --mem ... --disk-path ...`で受付に登録した。一本の小読取は{sample_seconds:.2f}秒・最大常駐{sample_rss:,} bytes（{sample_rss/1024**2:.2f} MiB）。残りとお店を含む読取は{read_seconds:.2f}秒・最大常駐{read_rss:,} bytes（{read_rss/1024**2:.2f} MiB）。予約0.4GBは前の同じ台帳の読取の最大約241MB×1.2を上限の目安にした。集計と検算は予約0.1GB。集計{tables_seconds:.2f}秒・最大{tables_rss:,} bytes、検算は`verification.json`に実測を保存した。', '',
        f'実行コマンドとコミットは[commands.json]({NAME}/commands.json)。実行時の台本は`codex_verb_2026-10-04/selection_diagnostic_2026-10-06/`にあり、その写しをこの報告フォルダにも保存した。最初の小読取で完了した一本の結果を、残りの読み取りで再利用した。', '',
        '## CSV', '',
        f'- [全対象候補]({NAME}/all_candidates.csv)・[代表候補]({NAME}/primary_candidates.csv)：席数、F/H/U、N3、全ての名前の席・履歴・対応の真偽、誕生試行と材料の動詞。',
        f'- [大小の組]({NAME}/size_pairs.csv)・[中央値と四分位]({NAME}/size_summary.csv)・[大きさの差の符号]({NAME}/size_pair_summary.csv)。',
        f'- [名前の四分類]({NAME}/name_class_counts.csv)・[別名の中身]({NAME}/other_name_details.csv)。',
        f'- [席が無い定義の誕生区分]({NAME}/absent_name_origins.csv)・[定義ごとの材料]({NAME}/absent_name_definition_details.csv)。',
        f'- [関門]({NAME}/gate_result.json)・[別の検算]({NAME}/verification.json)・[実測]({NAME}/resources.csv)・[圧縮した候補行]({NAME}/candidate_records.jsonl.gz)。', '']
    PATH.write_text('\n'.join(text))
    artifacts = []
    for p in sorted(DEST.iterdir()):
        if p.is_file():
            artifacts.append({'file': p.name, 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    rec.dump(DEST / 'artifact_manifest.json', artifacts)
    print(str(PATH.relative_to(rec.WORKSPACE)))


if __name__ == '__main__':
    main()
