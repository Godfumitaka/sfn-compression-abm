"""小さい証拠だけを報告へ写す。原本の出力は動かさず、個人の絶対パスを送らない。"""
from pathlib import Path
import hashlib
import json
import shutil

root=Path(__file__).resolve().parent
ws=root.parents[1]
report_repo=root.parent/'report-results'
name='2026-10-06_動詞の世界_SME版_Codex'
dest=report_repo/'control'/name
dest.mkdir(exist_ok=True)

def public(data):
    return data.replace(str(ws),'$WORKSPACE').replace(str(Path.home()),'$USER_HOME')

for filename in ('metadata.json','port.patch','gate_driver.py','world_sequence.py','run_case.py','compare_gates.py','stage_runner.py','attach_cpu_guardian.py','complete_guardian_records.py','finish_report.py','append_analysis.py','analyze_after_pilot.py','hash_after_pilot.py','publish_report.py','report_snapshot.py'):
    (dest/filename).write_text(public((root/filename).read_text()))
for kind in ('shop','verb'):
    shutil.copy2(root/'gates'/f'{kind}_comparison.json',dest/f'{kind}_comparison.json')
commands={}
for label in ('gates/shop_base','gates/shop_port','gates/verb_old','gates/verb_port','pilot_A_global_s01'):
    folder=root/label
    spec=json.loads(public((folder/'spec.json').read_text()))
    commands[label]=spec
    for filename in ('result.json','resources.jsonl','resources_guardian.jsonl','resources_original_supervisor.jsonl','guardian_attachment.json','guardian_complete.json'):
        if (folder/filename).exists():
            (dest/(label.replace('/','_')+'_'+filename)).write_text(public((folder/filename).read_text()))
(dest/'commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n')
analysis=root/'pilot_analysis'
for filename in ('spec.json','result.json','reader_status.json','resources.jsonl'):
    if (analysis/filename).exists():
        (dest/('analysis_'+filename)).write_text(public((analysis/filename).read_text()))
measurement=root/'final_measurement'
for filename in ('spec.json','result.json','reader_status.json','resources.jsonl'):
    if (measurement/filename).exists():
        (dest/('measurement_'+filename)).write_text(public((measurement/filename).read_text()))
