"""Aの完了証拠と本番argvの控えを保存し、B未着手を明記する。"""
from pathlib import Path
import datetime, hashlib, json, shutil, shlex, sys

here = Path(__file__).resolve().parent
port = here.parent
report = port / 'report'
sys.path.insert(0, str(port))
from admission_guard import census

rows, active, paused = census()
parents = set()
for pid in active | paused:
    parent = rows[pid]['parent']; seen = set()
    while parent in rows and parent not in seen:
        seen.add(parent)
        if parent in active | paused: parents.add(parent)
        parent = rows[parent]['parent']
active -= parents; paused -= parents
at = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
assert len(active) < 8 and shutil.disk_usage(here).free >= 20 * 2**30
(here/'A_report_before_start_01.json').write_text(json.dumps(dict(at_jst=at,
    active=len(active), paused=len(paused), excluded_parents=sorted(parents),
    processes=[dict(pid=pid, **rows[pid]) for pid in sorted(active | paused)],
    free_disk_bytes=shutil.disk_usage(here).free), ensure_ascii=False, indent=2)+'\n')
verification = json.loads((here/'completed_A_verification_01.json').read_text())
assert verification['status'] == 'passed'
evidence = report/'control/2026-10-07_介入_新しい版の移植_Codex/指示13_A全関門と本番argv_20261010_0308'
evidence.mkdir(exist_ok=False)
files = {}
for name in ['A_off_comparison_01.json', 'off_comparison_01_status.json',
             'off_comparison_before_start_01.json', 'off_comparison_protected_after_01.json',
             'off_comparison_01.log', 'off_comparison_01_admission.log', 'run_off_compare_01.py',
             'completed_A_verification_01.json', 'completed_A_before_start_01.json',
             'completed_A_verification_01_admission.log', 'verify_completed_A_01.py',
             'production_A_argv_01.json', 'commands_fixed_A.json', 'compare_A.py',
             'comparator_reference.json', 'baseline_A_reference.json', 'A_report_before_start_01.json']:
    files[name] = here/name
for label in ['A_fixed_off100', 'A_fixed_D_attention_04', 'A_fixed_D_attention_015']:
    for name in ['status.json', 'before_start.json', 'protected_before.json', 'protected_after.json', 'model.log']:
        files[f'{label}/{name}'] = here/label/name
    files[f'{label}_admission.log'] = here/f'{label}_admission.log'
    output = here/label/'output'
    for p in output.rglob('*'):
        if not p.is_file(): continue
        # 全出力のSHAは完了点検に保存。大きなside本体は原出力先に保持する。
        if p.name in ['flag.json', 'manifest.jsonl', 'partial_done.json', 'checkpoints.jsonl'] or p.suffix == '.done' or 'checks.json' in p.name or 'retention' in p.parts or p.name.endswith('.useforget.jsonl'):
            files[f'{label}/output/{p.relative_to(output)}'] = p
files['instruction13_status_A_completed.json'] = port/'instruction13_status.json'
files['instruction12_status_A_completed.json'] = port/'instruction12_status.json'
manifest = {}
for name, source in files.items():
    dest = evidence/name; dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert hashlib.sha256(dest.read_bytes()).hexdigest() == digest
    manifest[name] = dict(source=str(source), sha256=digest, size=source.stat().st_size)
