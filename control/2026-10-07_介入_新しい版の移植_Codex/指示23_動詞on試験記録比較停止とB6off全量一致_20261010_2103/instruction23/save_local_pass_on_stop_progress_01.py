"""実際の完了と最初の停止だけを保存し、旧状態と全資料を保持する。"""
from pathlib import Path
import datetime
import hashlib
import json
import shutil

here = Path(__file__).resolve().parent
port = here.parent
report = port/'report'
local = here/'local_pass_on_stop_01'
local.mkdir(exist_ok=False)
at = datetime.datetime.now().astimezone().isoformat()
label = 'candidate_on_D_04_200_01'
off = json.loads((port/'instruction22/candidate_off100_comparison_03.json').read_text())
on = json.loads((port/'instruction22'/label/'status.json').read_text())
verification = json.loads((port/'instruction22'/f'{label}_verification_02.json').read_text())
comparison = json.loads((port/'instruction22'/f'{label}_comparison_02.json').read_text())
b6 = json.loads((here/'B6_after_end_01/comparison_01.json').read_text())
assert off['passed'] and off['file_count'] == 16 and off['manifest_counts_comparison']['file_count'] == 26
assert on['state'] == 'completed' and on['exit_code'] == 0 and on['completed_trials'] == 200
assert verification['status'] == 'passed'
assert not comparison['passed'] and comparison['first_mismatch']['line'] == 5
assert b6['passed'] and len(b6['names']) == 27 and len(b6['checks']) == 31 and all(c['passed'] for c in b6['checks'])
assert not (port/'instruction22/candidate_on_D_015_200_01').exists()
assert json.loads((here/'on200_stop_evidence_01/first_stop_evidence_01.json').read_text())['both_outputs_unchanged']
public_name = '指示23_動詞on試験記録比較停止とB6off全量一致_20261010_2103'
public = report/'control/2026-10-07_介入_新しい版の移植_Codex'/public_name
public.mkdir(exist_ok=False)
for n in (12,13,14,17,20,21,22,23):
    path = port/f'instruction{n}_status.json'
    old = path.read_bytes()
    (local/f'instruction{n}_status.before.json').write_bytes(old)
    state = json.loads(old)
    state.update(completed=False, running_labels=[], queued_labels=[], last_update_at_jst=at,
        progress_evidence=str(local), report_pushed=False,
        report_delivery=str(here/'report_delivery_03.json'))
    if n in (12,13,14,17,20,21):
        state.update(state='B5_a_passed_B6_structure39_off200_full_passed_cloud_eight_gate_wait',
            b5_a_passed=True, b5_b_passed=False, b6_structure_passed=True,
            b6_off200_completed=True, b6_off200_verified=True, b6_off200_full_comparison_passed=True,
            b6_verification=str(here/'B6_after_end_01/verification_01.json'),
            b6_comparison=str(here/'B6_after_end_01/comparison_01.json'), candidate_accepted=False)
    else:
        state.update(state='candidate_off100_full_passed_on_tau04_200_verified_probe_record_sha_comparison_stopped_B6_off200_full_passed',
            off100_comparison_passed=True, off100_comparison_admission_ended=True,
            on_tau04_completed=True, on_tau04_verified=True, on_tau04_comparison_passed=False,
            on_tau04_status=str(port/'instruction22'/label/'status.json'),
            on_tau04_verification=str(port/'instruction22'/f'{label}_verification_02.json'),
            on_tau04_comparison=str(port/'instruction22'/f'{label}_comparison_02.json'),
            on_tau04_first_mismatch=comparison['first_mismatch'],
            numbered_probe_record_answer_wait=True, on_tau015_started=False, seed7_candidate_started=False,
            candidate_accepted=False, b6_off200_full_comparison_passed=True,
            b6_comparison=str(here/'B6_after_end_01/comparison_01.json'),
            next_steps=str(here/'NEXT_SAVED_STEPS_03.md'), additional_jobs_registered=7,
            desktop_records_received=False)
    path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    (local/f'instruction{n}_status.after.json').write_bytes(path.read_bytes())

progress = dict(at_jst=at, off100_passed=True, off100_files=16, off100_manifest_dictionaries=26,
    b6_off200_passed=True, b6_all_names=27, b6_checks=31, on_tau04_natural_exit=0,
    on_tau04_verified=True, on_tau04_all_D_before_after_unchanged=True,
    on_tau04_comparison_passed=False, on_tau04_first_mismatch=comparison['first_mismatch'],
    numbered_probe_record_answer_wait=True, model_starts_this_turn=1, on_tau015_started=False,
    seed7_candidate_started=False, model_or_comparison_reruns=False, candidates_accepted=False,
    production_changed=False, public_evidence=str(public))
