"""関門で停止した記録を保存する。走行も模型の変更も行わない。"""
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'outputs'
RESULTS = ROOT.parents[1] / 'codex_worldv4_2026-10-01/results'
DEST = RESULTS / 'mac/collective_strictpc_20261001/gate2'
REPORT = RESULTS / 'control/2026-10-01_穴出しと集団化_Codex.md'
MARKER = '## 段2：現行版への集団化の載せ直し・関門で停止'
assert MARKER not in REPORT.read_text()
assert not DEST.exists()
assert not (OUT / 'gate_passed.json').exists()
assert not list(OUT.glob('pilot_*'))
DEST.mkdir(parents=True)


def load(name):
    return json.loads((OUT / name).read_text())


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n')


def copy(path, relative):
    target = DEST / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    assert not target.exists(), target
    shutil.copyfile(path, target)


def zip_copy(path, relative):
    target = DEST / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    assert not target.exists(), target
    target.write_bytes(gzip.compress(path.read_bytes(), mtime=0))


small = load('small_examples.json')
hashes = load('checks_hashes.json')
observed = load('checks_counts_observed.json')
differences = json.loads(gzip.decompress((OUT/'bundle_world_mismatches.json.gz').read_bytes()))
eprice = load('eprice_receipts.json')
assert sum(x['tests'] for x in small) == 68
assert all(p['equal'] for p in hashes['body_pairs'])
assert hashes['comm_repeat_equal'] and eprice['all_receipt_prices_equal']
example = next(r['first_mismatch'] for r in differences if r['condition'] == 'q0')
assert (example['seed'], example['trial_zero_based']) == (1001, 14)
assert example['world']['predicted_edge']['predicate'] == 'stack'
assert example['bundle']['pred'][1] == 'push'
cf = next((OUT/'q0/side').glob('*/seed1001.cfvalue.jsonl'))
cf_rows = [r for line in cf.read_text().splitlines() if (r := json.loads(line)).get('trial') == 14]
assert cf_rows[-1]['answer_actual'] == 'stack' and cf_rows[-1]['answer_thinned'] == 'push'
silent_sent = next(r for p in differences if p['condition'] == 'eprice_check'
                   for r in p['mismatches'] if r['world']['coverage'] != 1 and r['bundle']['send'])
save(DEST/'minimal_examples.json', {'q0_actual_vs_diagnostic': example,
                                  'cf_diagnostic_rows': cf_rows,
                                  'sent_on_abstained_world_trial': silent_sent})
for name in ('small_examples.json', 'checks_hashes.json', 'checks_counts_observed.json',
             'bundle_world_mismatches.json.gz'):
    copy(OUT/name, name)
for path in OUT.glob('stopped_*.json'):
    copy(path, path.name)
zip_copy(OUT/'eprice_receipts.json', 'eprice_receipts.json.gz')
for path in sorted(OUT.glob('pytest_*')):
    copy(path, 'small_examples/'+path.name)
for path in sorted(OUT.glob('*.argv.json')):
    copy(path, 'commands/'+path.name)
