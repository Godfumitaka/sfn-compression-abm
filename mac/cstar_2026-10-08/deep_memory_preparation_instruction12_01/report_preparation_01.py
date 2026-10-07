"""未接続のメモリ観測の準備と小例を、一度だけ指定の報告へ保存する。"""
from pathlib import Path
from datetime import datetime
import fcntl
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]
PENDING = BASE / 'codex_cstar_pending_2026-10-06'
REPO = BASE / 'codex_worldv4_2026-10-01/results'
LOCK = BASE / 'codex_sme_light_2026-10-04/control_writer_01.lock'
REPORT = 'control/2026-10-08_C星の一本の時間の内訳_Codex.md'
MAIN = 'control/2026-10-07_C星の照合とディリクレ_実装_Codex.md'
INBOX = 'control/受け箱/SMEの係.md'
PROOF = 'mac/cstar_2026-10-08/deep_memory_preparation_instruction12_01'
MARKER = ROOT / 'reported_preparation_01.json'


def now():
    return datetime.now().astimezone().isoformat()


def read(path):
    return json.loads(path.read_text())


def git(*args):
    result = subprocess.run(['git', *args], cwd=REPO, capture_output=True, text=True)
    with (ROOT / 'report_git_01.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(at=now(), args=args, exit=result.returncode,
                                    out=result.stdout, err=result.stderr), ensure_ascii=False) + '\n')
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def main():
    assert not MARKER.exists(), '済んだ準備を重複して報告しない'
    prep = read(ROOT / 'preparation_01.json')
    checks = read(ROOT / 'checks_01.json')
    assert checks['passed'] and len(checks['checks']) == 7
    assert prep['state'] == 'prepared_not_launched' and not prep['model_started']
    for name, digest in prep['sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    with LOCK.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert not git('status', '--porcelain').strip(), '汚れた作業状態。解決しない'
        git('fetch', 'origin', 'results-2026-09-27')
        git('rebase', 'origin/results-2026-09-27')
        body = (REPO / INBOX).read_text()
        sections = re.findall(r'^## 指示 .*?(?=^## 指示 |\Z)', body, re.M | re.S)
        assert all('受領（' in section or '保留：アストラの承認待ち' in section
                   for section in sections), '新しい指示を先に読む'
        # 既存の16指示の範囲だけの準備。新しい優先の指示があれば先に読む。
        assert len(sections) == 16, '新しい指示を先に読む'
        section = re.search(r'^## 指示 12（.*?(?=^## 指示 |\Z)', body, re.M | re.S)
        assert section and '済み（' not in section[0]
        at = now()
        addition = (f'\n- 進み（{at}、SMEの係）：未完了の深いメモリの観測の部品を別の出力先へ準備。'
                    '模型を動かさない1GB受付76755で共有・循環・文字の鍵・属性・上限の小例7件が通過。'
                    '観測は模型へ未接続、現在の索引と高さの全長のコード・旗・入力は不変。'
                    '同じ実体を一度だけ数えるsys.getsizeof合計、現在の常駐、過去最大を分ける。'
                    f'実測と模型の全バイト関門は未完了。報告：{REPORT}。\n\n')
        (REPO / INBOX).write_text(body[:section.end()] + addition + body[section.end():])
        text = f'\n## 指示12の深いメモリの観測の準備（{at}）\n\n'
        text += ('現在の索引と高さの全長の11GB受付64842はそのまま継続。原版7774b60と作業版e05f990、'
                 '途中の模型・観測・旗・値を変更していない。別の出力先のメモリ観測だけを準備し、'
                 'まだ模型へ接続していない。新しく始めた模型0本。\n\n')
        text += ('模型を動かさない1GB受付76755は2026-10-08 07:24に部品検査を完了し、受付が自動で解放された。'
                 '共有・循環とUnicodeの鍵、根の間の共通実体、slotsの属性と型の除外、読み取り専用の辞書、'
                 '呼び出し種の記録と乱数の不変、観測の上限、正確な番地の控えの7件が通過。'
                 '小例1件は同じ組を3箇所で共有し、自分の辞書へ戻る循環を含む8実体・626バイトで、'
                 '通常の集合を使う独立の小例の数え方と一致した。既存の構造14件・部品18組・encode269件は再実行していない。\n\n')
        text += ('数えるものは、指定したデータの根から届くPythonの実体のsys.getsizeofの合計。'
                 '番地を8バイトごとの正確なビットで控え、同じ実体を根の間でも一度しか足さない。'
                 '大きいIDの集合や保存状態の写しを作らず、番地の控えの上限は準備の前に256MiBと固定した。'
                 '上限で読めなければ不完全と書き、模型の入力や記憶や乱数を変更せず、次の模型は始めない。\n\n')
        text += ('根の順はC*のcache・cache_rng・self_cache、SMEの同じ3辞書、sharedのRESULTS・GRAPHS・CHOICES。'
                 '共通の実体は先の根へ一度だけ含めるため、各根の独立した所有量とは呼ばない。'
                 '固定した試行100・1000・1740の予測直後と終了時に読む準備。試行1400の最初の照合器の戻りと'
                 '最初の保存の写しでは、生きている作業用の物や写しを根の末尾へ足し、新しく届く実体だけを読む。'
                 '20試行の前置きでは試行20を使う。模型の結果に応じて読む試行を選ばない。\n\n')
        text += ('現在の常駐は同じ過程のps、過去最大はru_maxrssとして別々に記録する準備。'
                 '観測の控えのバイトとCPUも別に記録する。型・関数・module等の実行環境、割り当て器の余白・未使用ページ、'
                 'Cの内部でsys.getsizeofとgcの参照に出ない領域は含まない。常駐との差を候補のメモリとは断定しない。'
                 '観測のために__dict__を新しく実体化せず、乱数・採点・候補の選び・記録の内容を変えない。速度の比較に使わない。\n\n')
        text += ('開始は現在の4条件の全長の一致と受付の終了の後、最新の指示・自分の模型と受付・資源・期限を確認してから。'
                 '原版7774b60、C*②、世界2・種1・PYTHONHASHSEED=0、horizon1740と元の旗・値の別出力へ、'
                 '20試行1GBの観測と7ファイルの全バイト関門を先に通し、その実測が11GBに収まる条件を満たすときだけ全1740試行へ進む計画。'
                 '台帳本体・全side・保存状態と乱数を比較し、除外は見出しとsec_trialだけ。不通・不一致を直そうとせず報告する。'
                 '現在は関門も深いメモリの実測も未実行。指示12を済みにしない。\n\n')
        text += f'準備・観測と集計の台本・小例・SHAの小さい証拠：{PROOF}。\n'
        with (REPO / REPORT).open('a') as stream:
            stream.write(text)
        with (REPO / MAIN).open('a') as stream:
            stream.write(f'\n### 指示12の未接続のメモリ観測の準備（{at}）\n\n'
                         '共有と循環の同じ実体を一度だけ数える部品は、模型なしの1GB受付76755で小例7件が通過。'
                         '現在の全長の模型とコードは不変。固定した試行の控え・照合器・写しのsys.getsizeof合計を、'
                         '現在の常駐と過去最大と観測の控えから分ける準備。別出力の観測は未接続で、模型の実測と全バイト関門は未完了。'
                         f'報告：{REPORT}。\n')
        destination = REPO / PROOF
        destination.mkdir(parents=True, exist_ok=False)
        for name in ('retained_size_01.py', 'check_retained_size_01.py', 'observe_memory_01.py',
                     'checks_01.json', 'preparation_01.json', 'report_preparation_01.py'):
            path = ROOT / name
            assert path.stat().st_size < 2**20
            shutil.copy2(path, destination / name)
        (destination / 'sha256.json').write_text(json.dumps({path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in destination.iterdir() if path.is_file()}, indent=2) + '\n')
        git('sparse-checkout', 'add', PROOF)
        git('add', '--sparse', INBOX, REPORT, MAIN, PROOF)
        git('commit', '-m', '指示12の未接続のメモリ観測と小例7件を報告')
        git('fetch', 'origin', 'results-2026-09-27')
        git('rebase', 'origin/results-2026-09-27')
        git('push', 'origin', 'HEAD:results-2026-09-27')
        result = dict(at=at, reported=True, commit=git('rev-parse', 'HEAD').strip(), report=REPORT,
                      proof=PROOF, model_not_started=True)
        MARKER.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        path = PENDING / 'pending_01.json'
        pending = read(path)
        pending.update(deep_memory_preparation=result, deep_memory_root=str(ROOT),
                       deep_memory_prepared=True, deep_memory_model_started=False,
                       deep_memory_component_checks_done=True, deep_memory_component_checks_count=7)
        path.write_text(json.dumps(pending, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        (ROOT / 'report_preparation_STOP_01.json').write_text(json.dumps(dict(
            at=now(), reason=str(exc), conflicts_not_resolved=True), ensure_ascii=False, indent=2) + '\n')
        raise