(local/'latest_progress_01.json').write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n')
next_text = f'''# 指示23：保存状態からの次の手順（{at}）

新旗off100の全16ファイル・26研究者辞書は比較03でpassed。B6offON200は自然終了0、必要記録点検と全27名前・31項目の指定比較がpassed。変更がなければ模型・比較・構造40/39・必要点検を再実行しない。

動詞70dfの修正on・種1・τ0.4・先頭200は自然終了0、全ST/AUDIT・D記録の試験/cf前後不変と必要200行を点検済み。ただし保存94との比較はretention/f0.5000_th2.1000_vt0.3842_first_order/seed001.jsonl.probe_checks.jsonの5行目before_sha256でstopped。旧比較02/原出力/全資料を保持し、欄を除外せず、この係の番号付き回答又はアストラの直接文面まで、候補修正・比較再開・τ0.15・種7修正走行・完走種照合を始めない。

試験ごとのbefore_sha256とafter_sha256は両側とも一致。控えの構成別の原字節が保存されていないため、両側間のSHA差の原因を記録口の名称だけと断定しない。問いは受け箱の指示23の下。今の停止を次回ごとに新しい終了として知らせない。

B5(b)はデスクトップの既存依頼の元同じhost/bootの全c4実関門待ち。B6八体20の正式入口と草稿は保存済みで未依頼・未走行。B5(a)・B6構造39・B6off200の合格だけで929/e96を受け入れない。原全8実関門・B5(b)と実八体の受付/CPU8/容量20GiB/実測予約/永続出力先が揃うまで実八体を始めず、マックの模型へ八体を重ねない。本番は正式な列・全命令・取得を待つ。

候補70df/e96/929は未受け入れ。指示12〜14/17/20/21/22/23は未完了・済みなし。指示2/3/5/8とb/正式3b材料待ち、完了A94と指示9〜11/15/16/18/19を維持。全旧停止/候補/一時資料/命令/出力、四つの禁止、受付と移植関門を保持。期限2026-10-13 09:00 JST以後は新規作業を始めず継続確認を停止し、期限を理由に本番を止めない。新番号付き指示も新しい自分の終了も無い待機不変なら再計数/再登録/報告commit・push/予定更新をしない。

通常受付の完了済み比較のRSS実測はoff100が333447168B（予約0.3GB）、B6が770801664B（予約0.6GB）。警告と原予約を保持。今後の新規比較は実測と条件差/余裕から1GB、必要点検は0.3GBの別入口launch_candidate_on200_checks_03.pyを使う。既存模型や受付の予約・設定を変更しない。この別入口は点検と比較だけで、結果の参照は元02を保持する。現在の模型・受付は全て自然終了し、自分のrunning/queuedは空。
'''
next_path=here/'NEXT_SAVED_STEPS_03.md'
with next_path.open('x') as f:f.write(next_text)

files=[]
for folder in (local,here/'resource_measurement_01',here/'on200_stop_evidence_01',here/'B6_after_end_01'):
    files.extend(p for p in folder.rglob('*') if p.is_file() and p.name!='comparison_excluded_fields_01.json')
files.extend([next_path,here/'save_local_pass_on_stop_progress_01.py',here/'save_on200_first_stop_01.py',here/'pack_B6_clock_evidence_01.py',
    port/'instruction22/candidate_off100_comparison_03.json',here/'off100_comparison_admission_exit_04.json',
    here/'off100_comparison_admission_04.log',here/'off100_comparison_launch_request_04.json',
    port/'instruction22/launch_candidate_on200_checks_03.py',port/'instruction22/candidate_on200_commands_02.json',
    port/'instruction22/run_candidate_on200_02.py',port/'instruction22/verify_candidate_on200_02.py',port/'instruction22/compare_candidate_on200_02.py',
    port/'instruction22'/f'{label}_verification_02.json',port/'instruction22'/f'{label}_comparison_02.json'])
for mode,suffix in [('model','02'),('verification','03'),('comparison','03')]:
    files.extend(port/'instruction22'/f'{label}_{mode}_{stem}_{suffix}.{ext}'
        for stem,ext in [('launch_request','json'),('before_admission','json'),('admission','log')])
for case in (port/'instruction22'/label,port/'instruction21/B6_gate_03/B6_off_on200_candidate03'):
    files.extend(case/name for name in ('status.json','protected_before.json','protected_after.json','before_start.json','model.log') if (case/name).exists())
    if (case/'runtime.json').exists():files.append(case/'runtime.json')
    if (case/'output/measurement/partial_done.json').exists():files.append(case/'output/measurement/partial_done.json')
