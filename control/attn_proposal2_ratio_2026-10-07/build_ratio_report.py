"""五関門と全40種の完了後、案2′の指定表・診断・原記録を保存する。"""
from collections import Counter,defaultdict
import csv,gzip,json,math,shutil,statistics,subprocess
from datetime import datetime
from pathlib import Path
import sys
JOB=Path(__file__).resolve().parent;BASE=JOB.parent;SOURCE=BASE/'source'
sys.path.insert(0,str(SOURCE/'tools'))
from attnposition_input import fingerprint
from attnposition_diagnosis import write_csv
REPORT=BASE/'report';MAIN=REPORT/'control/2026-10-07_注意の腕_案2の診断と既定との比_Codex2.md'
OUT=REPORT/'control/attn_proposal2_ratio_2026-10-07'
SUMMARY=JOB/'summary';DIAG=JOB/'ratio_diagnostics/diagnostic_summary'
IDS=('baseline','global_e01','global_e05','position_e01','position_e05','global_fixed1','position_fixed1')

def rows(path):
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rt',encoding='utf-8') as f:return list(csv.DictReader(f))

def table(head,data):
    def cell(x):return '算出不能' if x is None or x=='' else str(x).replace('|','\\|').replace('\n',' ')
    return '\n| '+' | '.join(head)+' |\n| '+' | '.join(['---']*len(head))+' |\n'+''.join('| '+' | '.join(cell(x) for x in row)+' |\n' for row in data)+'\n'

def percent(x):return None if x=='' else f'{float(x)*100:.2f}%'
def link(name):return f'[{name}](attn_proposal2_ratio_2026-10-07/{name})'
def label(c):return {'baseline':'元N3','global_e01':'global η=.1','global_e05':'global η=.5',
 'position_e01':'position η=.1','position_e05':'position η=.5',
 'global_fixed1':'global a=1固定','position_fixed1':'position a=1固定'}[c]

def labelkey(key):
    paths,own=json.loads(key)
    routes=['上端' if not p else '→'.join(str(step[0][0])+':'+''.join('物' if x=='entity' else '関' for x in step[0][1])+'/'+str(step[1]) for step in p) for p in paths]
    return '{'+' / '.join(routes)+'} '+str(own[0])+':'+''.join('物' if x=='entity' else '関' for x in own[1])

def copy(path,name=None):
    dest=OUT/(name or path.name)
    if dest.exists():assert fingerprint(dest)['sha256']==fingerprint(path)['sha256']
    else:shutil.copy2(path,dest)