(evidence/'evidence_sha256.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
off = json.loads((here/'A_fixed_off100/status.json').read_text())
compare = json.loads((here/'off_comparison_01_status.json').read_text())
prod = json.loads((here/'production_A_argv_01.json').read_text())
lines = [f'\n\n## 指示13A：全関門の完了、動詞の受け入れ版と本番argv（{at}）',
    '\n指示12Aと指示13の動詞Aの関門が揃った。受け入れ実コミットは94dbebc259981eec86efab1864f61df86ec68dd3（枝codex/verb-d-probe-fix-instruction13-2026-10-10、通常push済み）。旧候補54f0a412、旧停止、診断二枝、元命令、全出力と一時資料を保持する。指示12・13全体はBが未着手のため未完了で、済みを付けない。',
    f'\n旗off100は{off["ended_at_jst"]}に自然終了0、模型{off["model_seconds"]:.6f}秒、最大RSS{off["peak_children_rss_bytes"]}バイト。受付待ち{off["admission_wait_seconds"]:.6f}秒、CPU枠待ち{off["cpu_wait_seconds"]:.6f}秒。',
    f'\n通常受付41910（0.3GB）で保存済み6e4の同じマック・起動指紋の100と比較し、{compare["ended_at_jst"]}に通過。実在模型16ファイルの名前集合・原順・全バイトとmanifest26研究者辞書が一致、flag全バイト一致、完了札は両側存在。試験行を含み、除外は既存の時間欄のみ。受付待ち{compare["admission_wait_seconds"]:.6f}秒、CPU枠待ち{compare["cpu_wait_seconds"]:.6f}秒、解析{compare["analysis_seconds"]:.6f}秒。左側は再走行していない。']
for label, pid, tau in [('A_fixed_D_attention_04',42005,'0.4'),('A_fixed_D_attention_015',42031,'0.15')]:
    s = json.loads((here/label/'status.json').read_text()); v = verification['runs'][label]
    lines.append(f'\nτ{tau}は受付{pid}（0.5GB）、入口{s["wrapper_pid"]}、模型親{s["model_parent_pid"]}で{s["started_at_jst"]}から{s["ended_at_jst"]}に自然終了0。世界は動詞、種1、設定5000・horizon5000の先頭200。q＋k2注意、score-logp-eなし、match-eps0、B価格0.00035129738499384776、E価格0.01873710622997919、第二段・誕生HU・reuse off。速度二部品は土台に無いため既に確認した未実装のoff二組を省いた保存命令を使った。受付待ち{s["admission_wait_seconds"]:.6f}秒、CPU枠待ち{s["cpu_wait_seconds"]:.6f}秒、模型{s["model_seconds"]:.6f}秒、最大RSS{s["peak_children_rss_bytes"]}バイト。台帳・保持・旧Dの記録は各200件。試行100・200の試験で全ST・AUDIT・D記録口の位置と原字節を含む控えの前後SHAが一致し、二重の不変検査が通過。旧資料・模型・候補の指紋は不変。')
lines.extend(['\n手例32件、旗off全バイト一致、二つのτの200自然終了と試験前後不変を通常受付42191（0.3GB）の完了点検で確認した。成績は関門の判定に使っていない。正式3b材料・実材料への介入・全種適用は行っていない。',
    '\n### 本番argvの控え（まだ本番を開始しない）',
    '\n以下は種1の全長5000の全argv。測定観察器は使わない。元草稿の出力先変数${VERB_PROD_OUT}を保持し、正式な列を埋める係が出力先を指定する。種の範囲、本番の機械と受付・取得は正式な列と命令を待つ。'])
for arm in ['21','21b']:
    lines.append(f'\n#{arm}、source_commit={prod[arm]["source_commit"]}、cwd={prod[arm]["cwd"]}、PYTHONHASHSEED=0。\n\n```text\n'+shlex.join(prod[arm]['argv'])+'\n```')
lines.append('\n本番の出力先や対象種を推測で確定しない。全argvはproduction_A_argv_01.jsonにも保存。次に指示12B5・7の計算論の分を先に進め、B6・7には同じ試験・反実仮想の抑止と全前後不変検査を引き継ぐ。未完了の指示2・3・5・8、bと正式3b材料の待ち、四つの禁止・受付・関門を維持する。')
lines.append(f'\n証拠：{evidence.relative_to(report)}（{len(manifest)}ファイルのSHA256）。D200の全出力のSHAはcompleted_A_verification_01.jsonへ保存し、全原出力はinstruction13の各outputに保持。')
main = report/'control/2026-10-07_介入_新しい版の移植_Codex.md'
text = main.read_text(); assert '## 指示13A：全関門の完了' not in text
main.write_text(text+'\n'.join(lines)+'\n')
inbox = report/'control/受け箱/探索の腕と介入の係.md'
with inbox.open('a') as out:
    out.write(f'\nAの関門完了（{at}、control/2026-10-07_介入_新しい版の移植_Codex.md）。別候補94dbebc2の手例32件、旗off100の16ファイルとmanifest26辞書の全バイト一致、τ0.4・0.15の200自然終了0と試行100・200の全D控え・原字節不変を通常受付で確認。動詞Aの受け入れ版と本番全argvの控えを報告へ保存。本番は正式な列・命令・取得待ち。次にB5・7、続いてB6・7と試験抑止を進める。指示12・13全体は未完了で済みを付けない。\n')
for name in ['instruction13_status.json','instruction12_status.json']:
    f = port/name; s = json.loads(f.read_text())
    s.update(A_report_prepared_at_jst=at, A_report_evidence=str(evidence), A_report_pushed=False)
    f.write_text(json.dumps(s, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(dict(at_jst=at,evidence=str(evidence),copied_files=len(manifest)), ensure_ascii=False))
