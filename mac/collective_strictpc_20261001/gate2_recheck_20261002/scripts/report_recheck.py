"""関門の再検査の記録を保存する。走行と模型の変更はしない。"""
from datetime import datetime
from zoneinfo import ZoneInfo
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'outputs_recheck_2026-10-02'
RESULTS = ROOT.parents[1]/'codex_worldv4_2026-10-01/results'
DEST = RESULTS/'mac/collective_strictpc_20261001/gate2_recheck_20261002'
REPORT = RESULTS/'control/2026-10-01_穴出しと集団化_Codex.md'
MARKER = '### 関門2の再検査（2026-10-02）'


def read(name):
    return json.loads((OUT/name).read_text())


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1)+'\n')


def main():
    gate = read('gate_passed.json')
    assert gate['small_examples'] == 69 and gate['populations_audited'] == 16
    assert not DEST.exists() and MARKER not in REPORT.read_text()
    DEST.mkdir(parents=True)
    small, hashes, audits, diag, costs = [read(n) for n in ('small_examples.json', 'checks_hashes.json',
                                                         'checks_counts.json', 'diagnostic_noninterference.json',
                                                         'eprice_receipts.json')]
    for name in ('small_examples.json', 'checks_hashes.json', 'checks_counts.json',
                 'diagnostic_noninterference.json', 'gate_passed.json'):
        shutil.copyfile(OUT/name, DEST/name)
    (DEST/'eprice_receipts.json.gz').write_bytes(gzip.compress((OUT/'eprice_receipts.json').read_bytes(), mtime=0))
    for path in sorted(OUT.glob('pytest_*')):
        target = DEST/'small_examples'/path.name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(path, target)
    for path in sorted(OUT.glob('*.argv.json')):
        target = DEST/'commands'/path.name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(path, target)
    manifest = []
    for run in sorted(p for p in OUT.iterdir() if p.is_dir()):
        if (run/'flag.json').exists():
            target = DEST/'runs'/run.name/'flag.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(run/'flag.json', target)
        for path in sorted((run/'comm').glob('*')):
            target = DEST/'runs'/run.name/'comm'/(path.name+'.gz' if path.suffix == '.jsonl' else path.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == '.jsonl':
                target.write_bytes(gzip.compress(path.read_bytes(), mtime=0))
            else:
                shutil.copyfile(path, target)
        for path in sorted((run/'ledgers/cells').glob('*/*.jsonl.gz')):
            assert int(path.name.split('.')[0][4:]) in (1, 1001)
            body = hashlib.sha256()
            rows = 0
            with gzip.open(path, 'rb') as stream:
                next(stream)
                for line in stream:
                    body.update(line)
                    rows += 1
            manifest.append({'condition': run.name, 'path': str(path), 'rows': rows,
                             'body_sha256': body.hexdigest(),
                             'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    assert sum(x['rows'] for x in manifest) == 12480
    save(DEST/'ledger_manifest.json', manifest)
    comm = [json.loads(line) for line in (OUT/'q0/comm/run001.jsonl').read_text().splitlines()]
    bundle = next(r for r in comm if r['kind'] == 'bundle' and r['agent'] == 1 and r['t'] == 14)
    path = next((OUT/'q0/ledgers/cells').glob('*/seed1001.jsonl.gz'))
    with gzip.open(path, 'rt') as stream:
        next(stream)
        world = next(r for line in stream if (r := json.loads(line))['prediction_order'] == 14)
    assert bundle['pred'][1] == world['predicted_edge']['predicate'] == 'stack'
    save(DEST/'previous_example_recheck.json', {'world': world, 'bundle': bundle})
    source = ROOT/'source'
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    changed = subprocess.check_output(['git', 'diff', '--name-only', 'c207655'], cwd=source, text=True).splitlines()
    assert not any(x.startswith('abm/') for x in changed)
    save(DEST/'source_and_scope.json', {'source': sha, 'branch': 'codex-collective-strictpc',
                                      'base': gate['base'], 'abm_changed_files': 0,
                                      'python': '3.12.13', 'diagnostic_change_files': changed})
    target = DEST/'scripts'
    target.mkdir()
    shutil.copyfile(Path(__file__), target/'report_recheck.py')
    lines = [
        '\n'+MARKER+'\n',
        f'保存時刻：{datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")}。コード codex-collective-strictpc（{sha}）。土台88e0e38を保持。関門2は通過。',
        '',
        '指定どおり tools/probeworld.py の保存・復元に v311c の CTX・STATS・CFG を追加した。通信待ちの束、送信判断と名札の発行番号、送信設定を診断前へ戻す。--cf-value も同じ保存・復元を使う。abm/・世界・開示の確率・式は変更していない。前回の停止の記録と台帳は保持。',
        '',
        '小例：前回64件、現行の受信・試験4件、診断の保存・復元1件、計69件が通過（失敗・省略0）。全検査でPython 3.12.13。',
        '新しい確認は前回と同じ設定・値段で12,480世界課題。受信A・Bの通信検査は各個体300試行、送信確率0.5。種1と1001だけを使用。',
        '',
        '| 受入検査 | 再検査の結果 |',
        '|---|---|',
        '| ① 機能を切れば個体版と一致 | seed001・1740試行、見出しを除く台帳本文の指紋と行数が一致 |',
        '| ② 通信なしの複数個体と単独 | 名札なし、名札あり・送信確率0の各seed001・seed1001で本文一致 |',
        '| ③ 沈黙では送らず、予測を増やさない | 全16集団で棄権した試行の束0。一個体一試行の束は最多1。小例も通過 |',
        '| ④ 開示前に固定し、受け手へ真偽情報を渡さない | 全16集団で束の予測と実回答の相違0。公開入力の小例通過。前回の例もstack→stack |',
        '| ⑤ 参照先 | 多段追加・予測への参照・連鎖除外・共有参照・付け直しの小例通過 |',
        '| ⑥ 受信A/Bと空の記憶 | 小例、役割の観察、Uの照合・新世代の初期評価の追加例通過 |',
        '| ⑦ 名札の回数と抽選 | 小例通過 |',
        '| ⑧ 名札の費用 | 小例通過。全16集団の費用の見積りと実値の相違0 |',
        '| ⑨ 受信の採点 | 小例通過。全16集団で既存の席の通常採点・価値の変更0 |',
        '| ⑩ 受信から同試行の再送なし・再現 | 件数の検査と二回の本文・通信記録の一致 |',
        '| ⑪ 回答一致の試験の非介入 | 試験あり／なしの本文2組が一致。保存・復元の小例通過 |',
        '| ⑫ 台帳と件数の和 | 全16集団で世界課題・誤答の出どころ・四分類・送配受・束と実回答を突き合わせ、一致 |',
        '',
        '本文の比較9組は全て一致（checks_hashes.json）。追加の診断の比較6組でも各二体の本文、計12組が一致。',
        '通信の比較は、終了時のまとめ1行を除く元の通信記録をそのまま比較した。束の関係・名札・送信判断・宛先に加え、受信・再発話・回答一致の試験の記録も一字一句一致。まとめには実行時間と診断の旗の情報があるため比較から外した。',
        '',
        '| 受信 | 比べる旗 | 診断両方ありとの通信の指紋（両側同じ） | 二体の台帳本文 |',
        '|---|---|---|---|',
    ]
    for p in diag:
        mode = p['condition'].split('_')[1]
        flag = '・'.join(p['flags']) or '診断なし'
        lines.append(f"| {mode} | {flag} | {p['communication_sha256_reference']} | 2/2組一致 |")
    lines += ['', '| 確認条件 / 集団の種 | 世界課題 | 束 | 送信 | 受信 | 実回答と束の相違 |',
              '|---|---:|---:|---:|---:|---:|']
    for a in audits:
        n = a['数']
        run = int(a['run'].split('.')[0][3:])
        lines.append(f"| {a['condition']} / {run} | {n['課題']} | {n.get('束',0)} | {n.get('送信',0)} | {n.get('受け取り',0)} | {a['実回答と束の予測の相違']} |")
    lines += [
        '',
        f"--e-price の実受信の検査：忘却0.01873710622997919・学習0.2、費用を記録した受信{costs['receipts_with_costs']}件の全件で学習の係数0.2。",
        f'前回の最小例：q0、二体目、世界の種1001、試行番号14（15番目）。今回は台帳の実回答 stack、束の予測 stack。送信なし。全行を previous_example_recheck.json に保存。',
        '',
        '保存先：mac/collective_strictpc_20261001/gate2_recheck_20261002/。小例・指紋・全16集団の数え・通信の元記録・旗・実行引数・受信費用・台帳一覧を保存。新しい全台帳は '+str(OUT)+' に保持。',
        '段2の再検査の報告を保存し、段3（お店の世界1・2、受信A・通信なし、各集団の種1〜3）へ進む。',
    ]
    with REPORT.open('a') as f:
        f.write('\n'.join(lines)+'\n')
    files = [{'path': str(p.relative_to(DEST)), 'size': p.stat().st_size,
              'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(DEST.rglob('*')) if p.is_file()]
    save(DEST/'files.json', files)
    print(json.dumps({'files': len(files)+1, 'bytes': sum(x['size'] for x in files), 'gate_passed': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