for path in sorted(set(files)):
    target=public/path.relative_to(port)
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(path,target)
index={str(p.relative_to(public)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(public.rglob('*')) if p.is_file()}
(public/'SHA256SUMS').write_text(''.join(f'{digest}  {name}\n' for name,digest in index.items()))

report_text=f'''

## 指示23：B6旗off200の全量一致、動詞修正on200の試験検査記録で比較停止（{at}）

新旗off先頭100の同じ比較受付68850（owner明示、0.3GB、実outputのdisk-path）は20:42:22 JSTに自然終了0。比較03で原94の全実在16ファイルの名前集合・原順・原字節と全26研究者辞書が一致。実版/歴史的札・同じhost/boot・100行・完了札の両側存在と物理サイズ・flag全字節を必須点検し、既存TIMEだけを扱い、試験行を含めた。比較3.178610秒、実測RSS333447168B。投入から受付と比較を含む605.250160秒、独立CPU待ちは未計測。原94と模型を再走行せず、旧読取停止を保持。

B6の同じ通常受付30265（3GB）は20:45:35.864931 JSTに自然終了0。模型19128.811995秒、受付待ち801.373131秒、CPU枠待ち0.860619秒、最大children RSS2745794560B、旧資料前後不変。受付71760（0.3GB）で必要記録点検が通過し、台帳200原順、完了札実版/物理サイズ、manifest1・通信全agent errorなし・辞書外0/辞書点検400、模型/Python乱数各200とPython大域不変、最終SME/C*控え・性能200・全ケース42ファイルのSHA・原資料不変を保存。点検開始20:59:53 JST、独立点検時間/受付待ち/CPU待ち/RSSは未計測とし、模型の値と混同しない。

受付71820（0.6GB）の保存929対e96の指定比較は21:00:28.893648 JSTに自然終了0。全27出力名・31項目が通過し、全模型行/原順/試験行、全研究者辞書、最終SME/C*・全乱数、必須メタデータと同じhost/boot・設定SHA/全argvを確認。指示16/20/21の固定コードで確認した指定時計と時計同士の比だけ、両側原値・全ファイル/行/欄名・コードSHA/実行番号を残して扱い、calls_per_disclosed_trial・totalsの回数と全残余欄を保持。比較7.192611秒、実測RSS770801664B、投入から入口0.206770秒、独立CPU待ちは未計測。全旧資料・両側出力・原比較器は不変。時計の全347764欄の控え94473398Bを、受付72200前後の保存ログにある実PIDで通常受付へ通して可逆gzip保存（4816307B）。解凍SHAと原前後SHAが3f90d0ccf39f23150c7d69b4ea44288a2923f90562678bd4a086b4fc1e77a439で一致し、全欄と原値を減らさず保存した。

off100の全量一致後だけ、動詞70dfの新修正on・種1・τ0.4・設定5000/horizon5000・同じ試験つき先頭200を受付71785（0.6GB）、入口71789、模型親71796から21:00:02.613595 JSTに一度開始。21:02:27.650112 JSTに自然終了0。模型145.035034秒、受付待ち0.169481秒、CPU枠待ち0.056907秒、最大children RSS286507008B。1109原資料/候補の前後不変。受付72294（0.3GB）の必要点検は21:03:13 JSTに通過。台帳/retention/旧D side各200、固定試験100/200とprobeworld二回の全ST/AUDIT・記録口の前後原字節不変、元の全旗/全argv/実版/完了札を確認した。

保存94との比較は受付72317（1GB）で21:03:31.188705 JSTに停止。両側の全15実在D模型記録名・200原順・実版/歴史的札/完了札物理サイズ、宣言済み新旗on以外のflag全字節を点検し、注意2・evictions2・台帳・retention本体の六比較が通過した範囲だけを保存する。最初の不一致はretention/f0.5000_th2.1000_vt0.3842_first_order/seed001.jsonl.probe_checks.jsonの5行目before_sha256。旧1cb59fb6a195b540d2784ef930a1847e2caddf40c28dcd8a9fa25785721c3870、新e70b46431482c07b67812e7704ed7c4e88284f8bb8a317780cbf3d5f0adc950a。455B対455B、最初の差は69字節目。比較1.467726秒、最大RSS302120960B、独立受付/CPU待ちは未計測。残るsideと全manifest辞書までの全量一致は未確認。

受付72392（0.3GB）で最初の小さい原記録と同じ固定useforget_cstar.pyを別保存し、両側全点検済み出力・1109原資料と候補の不変を確認。試験ごとのbefore_sha256==after_sha256は両側の100/200で成立。固定コード16〜24行はD.ST/AUDITと記録口の名称/位置/原字節をreprへ入れるが、構成別の原字節は保存されていないため、両側のSHA差の原因を名称だけと断定しない。証拠点検0.339197秒、最大RSS22216704B。研究者の検査記録を除外せず、候補修正・比較再開・τ0.15・種7修正走行・完走種照合を停止し、指示23の下へ扱いの番号付き回答又はアストラ直接文面を求める問いを記した。

資源警告：完了済み比較のRSSはoff100の予約0.3GB、B6の予約0.6GBを超えた。21:01:46の一回の警告記録は実模型4・停止0、全ps親子/低RSSを含め、待つ親/jobs/trackerを二重計数せず、空き179501195264B。原予約・完了結果を保持し再実行しない。これからの新規比較は二つの実測と試行数差/25%余裕から1GBへ切り上げた別入口checks03を保存。必要点検は0.3GB、走った模型の0.6GBと全設定を変更せず、受付/CPU8/容量20GiB/予約24GB/移植関門は維持した。

B6当地の構造39と旗off200全量比較は完了。B5(b)はデスクトップの元同じ機械の全c4実関門待ち、B6八体20は未依頼・未走行。全体の候補929/e96/70dfは未受け入れ。指示12〜14/17/20/21/22/23は未完了・済みなし。指定デスクトップ原記録は未着、種4のassertは未確認。A94の旧関門と指示9〜11/15/16/18/19の済み、指示2/3/5/8とb/正式3b材料待ちを維持する。構造/模型/比較の重複起動なし。全旧停止/候補/一時資料/命令/出力と四つの禁止、10/13 09:00 JST期限を維持し、現在の自分のrunning/queuedは空。

保存：instruction22/23_status.json、instruction23/local_pass_on_stop_01、on200_stop_evidence_01、B6_after_end_01、resource_measurement_01、NEXT_SAVED_STEPS_03.md。公開証拠：control/2026-10-07_介入_新しい版の移植_Codex/{public_name}（{len(index)}資料＋全SHA索引）。通常pushの成否はinstruction23/report_delivery_03.jsonで確認する。今回の完了/停止/警告を次回ごとに新しい終了として知らせず、新番号付き指示も新しい自分の終了もない待機不変なら再計数/再登録/報告commit・push/予定更新をしない。
'''
# 圧縮受付の実PIDは保存された原ログからのみ取る。
import re
log=(here/'B6_after_end_01/clock_evidence_admission_01.log').read_text()
pid=re.search(r'受け付けた：PID (\d+)',log).group(1)
report_text=report_text.replace('受付72200前後の保存ログにある実PID',f'受付{pid}（0.3GB）')
rp=report/'control/2026-10-07_介入_新しい版の移植_Codex.md'
with rp.open('a') as f:f.write(report_text)
inbox=report/'control/受け箱/探索の腕と介入の係.md'
question=f'''

進行（{at}、control/2026-10-07_介入_新しい版の移植_Codex.md）。新旗off100の全16ファイル/26研究者辞書が比較03でpassed。B6同じ一本は20:45:35 JSTに自然終了0、必要200記録点検と保存929との全27名前/31項目が通過。動詞70dfの修正on・種1・τ0.4・先頭200は21:02:27 JSTに自然終了0、全ST/AUDIT・D記録の試験/cf前後不変と200行を確認。ただし保存94との比較は21:03:31 JST、retention/f0.5000_th2.1000_vt0.3842_first_order/seed001.jsonl.probe_checks.jsonの5行目before_sha256で停止。元の検査記録を除かず、最初の原値/全資料/通過六比較を保持し、τ0.15以降・比較再開・候補修正を止める。B5(b)/実八体と全体受け入れは待ち、済みなし。現在の自分のrunning/queuedは空。

問い（{at}、指示23の3の比較条件）。最初の差は上記の研究者の試験不変検査記録のbefore_sha256で、旧1cb59fb6a195b540d2784ef930a1847e2caddf40c28dcd8a9fa25785721c3870、新e70b46431482c07b67812e7704ed7c4e88284f8bb8a317780cbf3d5f0adc950aです。両側とも試験100/200ごとのbefore==afterとunchanged=trueは成立し、retention本体までの六比較は通過しました。同じ原probe_snapshotはD.ST/AUDITと記録口の名称/位置/原字節をreprへ入れますが、構成別の原字節が保存されていないため、SHA差の原因を名称だけと断定できません。元検査記録・全欄・原順・原出力・候補を保持し、不変条件も全量合格条件も減らさず、構成別の原字節を保存する限定診断と保存二本比較の扱いについて、この係の番号付き回答又はアストラの直接文面をお願いします。回答前に再比較・模型再走行・候補修正・τ0.15/種7/完走種照合を始めません。
'''
with inbox.open('a') as f:f.write(question)
print(json.dumps(dict(at_jst=at, public_evidence=str(public),public_file_count=len(index),
    b6_passed=True,on_tau04_comparison_stopped=True),ensure_ascii=False))
