"""段1で止まったH式の検証を、指定の報告と証跡にまとめる。"""
from __future__ import annotations
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import shutil
import subprocess

BASE=Path(__file__).resolve().parent
ROOT=BASE.parent
SOURCE=ROOT/'source'
REPO=ROOT/'report-results'
NAME='2026-10-05_動詞の世界_Hの式の引っ張り_Codex'
EVIDENCE=REPO/'control'/NAME
REPORT=REPO/'control'/(NAME+'.md')


def csv_rows(p):
    return list(csv.DictReader(p.open())) if p.stat().st_size else []


def dump(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    result=json.loads((BASE/'gate_result.json').read_text())
    refined=json.loads((BASE/'gate_result_refined.json').read_text())
    assert result['runs']==30 and result['stop_at_stage1'] and not result['stage2_executed']
    assert refined['runs']==30 and refined['stop_at_stage1'] and not refined['stage2_executed']
    assert json.loads((BASE/'status.json').read_text())['state']=='stopped_at_stage1'
    coverage=csv_rows(BASE/'record_coverage.csv')
    missing=csv_rows(BASE/'missing_fields_refined.csv')
    assert len(coverage)==30
    totals=defaultdict(Counter)
    for row in coverage:
        totals[(row['arm'],row['U'])].update({k:int(v) for k,v in row.items() if k not in ('run','arm','U','seed') and v})
    for row in csv_rows(BASE/'probe_independent_checks.csv'):
        totals[(row['arm'],row['U'])]['probe_known_no_answer_seat']+=int(row.get('probe_known_no_answer_seat') or 0)
    gaps=defaultdict(Counter)
    for row in missing:
        gaps[(row['arm'],row['U'])][row['phase']]+=int(row['count'])
    examples=json.loads((BASE/'missing_examples.json').read_text())
    originals=json.loads((ROOT/'stage3_night/plan.json').read_text())
    runs={r['label']:r for r in originals['runs']}
    detailed=json.loads((BASE/'missing_examples_refined.json').read_text())
    for label in sorted({e['run'] for e in examples}):
        run=runs[label]
        folder=ROOT/'stage3_night'/label/'run'
        p=next((folder/'side').glob(f'*/seed{run["seed"]:03d}.probe.jsonl'))
        records={(r['t'],r['verb_name']):r for r in map(json.loads,p.open())}
        for e in [e for e in examples if e['run']==label and e['phase']=='training']:
            rec=records.get((e['t'],e['verb'])) if e['phase']=='probe' else None
            detailed.append({**e,'record':rec,'record_path':str(p.relative_to(ROOT)) if rec else None})
    dump(BASE/'missing_examples_with_records.json',detailed)
    times=[]
    for r in originals['runs']:
        res=json.loads((ROOT/'stage3_night'/r['label']/'resources.json').read_text())
        times.append({'arm':r['arm'],'U':r['U'],'seed':r['seed'],'model_seconds':res['model_seconds'],
                      'peak_rss_bytes':res['process_peak_rss_bytes_time']})
    timing=defaultdict(list)
    for r in times:
        timing[r['arm']].append(r['model_seconds'])
    serial=sum(r['model_seconds'] for r in times)
    work_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip()
    formula_files=['abm/filling.py','abm/definition.py','tools/v39.py','tools/probeworld.py','tools/answerlog.py','tools/verb/analyze.py','tools/selectn3.py']
    unchanged=subprocess.run(['git','diff','--quiet',originals['commit'],work_commit,'--',*formula_files],cwd=SOURCE).returncode==0
    assert unchanged
    commands={'model_reruns_for_this_request':0,'original_model_commit':originals['commit'],
              'read_environment_work_commit':work_commit,
              'audit_command':'python3.12 ~/jobs/jobs.py run --wait --owner Codex-動詞H式停止報告確認 --mem 0.4 --disk-path ./h_formula_2026-10-05 -- /usr/bin/time -l python3.12 ./h_formula_2026-10-05/audit.py',
              'first_audit_command':'python3.12 ~/jobs/jobs.py run --wait --owner Codex-動詞H式記録検証 --mem 0.4 --disk-path ./h_formula_2026-10-05 -- /usr/bin/time -l python3.12 ./h_formula_2026-10-05/first_gate_partial/audit.py',
              'first_audit_stop':'1本目の試験の黙り483件に席の記録が無いことを確認して、自分の読取専用処理を停止。後続の数えは行わず、全30本の段1の件数を確認する処理だけに切り替えた。',
              'independent_probe_check_command':'python3.12 ~/jobs/jobs.py run --wait --owner Codex-動詞H式独立確認 --mem 0.4 --disk-path ./h_formula_2026-10-05 -- /usr/bin/time -l python3.12 ./h_formula_2026-10-05/refine.py',
              'report_command':'python3.12 ~/jobs/jobs.py run --wait --owner Codex-動詞H式停止報告作成 --mem 0.4 --disk-path ./h_formula_2026-10-05 -- python3.12 ./h_formula_2026-10-05/report.py',
              'working_directory':'codex_verb_2026-10-04（各パスはこのフォルダからの相対パス）',
              'formula_and_existing_classification_files_unchanged':formula_files,
              'rerun_model_serial_seconds_estimate':serial,'rerun_extra_recording_overhead':'未実測、待ち時間と全バイト照合の時間を別に加える',
              'report_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    dump(BASE/'commands_and_commits.json',commands)
    dump(BASE/'rerun_time_estimate.json',{'serial_model_seconds':serial,'runs':times,
            'additional_recording_and_byte_gate_seconds':None,'queue_wait_seconds':None,'rerun_executed':False})
    EVIDENCE.mkdir(exist_ok=True)
    manifests=csv_rows(BASE/'input_manifest.csv')
    for p in (BASE/'refine.py',BASE/'report.py'):
        manifests.append({'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
    for run in originals['runs']:
        for p in (ROOT/'stage3_night'/run['label']/'resources.json',ROOT/'stage3_night'/run['label']/'run/flag.json'):
            manifests.append({'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
    manifests=list({r['path']:r for r in manifests}.values())
    with (BASE/'input_manifest.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,['run','path','sha256','bytes']);w.writeheader();w.writerows(manifests)
    for name in ('audit.py','refine.py','report.py','gate_result.json','gate_result_refined.json','record_coverage.csv',
                 'missing_fields.csv','missing_fields_refined.csv','missing_examples_with_records.json','probe_independent_checks.csv',
                 'gate1_counts.csv','gate2_mismatches.csv','independent_H_probe_mismatches.json',
                 'input_manifest.csv','commands_and_commits.json','rerun_time_estimate.json'):
        shutil.copy2(BASE/name,EVIDENCE/name)
    md=[f'# Hの式の引っ張り：段1の記録確認で停止（2026-10-05、Codex）','',
        '**段1で停止。段2の区分別の数え・反実仮想・混合履歴の定義数・率は実施していない。** 既存30本（A/C/D×global/abstain×種1〜5）を読み、新たな模型走行は0本。模型・照合・既存の選び間違い／区別の喪失の分類コードは変更していない。種21〜40は読まず、走らせていない。別に承認された二軸の走行はこの停止の対象外。結果の良し悪しの判断はしない。','',
        '## 四つの記録','',
        '|項目|学習中|学習しない試験|','|---|---|---|',
        '|選択の定義|台帳R_used、answersのR/R_born、sideと照合|probeのR（名前@誕生試行）とR_used|',
        '|答えた席とF/H/U|回答時はpredicted_edgeの関係IDとanswersのslot/seat_stateを相互照合。黙りはambigのheld_slotがある件のみ直接決まる|有回答のFは固定名と引数の数、Hはsourceと履歴にある名前・階・引数の数で一意に同定する（重みは使わない）。Uの有回答は0件。黙りは対象席・写像・分布が無い件が残る|',
        '|直前の履歴（名前と回数）|直前の台帳状態のslot_history。今回の質問前状態を前行の状態指紋と照合|t試行後の台帳状態に履歴がある。席を一意に同定したH回答で利用できた|',
        '|直前のp̂|前行のp_hat counts/total/lambda_mix/alive_vocab|t試行後の同じ表。試験時点の状態指紋を照合|','',
        f"p̂は既存の状態に残っているため、設計確率や経験数による近似は使っていない。初回に定義が無い場合は答えた席も無い。学習中は当該試行の観察・開示を足す前の状態、試験はt試行を終えた状態を読む。局所履歴の指数はconfig/headerの **1.0**。MDLのλ=0.01873710622997919とは別。状態指紋の確認は{result['state_hashes']:,}箇所（質問直前・試験時点）。",'',
        '## 関門1：既存の過剰な規則化の件数','',
        f"`overregularization_per_verb.csv`の腕×U×500試行区間×V33〜V40の{result['gate1_rows']}行を、台帳のheld_out_is_pastとpredicted_edgeから再集計した。問うた数とREG件数の不一致は **{result['gate1_mismatch_rows']}行**。この既存CSVは学習中の集計である。試験は別のprobe記録として72,000問を確認した。",'',
        f"[全行の比較]({NAME}/gate1_counts.csv)。分母・REG件数の再現だけで、Hの引っ張りの指標は計算していない。",'',
        '## 関門2：Hの式の再現','',
        '|確認対象|確認件数|答えの不一致|独立に席を同定できたか|','|---|---:|---:|---|',
        f"|学習中の実際のH回答（answersの席番号と予測辺ID）|{result['gate2_counts'].get('training_answer:checked',0)}|{result['gate2_counts'].get('training_answer:mismatch',0)}|できた|",
        f"|学習中の当該H席のside.answers（上の回答と重複する補助記録）|{result['gate2_counts'].get('training_side:checked',0)}|{result['gate2_counts'].get('training_side:mismatch',0)}|できた|",
        f"|試験のH回答、履歴の名前・階・引数の数で同定した1席|{refined['counts'].get('independent_H_checked',0)}|{refined['counts'].get('independent_H_mismatches',0)}|式の重みを使わず同定してから、式を再計算した|",'',
        f"試験でHと記録された有回答は{refined['counts'].get('probe_answer_source_H',0)}件。このうち上表の件数を独立に再現した。席の同定では、履歴に答えた名があること・同じ階・同じ引数の数であることだけを使い、回数の大小・p̂・式の最大値は使っていない。初回の式から逆算した補助一致はゲートに数えず、別の独立確認に置き換えた。",'',
        '**四項目の全件確認は未完了のため、段1で停止。** 黙ったときの、当該過去形の席とその対応先・候補分布が記録に無い件が残る。Hの同点で黙ったのか、対象の候補が出なかったのか、他の席の同点等で答え全体が止まったのかを、当該の過去形の席について全件確定できない。この未確認を不一致0件として扱わない。', '',
        f"[学習中の確認対象の不一致例]({NAME}/gate2_mismatches.csv)（0件なら空）、[試験の独立確認の不一致例]({NAME}/independent_H_probe_mismatches.json)。H-一致／H-引っ張りの振り分けと、履歴最多の反実仮想は実施していない。",'',
        '## 記録不足の件数と例','',
        '|保持|U|学習中の過去形質問|学習中で対象席が未特定|試験の過去形質問|試験で対象席が未特定|答える席なし・学習中|答える席なし・試験|','|---|---|---:|---:|---:|---:|---:|---:|']
    for (a,u),c in sorted(totals.items()):
        md.append(f"|{a}|{u}|{c['training_past']}|{gaps[(a,u)]['training']}|{c['probe_past']}|{gaps[(a,u)]['probe']}|{c['training_known_no_answer_seat']}|{c['probe_known_no_answer_seat']}|")
    md += ['', '学習中の未特定には、ambigにheld_slotが無い等を含む。no_projectable_relationで候補分布も空の件は「答える席なし」として別欄にした。門の下や定義無しで使った定義が無い件も、記録不足とは数えない。', '',
           f"[腕・U・種・理由別の不足件数]({NAME}/missing_fields_refined.csv)、[元の試験行を添えた例]({NAME}/missing_examples_with_records.json)。初回の未割当一覧missing_fields.csvには、試験の投影無しも含む。独立確認で答える席なしを分けたrefined表を、この報告の不足件数に使った。",'',
           '例（元の試験行のRと棄権理由はJSONにもそのまま保存）：','']
    shown=0
    shown_conditions=set()
    for e in detailed:
        condition=e['run'].rsplit('_s',1)[0]
        if e.get('record') and shown<3 and condition not in shown_conditions:
            rec=e['record']
            md.append(f"- {e['run']}、t={e['t']}、{e['verb']}：R={rec.get('R')}、R_used={rec.get('R_used')}、answer={rec.get('answer')}、abstain={rec.get('abstain')}。席番号・予測辺ID・写像・穴埋め分布が無い。")
            shown+=1
            shown_conditions.add(condition)
    md += ['', '## 記録だけを追加する再走行の見込み（今回は走らせない）','',
           f"既存30本の模型部分の実測合計は **{serial:,.3f}秒（約{serial/3600:.2f}時間、一本ずつ直列の場合）**。受付の待ち時間、追加記録の負荷、台帳本体と既存sideの全バイト比較の時間は別に加える。並列時の所要時間は共有機械の空き次第なので、この合計をそのまま並列本数で割った時間を保証しない。",'',
           '|保持|既存の本数|模型部分の平均秒／本|模型部分の合計秒|','|---|---:|---:|---:|']
    for a,ts in sorted(timing.items()):
        md.append(f'|{a}|{len(ts)}|{sum(ts)/len(ts):.3f}|{sum(ts):.3f}|')
    md += ['', '追加するなら、予測直前の選択定義と誕生時点、実際の予測辺IDと席番号、席の状態・履歴の全回数、p_hatの全回数・総数・語彙・lambda_mix、黙り時の写像と穴埋め分布を、既存の台帳・sideとは別の補助出力に保存する。式・選択・照合・分類・乱数は変更しない。台帳本体と既存sideの各ファイルを全バイトで比較し、1バイトでも違えば止める。この一致を今回は確認したとすることはない。', '',
           '既存のsideにはselect.jsonl.gzもある。現在のgzip.openは現在時刻をヘッダへ書くので、解凍内容が同じでも生の全バイトが同じとは限らない。この差も指定どおり不一致として扱う必要があり、全バイト関門の合格をまだ見込んでいない。', '',
           '## 記録・実行の証跡','',
           f"原走行のコミット `{originals['commit']}`、読取時の作業枝コミット `{work_commit}`。Hの式・既存分類に使う対象ファイルは両コミットで一致し、今回の依頼でも変更0。解析台本はこの報告のコミットに保存。",'',
           f"[入力記録の相対パス・sha256・サイズ]({NAME}/input_manifest.csv)、[コマンドとコミット]({NAME}/commands_and_commits.json)、[実測からの再走行時間の見込み]({NAME}/rerun_time_estimate.json)、[最終の関門確認]({NAME}/gate_result_refined.json)、[検証台本]({NAME}/audit.py)・[独立確認]({NAME}/refine.py)。台本はローカルのcodex_verb_2026-10-04/h_formula_2026-10-05に置いて実行した。公開コピーは証跡であり、パスをその配置に戻せば同じ記録を読む。",'',
           f"両確認処理はjobs.py run --wait、mem=0.4、実出力先のdisk-pathつき。全30本の段1確認は{result['elapsed_seconds']:.3f}秒、最大常駐{result['peak_rss_bytes']:,} bytes。試験の独立確認は{refined['elapsed_seconds']:.3f}秒、最大常駐{refined['peak_rss_bytes']:,} bytes。予測・照合・学習の呼出しは0。",'']
    REPORT.write_text('\n'.join(md))
    print(json.dumps({'report':str(REPORT.relative_to(REPO)),'evidence_files':len(list(EVIDENCE.iterdir())),
                      'gate1_mismatches':result['gate1_mismatch_rows'],'stop_at_stage1':True},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
