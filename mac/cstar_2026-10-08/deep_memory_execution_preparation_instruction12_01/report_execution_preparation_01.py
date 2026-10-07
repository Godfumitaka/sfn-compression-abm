"""観測の起動前の固定した命令と確認手順を、一度だけ報告する。"""
from pathlib import Path
from datetime import datetime
import fcntl, hashlib, json, re, shutil, subprocess

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent.parent
REPO = BASE/'codex_worldv4_2026-10-01/results'
PROOF = 'mac/cstar_2026-10-08/deep_memory_execution_preparation_instruction12_01'
MARKER = ROOT/'reported_execution_preparation_01.json'
REPORT = 'control/2026-10-08_C星の一本の時間の内訳_Codex.md'
MAIN = 'control/2026-10-07_C星の照合とディリクレ_実装_Codex.md'
INBOX = 'control/受け箱/SMEの係.md'

def now():
    return datetime.now().astimezone().isoformat()

def git(*args):
    p = subprocess.run(['git', *args], cwd=REPO, capture_output=True, text=True)
    with (ROOT/'execution_report_git_01.jsonl').open('a') as f:
        f.write(json.dumps(dict(at=now(), args=args, exit=p.returncode, out=p.stdout, err=p.stderr), ensure_ascii=False)+'\n')
    if p.returncode:
        raise RuntimeError(p.stderr)
    return p.stdout

try:
    assert not MARKER.exists(), '同じ準備を重複報告しない'
    assert not (ROOT/'preflight20_01').exists(), '接続前の準備の報告だけ'
    plan = json.loads((ROOT/'execution_plan_01.json').read_text())
    for name, sha in plan['scripts_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == sha
    with (BASE/'codex_sme_light_2026-10-04/control_writer_01.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert not git('status', '--porcelain').strip(), '汚れた作業状態。解決しない'
        git('fetch', 'origin', 'results-2026-09-27')
        git('rebase', 'origin/results-2026-09-27')
        body = (REPO/INBOX).read_text()
        sections = re.findall(r'^## 指示 .*?(?=^## 指示 |\Z)', body, re.M|re.S)
        assert len(sections) == 16 and all('受領（' in s for s in sections), '新しい指示を先に読む'
        section = re.search(r'^## 指示 12（.*?(?=^## 指示 |\Z)', body, re.M|re.S)
        assert section and '済み（' not in section[0]
        at = now()
        text = ('\n### 指示12のメモリ観測の起動前の確認（'+at+'）\n\n'
                '原版7774b60と観測のSHAは準備時のまま。20試行と全1740試行の命令は、済んだ個別計測の命令と出力先・前置きの試行数以外すべて一致。'
                '起動・受付・監督は未開始。現在の索引と高さの旗ありC*の模型・旗・観測を変更していない。\n\n'
                '新しい監督と起動の台本は、前の全長4条件の全ファイルの一致と11GB受付64842の終了、最新の受け箱と列、'
                '自分の別の模型と受付の不在、機械全体8本・空き20GiB・熱・スワップ・期限を確かめ、同じ出力先の受付・途中・完了を二重に始めない。'
                '受付後も各模型の開始前に期限と原版・観測のSHAを確かめる。期限だけで動いている模型を止めない。\n\n'
                '20試行は1GBの読み取りを含む計測受付。参照の集計4箇所が完全で、台帳本体・全side・保存状態と乱数の7ファイルが原版と全バイト一致してから、'
                '別の全長11GB受付へ進む。全長は自動起動しない。不完全・不通・不一致なら、小例と件数を残し後続を始めない。比較の除外は台帳の見出しとsec_trialだけ。\n\n'
                '全長の受付の見込みは、原版の直近の全長の模型の木の常駐最大へ、固定した番地の控え256MiB、管理欄と小さい表の余裕16MiB、'
                '観測20試行と観測なし20試行の常駐最大の差の正の分を足す。この式を20試行の結果を見る前に固定した。'
                '11GiB以下の見込みにならなければ全長を受け付けず報告する。常駐の厳密な上限とは呼ばず、受付の見込みを減らさず、'
                '模型の値・観測点・256MiBの上限を結果で替えない。\n\n'
                '新しい台本の構文と命令・既存SHAの一致を模型を動かさず確認。済んだ部品7件・構造18組・14件・encode269件は再実行していない。'
                '深いメモリの実測と模型での観測の関門は未完了。指示12は未完了。小さい台本・固定した式・SHAの証拠：'+PROOF+'。\n')
        for path in (REPORT, MAIN):
            with (REPO/path).open('a') as f:
                f.write(text)
        addition = ('\n- 進み（'+at+'、SMEの係）：原版7774b60の別出力のメモリ観測の起動前の確認と二重起動防止を準備。'
                    '固定した観測のSHAと命令は不変、接続・受付・模型は未開始。20試行の完全な参照集計と7ファイル一致、'
                    '固定した11GBに収まる見込みを満たしてから全長へ進む。報告：'+REPORT+'。\n\n')
        (REPO/INBOX).write_text(body[:section.end()]+addition+body[section.end():])
        dest = REPO/PROOF
        dest.mkdir(parents=True, exist_ok=False)
        for name in ('run_memory_01.py','launch_memory_01.py','execution_plan_01.json','execution_prepared_01.json','report_execution_preparation_01.py'):
            shutil.copy2(ROOT/name, dest/name)
        (dest/'sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.iterdir()}, indent=2)+'\n')
        git('sparse-checkout', 'add', PROOF)
        git('add', '--sparse', REPORT, MAIN, INBOX, PROOF)
        git('commit', '-m', '指示12のメモリ観測の起動前の確認を準備')
        git('fetch', 'origin', 'results-2026-09-27')
        git('rebase', 'origin/results-2026-09-27')
        git('push', 'origin', 'HEAD:results-2026-09-27')
        result = dict(at=at, reported=True, commit=git('rev-parse','HEAD').strip(), proof=PROOF, model_started=False)
        MARKER.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps(result, ensure_ascii=False), flush=True)
except Exception as exc:
    (ROOT/'report_execution_preparation_STOP_01.json').write_text(json.dumps(dict(at=now(), reason=str(exc), conflicts_not_resolved=True), ensure_ascii=False, indent=2)+'\n')
    raise