def main():
    marker=JOB/'ratio_report_built.json'
    if marker.exists():raise RuntimeError('案2比の報告を重複しない')
    gates=json.loads((JOB/'all_gates.json').read_text());assert gates['passed'] and gates['gate1_trials']==gates['gate5_trials']==69600
    check=json.loads((SUMMARY/'summary.check.json').read_text());assert check['passed'] and check['runs']==240 and check['trials']==69600 and check['unavailable_to_correct']==0
    dc=json.loads((DIAG/'diagnosis_summary.check.json').read_text());assert dc['passed'] and dc['trials']==69600
    assert json.loads((BASE/'ancestor_audit_2026-10-06/six_ancestor_checks.json').read_text())['passed']
    changed=rows(DIAG/'changed_pairs.csv.gz');healed=rows(DIAG/'healed_selection_errors.csv')
    damage=rows(SUMMARY/'normal_correct_transitions.csv');selection=rows(SUMMARY/'selection_error_destinations.csv')
    # 件別の診断と独立な回答表を照合する。回答の条件を緩めない。
    damage_counts=Counter((r['world'],r['condition'],r['outcome']) for r in changed if r['day']=='normal')
    for r in damage:
        assert int(r['correct_to_wrong'])==damage_counts[r['world'],r['condition'],'wrong']
        assert int(r['correct_to_abstain'])==damage_counts[r['world'],r['condition'],'abstain']
    healed_counts=Counter((r['condition'],r['baseline_seal_class']) for r in healed)
    for r in selection:
        if r['condition']!='baseline':assert int(r['correct'])==healed_counts[r['condition'],r['baseline_seal_class']]
    for r in changed:
        assert r['record_status']=='complete'
        for side in ('d0','d1'):
            assert sum(int(r[side+'_'+x]) for x in ('F','H','U'))==int(r[side+'_seats_total'])
            assert int(r[side+'_F'])+int(r[side+'_H'])==int(r[side+'_gate_FH_n'])
            exclusion=sum(int(v) for k,v in r.items() if k.startswith(side+'_excluded_'))
            assert int(r[side+'_m_counted'])+exclusion==int(r[side+'_seats_total'])
            assert int(r[side+'_U_counted'])==int(r[side+'_U_numeric_zero'])
            assert math.isclose(float(r[side+'_penalty']),float(r[side+'_penalty_seal'])+float(r[side+'_penalty_other']),abs_tol=1e-12,rel_tol=1e-12)
            assert float(r[side+'_z'])==float(r[side+'_ln_Q'])-float(r[side+'_penalty'])
            r[side+'_counted_non_U']=int(r[side+'_m_counted'])-int(r[side+'_U_counted'])
        r['d1_fewer_counted_non_U']=r['d1_counted_non_U']<r['d0_counted_non_U']
    OUT.mkdir(exist_ok=True)
    for p in SUMMARY.iterdir():
        if p.is_file():copy(p)
    ddir=OUT/'diagnostic';ddir.mkdir(exist_ok=True)
    for p in DIAG.iterdir():
        if p.is_file():shutil.copy2(p,ddir/p.name)
    write_csv(OUT/'diagnostic/changed_pairs_with_U_zero.csv.gz',changed)
    comparisons=Counter();excluded=Counter();proofs=[];manifest={}
    def remember(d):manifest[d['path']]=d
    for w in (1,2):
        for s in range(1,21):
            name=f'n3_w{w}_A_L50'
            for folder,kind in (('features','features'),('runs','replay')):
                p=JOB/folder/name/f'seed{s:03d}.{kind}.check.json';d=json.loads(p.read_text());assert d['passed'] and d['trials']==1740
                proofs.append({'kind':kind,**d});remember(fingerprint(p))
                for x in d['inputs']:remember(x)
                remember(d['output'])
                if kind=='features':
                    for r in d['baseline_comparisons']:comparisons[w,r['key'],r['state'],r['base'],r['changed']]+=r['seats_trials']
                    for r in d['old_baseline_unavailable_excluded']:excluded[w,r['key'],r['state'],r['reason']]+=r['seats_trials']
            p=JOB/'ratio_diagnostics/diagnosis'/name/f'seed{s:03d}.diagnosis.check.json';d=json.loads(p.read_text());assert d['passed'] and d['trials']==1740
            proofs.append({'kind':'diagnosis',**d});remember(fingerprint(p))
            for x in d['inputs']:remember(fingerprint(Path(x)))
    cr=[]
    for w,key,st,mode,ch in sorted(comparisons):
        cr.append({'world':w,'position_key':key,'state':st,'base':mode,'changed':ch,'seat_trials':comparisons[w,key,st,mode,ch]})
    write_csv(OUT/'base_comparison_by_position.csv',cr)
    er=[{'world':w,'position_key':k,'state':st,'reason':r,'old_base_unavailable_seat_trials':n}
        for (w,k,st,r),n in sorted(excluded.items(),key=lambda kv:str(kv[0]))]
    write_csv(OUT/'base_comparison_excluded.csv',er)
    with gzip.open(OUT/'all_seed_checks.jsonl.gz','wt',encoding='utf-8') as f:
        for d in proofs:f.write(json.dumps(d,ensure_ascii=False)+'\n')
    for d in check['inputs']+check['outputs']:remember(d)
    (OUT/'raw_records_manifest.json').write_text(json.dumps({'worlds':[1,2],'seeds':list(range(1,21)),
        'files':[manifest[k] for k in sorted(manifest)]},ensure_ascii=False,indent=2)+'\n')
    for name in ('all_gates.json','hand_gates.json','pre_result_ratio_decisions.json','machine_registered.jsonl'):
        copy(JOB/name)
    copy(JOB/'comparison_supervision/code_label_correction.json')
    machines=[]
    for folder in ('ratio_features_supervision','comparison_supervision','ratio_diagnostics/diagnosis_supervision'):
        copy(JOB/folder/'status.json',folder.replace('/','_')+'_status.json')
        for name in ('machine_registered.jsonl','commands.jsonl'):
            p=JOB/folder/name
            if p.exists():
                with p.open('rb') as src,gzip.open(OUT/(folder.replace('/','_')+'_'+name+'.gz'),'wb') as dst:shutil.copyfileobj(src,dst)
        machines.extend(json.loads(line) for line in (JOB/folder/'machine_registered.jsonl').open())
    machines.extend(json.loads(line) for line in (JOB/'machine_registered.jsonl').open())
    assert all(not m['thermal_warnings'] and not m['unregistered_heavy_python'] and m['swap_window_ok'] and m['disk_free_gib']>=18.5 for m in machines)
    pair=rows(DIAG/'changed_pair_summary.csv')
    extra=Counter()
    for r in changed:extra[r['world'],r['condition'],r['day']]+=r['d1_fewer_counted_non_U']
    final=rows(SUMMARY/'final_position_attention.csv');grouped=defaultdict(list)
    keys=sorted({r['position_key'] for r in final});mapping={key:f'P{i:02d}' for i,key in enumerate(keys,1)}
    write_csv(OUT/'position_key_index.csv',[{'label':mapping[k],'structure':labelkey(k),'position_key':k} for k in keys])
    for r in final:grouped[int(r['world']),r['condition'],r['position_key']].append(float(r['a_final']))
    tables_checked={'passed':True,'normal_damage_matches_changed_pairs':True,'selection_healers_match':True,
      'candidate_seat_accounting_matches':True,'all_valid_U_costs_zero':True,'z_identity_matches':True,
      'unavailable_to_correct':0,'changed_pairs':len(changed),'healed_records':len(healed)}
    (OUT/'table_checks.json').write_text(json.dumps(tables_checked,ensure_ascii=False,indent=2)+'\n')
    text=MAIN.read_text();text=text.replace('共通の基底への変更は承認済み。段2の前の六席の祖先点検は合格し、共通基底の案2′の関門を準備している。段2の成績は未計算。',
      '共通の基底への変更は承認済み。六席の祖先点検と案2′の五関門は全て合格。段2の両世界・種1〜20、六条件×40種＝240走行と指定の表・候補費用の事後診断を完了した。結果の良し悪しは判断していない。')
    text+='\n## 段2：共通基底の案2′の完了\n\n'
    text+=f'完了記録時刻：{datetime.now().astimezone().isoformat()}。五関門を通してから六条件の回答を計算した。関門1は両基底・全69,600試行の回答全欄の全バイト一致、関門5は全69,600試行の予測前の観察会計と、正解・型の差し替えによる特徴の不変。関門2〜4は上の三手例。全非ドア回答は元と一致（六条件で {check["non_door_identical_count"]:,} 件）。未開示試行のLはnullで、未開示の正解を読んでいない。開示されたドアだけで更新し、今の答えは更新前、次から更新後。a=1固定は学習しない。\n\n'
    text+='本人にドア課題の指示が伝わるという承認済みのheld_out_is_doorの仮定はそのまま。門と候補回答、記憶、既存の乱数は保存済みで変更していない。モデル・照合・記憶の走り直しは無し。globalの形は過去に見た名前と実開示の名前の記録、全体頻度は保存された予測前p_hatだけ。positionは同じ予測前の位置の表。共通基底は混ぜ・U・比の基準の三か所で同じ。以下で共通基底への変更と比への変更の効果を分離した比較とはしていない。\n\n'
    text+='コード：0db9e4c9（六席の原台帳点検）、87ed32b8（五関門と符号つき数値部品）、a0360dd0（六条件の比較と事後集計）。追加の符号・開示時点・共通基底の検査と既存N3・位置注意・診断の計37検査が合格。専用CLI：`tools/attnratio_features.py --base … --world 1|2 --seed 1..20 --output …/features`、`tools/attnratio_run.py --features … --world 1|2 --seed 1..20 --output …/runs --gate …/all_gates.json`、`tools/attnratio_summary.py --job … --output …/summary`、`tools/attnratio_diagnosis.py --base … --old-job … --world 1|2 --seed 1..20 --output …/ratio_diagnostics/diagnosis`。旧い案1・案2の動作を変える旗は追加していない。比較監督のコード表示に関門コミットを残した箇所は、実行コードa0360dd0との対応をcode_label_correction.jsonに記録した。計算中に数値コードは変更していない。\n\n'
    text+='### 条件・世界・日ごとの回答\n\n割合と種別は'+link('outcomes.csv')+'・'+link('outcomes_by_seed.csv')+'。店・日・正解は確定後の集計だけに使う。\n'
    daily=rows(SUMMARY/'outcomes.csv')
    text+=table(['世界','条件','日','全件','正解','外れ','黙り'],[[r['world'],label(r['condition']),r['day'],r['total'],r['correct'],r['wrong'],r['abstain']] for r in daily])
    text+='### 世界2の選び間違い136件と区別の喪失43件\n\n三分類は元N3の誤った候補のシールで固定した。\n'
    text+=table(['条件','元のシール','全件','正解へ','外れのまま','黙りへ'],[[label(r['condition']),r['baseline_seal_class'],r['total'],r['correct'],r['wrong'],r['abstain']] for r in selection])
    text+=table(['条件','区別の喪失の全件','正解へ','外れのまま','黙りへ'],[[label(r['condition']),r['total'],r['correct'],r['wrong'],r['abstain']] for r in rows(SUMMARY/'distinction_loss_destinations.csv')])
    text+='件別・種別：'+link('door_trials.csv.gz')+'、'+link('transitions_by_seed.csv')+'。正解候補が無い元の外れから正解に変わった件数は0。\n\n'
    text+='### 通常の日の元の正解と世界1の変化\n'
    text+=table(['世界','条件','元の正解','正解のまま','外れへ','黙りへ'],[[r['world'],label(r['condition']),r['baseline_correct_total'],r['correct_to_correct'],r['correct_to_wrong'],r['correct_to_abstain']] for r in damage])
    sums={c:{k:sum(int(r[k]) for r in daily if r['world']=='1' and r['condition']==c) for k in ('correct','wrong','abstain')} for c in IDS}
    text+=table(['世界1・条件','正解','外れ','黙り','元からの黙り件数差'],[[label(c),sums[c]['correct'],sums[c]['wrong'],sums[c]['abstain'],sums[c]['abstain']-sums['baseline']['abstain']] for c in IDS])
    text+='### 旧基底と共通基底の差\n\n次は旧案2で一意に対応して採点された席×ドア試行について、b(x)を浮動小数の保存値として比較した件数。除外席は旧bを計算しておらず、比較不能として別記する。位置別の全体：'+link('base_comparison_by_position.csv')+'、理由別の比較不能：'+link('base_comparison_excluded.csv')+'。\n'
    text+=table(['世界','席','基底','比較できた席×試行','b(x)が異なる','同じ','旧bが無い除外席×試行'],[
      [w,st,mode,sum(n for (ww,k,ss,b,ch),n in comparisons.items() if ww==w and ss==st and b==mode),
       sum(n for (ww,k,ss,b,ch),n in comparisons.items() if ww==w and ss==st and b==mode and ch),
       sum(n for (ww,k,ss,b,ch),n in comparisons.items() if ww==w and ss==st and b==mode and not ch),
       sum(n for (ww,k,ss,r),n in excluded.items() if ww==w and ss==st)]
      for w in (1,2) for st in ('F','H','U') for mode in ('global','position')])
    text+='### 案2′の変わった回答の候補・費用（段1の項目2・3）\n\n有効に対応してm′を計算した席を「対応席」と数える。Uは全て厳密に0なので、Uを除く対応席数も別記する。F/H/U、数値0、祖先欠落・鍵の重複・可視位置無し・ドアなどの除外、Σa·m′のシール／それ以外、lnQ・z・黙りの理由を件ごとに'+link('diagnostic/changed_pairs_with_U_zero.csv.gz')+'へ保存した。対象は通常の正解→外れ・黙りと例外の全回答変化。費用差の割合は符号つきの合計の比であり、0・負の分母の件数もCSVにある。\n'
    text+=table(['世界','条件','日','回答変化','d1の対応席が少ない','割合','d1のU除く対応席が少ない','費用差の非シール割合'],[
      [r['world'],label(r['condition']),r['day'],r['changed_trials'],r['d1_fewer_counted'],percent(r['d1_fewer_fraction']),
       extra[r['world'],r['condition'],r['day']],percent(r['nonseal_signed_fraction_of_sum'])] for r in pair])
    text+='全件の費用差・分母は'+link('diagnostic/changed_pair_summary.csv')+'。\n\n'
    kinds=rows(DIAG/'seat_kind_means.csv')
    text+=table(['世界','基底','席の種類','席×試行','平均m′'],[[r['world'],r['condition'].split('_')[0],r['seat_kind'],r['count'],None if r['m_mean']=='' else format(float(r['m_mean']),'.9g')] for r in kinds if r['condition'] in ('global_e01','position_e01')])
    text+='分母は全候補の有効な対応席×ドア試行。Uの平均は0、対応したF席は0件で平均は算出不能。同じ基底ではη・固定1でm′は同じ。全六条件と除外理由の会計は'+link('diagnostic/seat_kind_means.csv')+'・'+link('diagnostic/counted_and_excluded.csv')+'。\n\n'
    census=rows(DIAG/'missing_ancestor_denominators.csv')
    text+=table(['世界','条件','候補区分','全席×試行','祖先欠落の席×試行','割合'],[
       [r['world'],label(r['condition']),r['scope'],r['all_candidate_seat_trials'],r['missing_ancestor'],percent(r['missing_ancestor_fraction_all'])] for r in census])
    text+='分母はドアの席も含む全席。Q=0も含む全候補、選ばれた候補、門上の正解候補を分け、ドア除外後の分母も'+link('diagnostic/missing_ancestor_denominators.csv')+'に残した。selected_Rの空欄は採用定義R_usedの空欄であり、選びの一位と混同しない。一位と黙りの理由は'+link('diagnostic/blank_selected_R.csv.gz')+'に残す。U同点かH同点かの内訳は保存記録では不明のまま。\n\n'
    text+='### 最終の位置ごとのa\n\n世界・条件ごとに、記録種の平均aが大きい3位置を示す。同点は構造鍵順。全位置・全種は'+link('final_position_attention.csv')+'、位置の完全な鍵は'+link('position_key_index.csv')+'。道の各段の形と下りる引数番号を省かず表記する。固定1は学習無し。\n'
    tops=[]
    for w in (1,2):
        for c in IDS[1:]:
            vals=[(statistics.mean(v),k,min(v),max(v),len(v)) for (ww,cc,k),v in grouped.items() if ww==w and cc==c]
            for avg,k,lo,hi,n in sorted(vals,key=lambda r:(-r[0],r[1]))[:3]:tops.append([w,label(c),mapping[k]+' '+labelkey(k),format(avg,'.9g'),format(lo,'.9g'),format(hi,'.9g'),n])
    text+=table(['世界','条件','位置','平均a','最小','最大','記録種数'],tops)
    text+='### 会計・資源・原記録\n\n'
    text+=f'回答表と件別の診断で、通常の正解→外れ・黙りと136件の正解への移り先が一致した。全{len(changed):,}件で席数・除外・U=0・費用の内訳・zの会計を検算した。正解候補無し→正解は0件。全表の検算は'+link('table_checks.json')+'。L・実際のf・開示・更新理由・a_before/a_afterは毎試行の原side、種別の更新理由は'+link('updates_by_seed.csv')+'。P=0・逆転・鍵が一意でない件数は位置・状態・基底・条件・種別で'+link('position_audit_by_seed.csv.gz')+'に保存した。\n\n'
    text+=f'全計算はjobs.py run --wait、実出力先の--disk-path指定。特徴・比較・診断は種別0.3GB、回答集計と報告は0.5GB、診断集計は0.3GB。最大4種で、開始前・各重い計算前・実行中の空き容量は{min(m["disk_free_gib"] for m in machines):.2f}〜{max(m["disk_free_gib"] for m in machines):.2f}GiB、スワップ{min(m["swap_mb"] for m in machines):.2f}〜{max(m["swap_mb"] for m in machines):.2f}MBで増加無し。熱・性能警告無し、未登録の重いPython無し。空きの割合は各machine記録に保存。実測最大RSSは特徴{max(d["peak_rss_bytes"] for d in proofs if d["kind"]=="features")/1024**2:.2f}MiB、比較{max(d["peak_rss_bytes"] for d in proofs if d["kind"]=="replay")/1024**2:.2f}MiB、診断{max(d["peak_rss_bytes"] for d in proofs if d["kind"]=="diagnosis")/1024**2:.2f}MiB、回答集計{check["peak_rss_bytes"]/1024**2:.2f}MiB。\n\n'
    text+='原記録は'+link('raw_records_manifest.json')+'に、両世界・種1〜20の公開入力・保存候補・相対費用・毎試行の学習記録・ケース表の明示的パス、容量、sha256を列挙した。五関門・三手例・120件の種別合格書・資源の監督記録・CSVの表を同じ報告枝に保存した。保持への間接効果、全走行、記憶費用、本番値、10月8日の採否は調べていない。結果の良し悪しは書かない。段③、種21〜40、代替U黙るの腕には進んでいない。\n'
    MAIN.write_text(text)
    result={'complete':True,'time':datetime.now().astimezone().isoformat(),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip(),
      'main':fingerprint(MAIN),'table_checks':tables_checked,'stage2_runs':240,'phase3_started':False,'outputs':[fingerprint(p) for p in OUT.iterdir() if p.is_file()]}
    marker.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'complete':True,'table_checks':tables_checked,'runs':240},ensure_ascii=False))

if __name__=='__main__':main()