metadata=json.loads((root/'metadata.json').read_text())
shop=json.loads((root/'gates/shop_comparison.json').read_text())
verb=json.loads((root/'gates/verb_comparison.json').read_text())
report=report_repo/'control'/f'{name}.md'
if not report.exists():
    report.write_text(f'''# 動詞の世界のSME版

種1の二つの移植関門は通過。保持A・U global・λ={metadata['pilot']['lambda']}の5,000試行を、2026-10-06 12:49 JSTに開始した。1,000試行ごとの時間・最大常駐、総時間・出力容量、120本の見込みは完走後に追記する。

土台は`codex/sme-evict-a-2026-10-06`の`{metadata['base_commit']}`。動詞の世界・課題・研究者側の分類道具を、`codex/verb-world-2026-10-04`の`{metadata['old_commit']}`から移した。作業枝はローカルの`{metadata['ported_branch']}`、コミット`{metadata['ported_commit']}`。abm/とSME照合・模型の式は変更していない。世界の旗を切ったとき、新しい動詞・時間観察のモジュールを読み込まない。分類道具はSMEのSES・自己照合からN3を再計算し、再現したR_usedがN3・席数・登録時点の最大集合に入ることを検査する。旧い照合のN3をSMEへ流用しない。

構造のpytestは20件通過（0.30秒、Python3.14/pytest9.1.1）。模型の実行はPython3.12.13。Schulerは走らせていない。過去形を問う割合の旧版の軸は30本すべて完了済みで、今回停止・再走行していない。今回の種は1のみ。種21〜40は読まず、走らせず、120本の走行も始めていない。

|関門|対象|照合した記録のバイト数|不一致ファイル数|
|---|---|---:|---:|
|旗なしのお店|種1・200試行、台帳・全side・保存状態・SME照合・控え削除の記録・旗の10ファイル|{shop['compared_content_bytes']}|{shop['mismatching_files']}|
|動詞の場面・問い|種1・全5,000場面＋固定試験48問。全場面、提示、伏せ辺、動詞、正解、開示用の乱数|{verb['compared_content_bytes']}|{verb['mismatching_files']}|

gzipは展開した記録の全バイトを比較し、JSONの並べ替え、欄の除外、数値の丸めをしなかった。お店の関門に限り、ヘッダの出所タグcode_commitを実行入口で共通の10cd8bdに固定した。実際のコードのコミットは[commands.json]({name}/commands.json)のsourcesに別記した。台帳のヘッダを含む全内容は一致。manifest/.doneの終了時刻や計測値、gzip容器の作成時刻は模型の記録のこの一致関門の対象外である。[お店の全ファイルのsha256]({name}/shop_comparison.json)、[動詞の全記録のsha256]({name}/verb_comparison.json)。

測定は`--sme2017 --sme-call-seed --sme-tie-uniform --score-arg-order --sme-intern-cache --sme-evict-trial-cache`。墓石検査は付けない。旧版の`--select-n3`と`--select-log`はSMEでは使わず、共通窓口のN3とSMEの候補記録を使う。U globalの候補を過去形に絞る変更はない。旧版と同じ40動詞・既定の過去形の問い割合・λ・5,000試行/horizon。学習しない試験は100試行ごとに48問（学習語40、新語8）。保持Aの旗は土台のSMEのお店のnative命令を使い、お店の生成とscatterの旗を動詞の生成へ替えた。今回の測定はcf-valueの追加診断を付けず、SME土台と同じ台帳・保存状態・回答・届け先の記録を含む。

時間は1,000試行の台帳追記後に別記録へ出す。各区間には、その時点までに完了した学習しない試験も含む。最大常駐は個体workerの、その時点までの累積最大値。世界の初期生成も最初の区間へ含む。模型の状態、乱数、台帳の内容を時間観察から変更しない。

重い処理はすべてjobs.py run --wait、--mem、実出力先の--disk-pathで受付に通した。200試行と場面の関門は0.6GB、比較は0.2GB、5,000試行は1.3GBの事前予約。後者は既存のお店A・1,740試行の最大350.9MB×(5000/1740)×1.2=1.210GBを上へ丸めた見込みであり、今回の実測値ではない。

[共通のCPU前置き](2026-10-06_渡す委任書_Claude.md#共通の前置き32〜37-番)に従い、物理CPU10−2=8を共有機械の上限にした。自分は直列で、ほかの係の重いPythonもpsで数え、枠が足りない間は待つ。稼働中に上限や熱・容量の条件を外れたときは自分のプロセス群だけを待機させる。お店の元の関門の監視ではpsの短いcomm列がPythonを省略したため本数欄を採用しない。移植版からは実行コマンドの先頭の実行ファイル名で数えるよう、模型の外の監督だけを修正した。独立したpsの確認では元の関門の全体は8本以内だった。元と移植版の関門の模型の記録は全件一致している。

原本はワークスペース内の`codex_verb_2026-10-04/sme_2026-10-06/`。大きい台帳・保存状態は原本の出力先に残し、報告には小さい証拠だけを置く。`$WORKSPACE`はそのワークスペースの根、`$USER_HOME`はユーザーのホームを表す。実際の呼び出しの配列を、この二つのパス接頭辞だけ置き換えて[commands.json]({name}/commands.json)へ保存。[移植の差分]({name}/port.patch)は10cd8bdへ適用できる。送信の明示承認は旧作業枝とresults枝の二つだけなので、今回の新しいSME作業枝はローカルに保存し、差分を報告枝へ同梱する。
''')
manifest=[]
for p in sorted(dest.rglob('*')):
    if p.is_file() and p.name!='evidence_sha256.json':
        manifest.append({'path':str(p.relative_to(dest)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(dest/'evidence_sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(report)