ledger_manifest = []
for run in sorted(p for p in OUT.iterdir() if p.is_dir()):
    if (run/'flag.json').exists():
        copy(run/'flag.json', 'runs/'+run.name+'/flag.json')
    for path in sorted((run/'comm').glob('*')):
        if path.suffix == '.jsonl':
            zip_copy(path, 'runs/'+run.name+'/comm/'+path.name+'.gz')
        elif path.suffix == '.json':
            copy(path, 'runs/'+run.name+'/comm/'+path.name)
    for path in sorted((run/'ledgers/cells').glob('*/*.jsonl.gz')):
        assert int(path.name.split('.')[0][4:]) in (1, 1001)
        body = hashlib.sha256()
        rows = 0
        with gzip.open(path, 'rb') as stream:
            next(stream)
            for line in stream:
                body.update(line)
                rows += 1
        ledger_manifest.append({'condition': run.name, 'path': str(path), 'rows': rows,
                                'body_sha256': body.hexdigest(),
                                'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
assert sum(r['rows'] for r in ledger_manifest) == 8880
save(DEST/'ledger_manifest.json', ledger_manifest)
for name in ('audit_failure.py', 'port_collective.py', 'report_stopped.py'):
    copy(ROOT/name, 'scripts/'+name)
source = ROOT/'source'
base_sha = '88e0e38bbd4f8ebbdc3f087de36801ce64a673e2'
source_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
changed = subprocess.check_output(['git', 'diff', '--name-only', base_sha], cwd=source, text=True).splitlines()
assert not any(p.startswith('abm/') for p in changed)
save(DEST/'source_and_scope.json', {'base': base_sha, 'source': source_sha,
                                  'branch': 'codex-collective-strictpc', 'gate_passed': False,
                                  'pilot_runs': 0, 'python': subprocess.check_output([
                                      '/opt/homebrew/opt/python@3.12/bin/python3.12', '--version'], text=True).strip(),
                                  'changed_files': changed, 'abm_changed_files': 0,
                                  'created': datetime.now().astimezone().isoformat(timespec='seconds')})

lines = [
    '\n'+MARKER+'\n',
    f'保存時刻：{datetime.now().astimezone().isoformat(timespec="seconds")}。関門2は不通。段3は0走行。停止後の模型の修正・再走行は行っていない。',
    '',
    f'土台 strict-pc-2026-10-01 は {base_sha}。集団化 v3.11cu-main（d3970a86bb3645b766c6c32ce1e69fd2c22cc8fa）を探索枝 codex-collective-strictpc（{source_sha}）へ載せた。abm/ の変更は0ファイル。Python 3.12.13。',
    '',
    '診断予測：席の中身を一時的に薄くした状態で答えを計算し、値を測る --cf-value の計算。実際の世界への回答とは別に記録される。',
    '通信の束：相手へ伝える関係の集まり。仕様では、実際の回答から開示前に固定する。',
    '',
    '関門の設定は config/sweep_b2_hide_s1_2026-09-22.json、セル f0.5000_th2.1000_vt0.3842_first_order。B＋E、席の履歴・採点、四つの直し、--strict-pc --answer-gap --dump-answers --dump-routing --cf-value --probe-world を同時に使用。忘却・学習の値段はともに0.01873710622997919。eprice_check だけ学習の値段を0.2にした。各条件の全旗は保存した commands/*.argv.json と runs/*/flag.json にある。',
    '関門は順に1条件ずつ実行。個体走行の世界課題は8,880件（集団の確認5,100件、単独の確認3,780件）。使った世界の種は1と1001。種21〜40は使用していない。8体の集団と段3の試しは実行していない。',
    '',
    '### 小さな例と本文の一致',
    '',
    '前回の小例46件（U9・履歴5・採点5・B＋E11・予算16）、候補ごとの棄権6件、集団化12件、現行旗の受信・試験4件、計68件を全件実行し、失敗・省略は0。試験の結果は small_examples.json と small_examples/ に保存。',
    '',
    '| 現行の処理 | 確かめた小さな例・実受信 | 結果 |',
    '|---|---|---|',
    '| --strict-pc | 親の名前が同じでも子の名前が異なる束。受信時の対応は c2→d2 だけ | 一致 |',
    '| 引数の種類の控え | 空の記憶へ受信、二つ目の束で誕生。子の行を除いた部分定義でも、その位置を関係として保持 | 一致 |',
    '| --answer-gap | 受信から生まれた定義に、伏せた hold と見えている push の候補。見えている push を外し、hold を回答 | 一致 |',
    '| --e-price | 忘却0.01873710622997919、学習0.2。実受信168件の学習費用の係数 | 168/168件で0.2 |',
    '| 回答一致の試験の復元 | 現行の種類の控え、欠けた位置の記録、回数表の型と値を試験前へ戻す | 一致 |',
    '',
    '台帳本文：圧縮を開いた先頭の見出し1行を除く部分。SHA256は、その部分の一字一句の一致を検査する指紋。次の9組は全て一致。通信の再実行も、終了時の実行時間を含むまとめの行を除き、一字一句一致。',
    '',
    '| 左 / 右 | 世界の種 | 本文の行数（片側） | 本文のSHA256（左右同じ） |',
    '|---|---:|---:|---|',
]
for p in hashes['body_pairs']:
    lines.append(f"| {p['a']} / {p['b']} | {p['seed']} | {p['left']['rows']} | {p['left']['sha256']} |")
lines += [
    '',
    'off_base/off_port は集団化を切った現行版と載せ直した版。notags は名札を切った二体、q0 は名札あり・送信確率0。repeat1/repeat2 は受信B・送信確率0.5の同条件の再実行。noprobe は回答一致の試験だけを切った条件（--cf-value と --probe-world は維持）。recvA_check は受信A・送信確率0.5。いずれも段3の試しではない。',
    '',
    '### 不通の具体例',
    '',
    'q0、二体目、世界の種1001、台帳の試行番号14（15番目の課題）。期待：実回答 stack を含む束を固定し、後の診断で書き換えない。実際：台帳の実回答は stack、束の予測は push。関係IDと二つの引数は同じ。束は10関係、送信はなし。',
    f"実回答：{example['world']['predicted_edge']}。束の予測：{example['bundle']['pred']}。",
    '同試行の --cf-value は席0・7・9を順に測り、最後の席9の診断回答が push。実回答 stack の費用0、診断 push の費用6。束に残った名前は、この最後の診断回答と一致した。',
    '',
    f"別の例：eprice_check、個体{silent_sent['agent']}、世界の種{silent_sent['seed']}、試行番号{silent_sent['trial_zero_based']}（{silent_sent['trial_zero_based']+1}番目）。実際の世界では棄権（{silent_sent['world']['abstain_reason']}）、束の予測は {silent_sent['bundle']['pred'][1]}、送信あり。期待は、棄権した試行では送信しないこと。",
    '',
    'コードの経路：tools/cfvalue.py:135 が診断に inner_predict を呼ぶ。載せ直した組合せでは tools/v311c.py:557 が通信待ちの CTX["bundle"] を消し、同:587 が診断の束を保存する。診断の保存・復元（tools/probeworld.py:31〜46）の対象に v311c は入っていない。tools/v311c.py:610 は残った束を取り出して通信へ渡す。現行版の診断道具のコードは変更していない。',
    'ここでは保存済みの台帳・通信・診断の記録とコードを照合した。診断の旗を切り分けた追加走行は行っていない。最小例の全行を minimal_examples.json に保存。',
    '',
    '### 受入検査中の件数',
    '',
    '予測の相違は、関係ID・述語・引数を実際の世界への回答と比較した件数。棄権時は実回答が無いので相違に含む。空でない束だけを対象とした。繰り返し条件は同じ走行の再現検査であり、独立した本番標本として足していない。本番の頻度と、その後の学習・成績への差は未計測。',
    '',
    '| 条件 / 集団の種 | 世界課題 | 空でない束 | 実世界で棄権した試行の束 | そのうち送信 | 束と実回答の予測の相違 | 送信した束の予測の相違 / 送信 |',
    '|---|---:|---:|---:|---:|---:|---|',
]
for r in differences:
    o = next(o for o in observed if (o['condition'], o['run']) == (r['condition'], r['run']))
    c = r['counts']
    n = int(r['run'].split('.')[0][3:])
    lines.append(f"| {r['condition']} / {n} | {o['数']['課題']} | {c.get('nonempty_bundles',0)} | {c.get('bundles_in_abstained_world_trial',0)} | {c.get('sent_in_abstained_world_trial',0)} | {c.get('bundle_prediction_differs_from_world_prediction',0)} | {c.get('sent_prediction_differs_from_world_prediction',0)} / {o['数'].get('送信',0)} |")
lines += [
    '',
    '受入検査③の「沈黙では送らず」と④の「開示で束が書き換わらず」に対し、上の不一致を記録。⑫の「束のある試行は台帳で実際に答えた試行」は、名札ありの8集団の記録で不一致、名札なしの2集団で一致。関門の件数検査で不一致を検出し、停止した。',
    '同じ10集団について、個体ごとの正解＋誤答＋棄権＝課題数、誤答の出どころの和、回答一致の四分類の和、送信＝配達＝受け取り、一個体一試行の束は一つ以下、受信から同試行への再送なしは一致。実受信の通常の採点変更・価値の変更・記憶費用の見積りと実値の不一致は全条件0。これらの一致を、①〜⑫全体の合格とはしていない。',
    '',
    '受入検査①②は上記の本文比較で一致。⑤〜⑨の束の参照・名札・受信・費用・初期採点の小例は実行済み。⑩の再現と⑪の回答一致試験の前後の本文は一致。③④⑫は不通。',
    '',
    '保存先：mac/collective_strictpc_20261001/gate2/。68小例、本文9組、10集団の数え、予測の相違の全行、最小例、168実受信の費用、通信の元記録、旗と実行引数、停止の記録、解析の台本を保存。台帳の全ファイルは自分の作業場所 '+str(OUT)+' に保持し、ledger_manifest.json に本文の指紋と場所を記載。',
    '段3（お店の世界1・2、受信Aと通信なし、各種1〜3）は未開始。例外・通常のドアの比較、例外由来の束の取り込み・使用・再伝達の表は未作成。関門の不通後に本番枝への修正、新しいタグ、再走行は行っていない。',
]
with REPORT.open('a') as stream:
    stream.write('\n'.join(lines)+'\n')
manifest = [{'path': str(p.relative_to(DEST)), 'size': p.stat().st_size,
             'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(DEST.rglob('*')) if p.is_file()]
save(DEST/'files.json', manifest)
print(json.dumps({'files': len(manifest)+1, 'bytes': sum(x['size'] for x in manifest),
                  'report': str(REPORT), 'gate_passed': False, 'pilot_runs': 0}, ensure_ascii=False))
