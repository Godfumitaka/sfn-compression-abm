"""承認された継続確認の読み取りと報告。新しい模型・削除・停止を実行しない。"""
from pathlib import Path
from zoneinfo import ZoneInfo
import datetime,hashlib,json,re,shutil,subprocess,time
import admission_guard as guard

ROOT=Path(__file__).resolve().parent
REPO=ROOT/'report'
RUN=ROOT.parent/'codex_uposition_sme_2026-10-06/resume_01'
STEM='2026-10-07_介入_新しい版の移植_Codex'
PY='/opt/homebrew/bin/python3.12'

def run(args,**kw):
    return subprocess.run(args,check=True,**kw)

def report_link_exists(doc,link):
    path=doc.parent/link
    if path.exists():return True
    # sparse checkoutに展開されない資料も、保存されたGitの内容で存在を検査する。
    # 関門や模型の入力の不足にはこの代替を使わない。
    try:relative=path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:return False
    return subprocess.run(['git','cat-file','-e','HEAD:'+relative],cwd=REPO,
                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0

def without_counted_ancestors(rows, active, paused):
    """低RSSの受付・観測を挟んだ待つ親も、模型の子と二重計上しない。"""
    candidates=active|paused
    ancestors=set()
    for child in candidates:
        seen={child}
        parent=rows[child]['parent']
        while parent in rows and parent not in seen:
            seen.add(parent)
            if parent in candidates:ancestors.add(parent)
            parent=rows[parent]['parent']
    return active-ancestors, paused-ancestors, ancestors


def main():
    now=datetime.datetime.now(ZoneInfo('Asia/Tokyo'))
    assert now<datetime.datetime(2026,10,9,9,tzinfo=ZoneInfo('Asia/Tokyo')), '期限以後は新作業を始めない'
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=REPO,text=True).strip(),'変更を保持して停止'
    run(['git','pull','--quiet','--rebase','origin','results-2026-09-27'],cwd=REPO)
    refs=['control/受け箱/README.md','control/受け箱/探索の腕と介入の係.md','control/走行の列_2026-10-08.md','control/2026-10-06_SMEの一本の時間の内訳_Codex.md','control/2026-10-07_C星の照合とディリクレ_実装_Codex.md','control/2026-10-07_注意の第二段_実装_Codex2.md']
    texts={p:(REPO/p).read_text() for p in refs}
    sections=list(re.finditer(r'(?ms)^## 指示 (\d+)(.*?)(?=^## 指示 |\Z)',texts[refs[1]]))
    instruction_states=[{'number':int(m.group(1)),
                         'received':bool(re.search(r'(?m)^受領（',m.group(2))),
                         'completed':bool(re.search(r'(?m)^済み（',m.group(2))),
                         'held':bool(re.search(r'(?m)^保留：アストラの承認待ち',m.group(2)))}
                        for m in sections]
    pending=[m.group(0) for m,s in zip(sections,instruction_states) if not s['received']]
    ready=[p for p in texts[refs[2]].splitlines() if p.startswith('|') and '未着手' in p]
    if pending or ready:
        print(json.dumps({'review_before_continuing':True,'pending_instructions':pending,'eligible_rows_to_review':ready},ensure_ascii=False))
        return
    before=(ROOT/'heartbeat_sme_reference.sha256').read_text().strip()
    if hashlib.sha256((REPO/refs[3]).read_bytes()).hexdigest()!=before:
        print(json.dumps({'sme_report_changed_review_completion':True,'report_tail':'\n'.join(texts[refs[3]].splitlines()[-55:])},ensure_ascii=False))
        return
    now=datetime.datetime.now(ZoneInfo('Asia/Tokyo'));at=now.isoformat(timespec='seconds');stamp=now.strftime('%Y%m%d_%H%M%S')
    out=REPO/'control'/STEM/f'確認_{stamp}';out.mkdir()
    sme_review_path=ROOT/'heartbeat_sme_review.json'
    sme_review=json.loads(sme_review_path.read_text()) if sme_review_path.exists() else None
    if sme_review:
        assert sme_review['report_sha256']==before
        shutil.copyfile(sme_review_path,out/'25primeの完了確認.json')
    both_completed=bool(sme_review and sme_review.get('both_completed'))
    receipt_written=False
    if both_completed:
        policy=json.loads((ROOT/'admission_policy.json').read_text())
        if policy['active']:
            policy.update(active=False,released_at_jst=at,completion_report_sha256=before,
                          release_reason='指定報告の05:58:41の二本の完了・一致確認')
            (ROOT/'admission_policy.json').write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n')
            for _ in range(20):
                if json.loads((ROOT/'admission_status.json').read_text()).get('event')=='finished':break
                time.sleep(.1)
        if '済み（' not in texts[refs[1]]:
            with (REPO/refs[1]).open('a') as f:
                f.write(f'\n済み（{at}、control/{STEM}.md）。指定のSME時間内訳の05:58:35の動詞の報告と05:58:41の二本の完了・一致確認を確認。指示1の新規受付6本以下の条件だけを解除。全体8本の上限と、既存の模型の命令・旗・値・順番・関門を維持し、本番の停止・再起動は行っていない。\n')
            receipt_written=True
    limit=8 if both_completed else 6
    rows,active,paused=guard.census()
    active,paused,waiting_parents=without_counted_ancestors(rows,active,paused)
    def own(pid):
        seen=set()
        while pid in rows and pid not in seen:
            if pid==55602:return True
            seen.add(pid);pid=rows[pid]['parent']
        return False
    machine={'at_jst':at,'active':len(active),'paused':len(paused),'own_active':sum(own(p) for p in active),'own_paused':sum(own(p) for p in paused),'model_cap':8,'new_admission_limit':limit,'processes':[{'pid':p,'parent':rows[p]['parent'],'stat':rows[p]['stat'],'rss_kb':rows[p]['rss'],'own':own(p)} for p in sorted(active|paused)],'controllers':[{'pid':p,'stat':rows[p]['stat'],'command':rows[p]['command']} for p in sorted({55602,55730,40737}|waiting_parents) if p in rows]}
    machine['excluded_counted_ancestors']=[{'pid':p,'parent':rows[p]['parent'],'stat':rows[p]['stat'],'rss_kb':rows[p]['rss'],'command':rows[p]['command']} for p in sorted(waiting_parents)]
    machine['paused_non_model_processes']=[{'pid':p,'parent':row['parent'],'stat':row['stat'],'command':row['command']} for p,row in sorted(rows.items()) if row['stat'].startswith('T') and 'python' in row['command'].split()[0].lower() and p not in paused]
    state=json.loads((RUN/'pipeline_status.json').read_text());events=[json.loads(p) for p in (RUN/'pipeline_events.jsonl').read_text().splitlines()]
    old=json.loads((RUN/'priority25_01/withdrawal.json').read_text())
    hashes={k:hashlib.sha256((RUN/p).read_bytes()).hexdigest() for k,p in [('pipeline_sha256','pipeline.py'),('finalizer_sha256','finalize_when_done.py'),('native_command_sha256','gate_off/a/native_command.json')]}
    assert all(hashes[k]==old[k] for k in hashes),'命令又は監督の指紋が変わったので停止'
    proofs={}
    audits={}
    for mode in ('a','logp'):
        p=RUN/f'evidence/gate1_{mode}/gate1.json'
        if p.exists():
            shutil.copyfile(p,out/f'gate1_{mode}.json')
            v=json.loads(p.read_text());proofs[mode]={'passed':v['passed'],'files':len(v['files']),'all_files_equal':all(x['gate_equal'] for x in v['files']),'saved_state_lines':v['saved_state_lines'],'rng_trial_lines':v['rng_trial_lines']}
        p=RUN/f'evidence/gate4_5_{mode}/gate4_5.json'
        if p.exists():
            shutil.copyfile(p,out/f'gate4_5_{mode}.json')
            v=json.loads(p.read_text());audits[mode]={'passed':v['passed'],'trials':v['trials'],'seed':v['seed'],'visible_count':v['visible_count'],'disclosed_count':v['disclosed_count']}
    logpath=RUN/'pipeline_logs'/f'{state["stage"]}.log'
    tail='\n'.join(logpath.read_text().splitlines()[-30:]) if logpath.exists() else ''
    (out/'現在の受付又は実行ログ.txt').write_text(tail+'\n')
    registry=subprocess.check_output([PY,'/Users/tatsu-admin/jobs/jobs.py','status'],text=True)
    (out/'受付表.txt').write_text(registry)
    registered='\tCodex 位置U '+state['stage']+'\t' in registry
    waiting_swap='スワップの記録が直近 10 分ぶん無い' in tail and not registered and state['status']=='running'
    result={'at_jst':at,'results_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'automation_id':'10-9-9','unreceived':[],'received_pending':[1],'completed_now':[],'held_now':[],'eligible_rows':0,'sme25_completion_proved':False,'combined41_42_gates_proved':False,'new_interventions_started':False,'model_signals_sent':[],'new_models_started_by_this_check':0,'position_stage':state['stage'],'position_status':state['status'],'waiting_swap_history':waiting_swap,'gate1':proofs,'protected_sha256':hashes,'unchanged_before25':True,'references_sha256':{p:hashlib.sha256((REPO/p).read_bytes()).hexdigest() for p in refs}}
    result['position_gate4_5']=audits
    result.update(received_pending=[s['number'] for s in instruction_states if s['received'] and not s['completed']],
                  completed_instructions=[s['number'] for s in instruction_states if s['completed']],
                  held_instructions=[s['number'] for s in instruction_states if s['held']],
                  completed_now=[1] if receipt_written else [],sme25_completion_proved=both_completed,new_admission_limit=limit)
    for name,value in [('確認.json',result),('受け箱の状態.json',instruction_states),('機械の過程.json',machine),('位置Uの進行.json',state),('位置Uの経過.json',events),('受付条件の監督.json',json.loads((ROOT/'admission_status.json').read_text())),('終了報告の監督.json',json.loads((RUN/'finalizer_status.json').read_text()))]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    (out/'指紋.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()},ensure_ascii=False,indent=2)+'\n')
    base=f'{STEM}/確認_{stamp}'
    gate_desc=[]
    for mode,label in [('a','今の採点'),('logp','log P')]:
        if mode in proofs:
            p=proofs[mode];gate_desc.append(f'{label}の旗なし関門1は{p["files"]}ファイルで'+('一致' if p['passed'] else '不一致')+f'、保存状態{p["saved_state_lines"]}行、乱数{p["rng_trial_lines"]}行。[{label}の証拠]({base}/gate1_{mode}.json)。')
        else:gate_desc.append(f'{label}の関門1の完了証拠はまだ出ていない。')
        if mode in audits:
            p=audits[mode];gate_desc.append(f'{label}の位置Uの可視情報・会計は種{p["seed"]}の全{p["trials"]}試行で'+('通過' if p['passed'] else '不通過')+f'。[{label}の関門4・5の証拠]({base}/gate4_5_{mode}.json)。')
    wait_desc=('現段の受付は直近10分のスワップ記録不足で待機。記録不足を実際のスワップ増加と混同しない。比較はまだ開始しておらず、合格とは記載しない。受付・sampler・条件を変更せず、同じjobs.py run --waitで待つ。' if waiting_swap else '現段の状態をそのまま記録し、元の関門・受付を継続。')
    terminal=state['status'] in ('completed', 'failed', 'stopped')
    if terminal:
        wait_desc='既存pipelineは終了済み。記録を保持し、監督・模型・分類を再起動しない。'
    scientific_review_path=ROOT/'position38_review_status.json'
    scientific_review=json.loads(scientific_review_path.read_text()) if scientific_review_path.exists() else None
    result['position_review']=scientific_review
    if scientific_review:
        (out/'位置Uの集計確認.json').write_text(json.dumps(scientific_review,ensure_ascii=False,indent=2)+'\n')
    progress=' '.join(gate_desc)
    sme_note=('25′のお店1,740試行は04:49の報告で完了・一致確認まで確認した。動詞1,000試行の完了は未確認であり、二本の完了条件は満たしていない。[確認]('+base+'/25primeの完了確認.json)。' if sme_review and sme_review.get('shop_completed') and not sme_review.get('both_completed') else '')
    text=f'''\n\n### 継続確認：{at}\n\n取り込み `{result['results_commit']}`。未受領0件、取得可能な列の行0件。指示1は受領済み・未完了。25′の完了を指定の報告で確認していないため、新規受付6本以下の条件を継続。機械全体の模型・重い解析の稼働は{len(active)}本（自分{machine['own_active']}本）、SIGSTOP中は{len(paused)}本（自分{machine['own_paused']}本）。親・受付・resource_trackerを二重計上せず、小さいspawn/forkも含める。[機械の過程]({base}/機械の過程.json)、[受付表]({base}/受付表.txt)。\n\n38番は `{state['stage']}`、状態 `{state['status']}`。{progress}\n\n{wait_desc} pipeline・終了報告・native commandのSHA256は25′前の保存と同じ。模型への信号・重複起動・旗や順番の変更は今回行っていない。[進行]({base}/位置Uの進行.json)、[現在の受付又は実行ログ]({base}/現在の受付又は実行ログ.txt)。\n\n追加枠は空き（{at}）。{('38番の既存監督は終了済みで、再起動しない。' if terminal else '既存の38番の監督は継続。')}41/42の統合版の全関門合格を未確認のため、46番の移植後の解析は未着手。[確認と参照の指紋]({base}/確認.json)。\n'''
    if sme_note:text+='\n'+sme_note+'\n'
    if both_completed:
        text=text.replace('指示1は受領済み・未完了。25′の完了を指定の報告で確認していないため、新規受付6本以下の条件を継続。',
                          '指示1は済み。指定のSME時間内訳の05:58:35の動詞の完了と05:58:41の二本の完了・一致確認を確認し、6本以下の新規受付条件だけを解除。全体8本の上限と元の命令・旗・値・順番・関門は維持。')
        text+='\n[25′の完了根拠]('+base+'/25primeの完了確認.json)。軽い受付監督はpolicyのactive=falseを読んで終了し、模型の子へ信号を送っていない。[監督の終了状態]('+base+'/受付条件の監督.json)。受け箱の指示1へ済みを記録した。\n'
    statuses='、'.join(f'指示{s["number"]}は'+('済み' if s['completed'] else '保留' if s['held'] else '受領済み・未完了') for s in instruction_states)
    text+=f'\n今回の受け箱の状態：{statuses}。[受領・済み・保留の記録]({base}/受け箱の状態.json)。\n'
    report=REPO/'control'/f'{STEM}.md'
    with report.open('a') as f:f.write(text)
    pos=REPO/'control/2026-10-06_位置で条件づけたUの既定_SME版_Codex.md'
    with pos.open('a') as f:f.write(f'\n\n## 継続の中間確認：{at}\n\n{progress}\n\n現在は `{state["stage"]}`。{wait_desc} 元の命令・旗・値・順番と、gzipは展開後の全バイトで比べる関門を維持。[同時刻の受付・過程・経過の記録]({STEM}.md)。{('模型12本・分類12本は終了済み。日の集計の訂正の状態は介入報告と位置Uの末尾の追記を参照する。' if terminal else '今後のon関門と種1〜3の試しは、両採点の関門を通過した場合だけ既存の監督が進める。')}\n')
    # 位置Uの既存の添付は別のsparse checkoutにある。今回追加したリンクと、
    # この作業場所の介入報告のリンクを確認する。
    assert (pos.parent/f'{STEM}.md').exists()
    for doc in (report,):
        missing=[p for p in re.findall(r'\]\(([^)]+)\)',doc.read_text()) if not p.startswith(('https:','http:','#')) and not report_link_exists(doc,p)]
        assert not missing,missing
    files=[str(report.relative_to(REPO)),str(pos.relative_to(REPO)),str(out.relative_to(REPO))]
    if receipt_written:files.append(refs[1])
    run(['git','add','--',*files],cwd=REPO)
    run(['git','commit','-m',f'{at}の受け箱と位置Uの関門・受付待ちを記録'],cwd=REPO,stdout=subprocess.DEVNULL)
    for attempt in range(4):
        run(['git','pull','--quiet','--rebase','origin','results-2026-09-27'],cwd=REPO)
        pushed=subprocess.run(['git','push','origin','HEAD:results-2026-09-27'],cwd=REPO)
        if pushed.returncode==0:break
    else:raise RuntimeError('通常pushが通らなかった。強制pushはしない')
    result['published_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    (ROOT/'last_heartbeat.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'published':True,'at_jst':at,'commit':result['published_commit'],'active':len(active),'own_active':machine['own_active'],'gate1':proofs,'stage':state['stage'],'swap_history_wait':waiting_swap},ensure_ascii=False))

if __name__=='__main__':main()
