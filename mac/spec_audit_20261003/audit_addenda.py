from pathlib import Path
import re,json,csv
R=Path(__file__).parent; res=R.parent/'codex_worldv4_2026-10-01/results'; items=[]
for p in sorted((res/'docs/台帳').glob('*.md')):
 lines=p.read_text().splitlines(); section=''; declarations=[]
 for i,s in enumerate(lines,1):
  if s.startswith('## '):section=s
  m=re.search(r'\b([DCM]-(?:[A-Z])?\d+[a-z]?|M-xx)\b',s)
  start=bool(m and (s.startswith('#') or s.startswith('- '+m[1]) or s.startswith('**') or s.startswith(m[1]) or s.startswith('決定 M-xx')))
  if start:
   id=m[1]; title=s[m.end():].strip(' *★—−()：')
   declarations.append((i,id,title,section))
  elif s.startswith('確定 '):declarations.append((i,'未付番C@'+str(i),s.lstrip('確定 *★'),section))
  elif p.name.startswith('台帳追記_2026-09-19') and s.startswith('### ') and '## 4.' in section:declarations.append((i,'未付番C@'+str(i),s.lstrip('# *★'),section))
 for n,(line,id,title,sec) in enumerate(declarations):
  end=declarations[n+1][0]-1 if n+1<len(declarations) else len(lines)
  # 固有番号の範囲。撤回・未決の本文やs21の結果を検査本文に取り込まない。
  if p.name=='台帳追記_2026-09-25.md' and id in ['C-9','C-11']:
   body='';status='見つからない（対象外）';ev='s21の結果に関わる項目。種21〜40の記録は読まないため、結果の再照合は行わない。'
  else:
   body='\n'.join(lines[line-1:end]);status='見つからない';ev='過去の実測・解析・研究の段取りの条文。今回の本番の実行規則に対応する場所を特定しない。数の再検証・解釈はしない。'
  items.append(dict(document=str(p.relative_to(res)),line=line,id=id,rule=title,status=status,location='—',evidence=ev,body=body))
# Current executable clauses, explicitly scoped by document, rather than merging same numbers.
mapping={
('2026-09-25','D-18'):('tools/v39.py:650','不一致（Eで置換）','旧同定はlive。本番B＋Eは同定を止めて費用最小の候補を選ぶ。'),
('2026-09-25','D-19'):('tools/v39.py:437','一致','H/Uの席を現在の中身から埋める。Uは構造の照合に参加。'),
('2026-09-25','D-23'):('tools/v3_run.py:226; tools/v39.py:1042','不一致（後続B＋Eで置換）','nohashとvtは使用。θ′による誕生の刈り込みは本番では行わず、Eの費用で選ぶ。'),
('2026-09-25','D-24'):('tools/v39.py:759; tools/v39.py:1042','一致','子がない高階の行の扱いと最小2行。'),
('2026-09-25','D-31'):('tools/v31.py:162','不一致（D-36で変更）','profitの実装は残るが本番はnone。'),
('2026-09-25','D-32'):('tools/v31.py:78','一致（旧罰の実装）','B＋EのVはこの罰Qを使わない。'),
('2026-09-26','D-36'):('tools/v31.py:123','一致','本番のextend-rule none。'),
('2026-09-26','D-37'):('tools/v32.py:1; tools/v310be.py:345','不一致（Eで置換）','旧NSIMの3直しは旗として残る。本番ではEによる案の費用比較。'),
('2026-09-26','D-38'):('tools/fix2.py:1; tools/v39.py:289','一致','H履歴の子と可視／不可視の位置を分ける。Uと親子は後続strict-pc。'),
('2026-09-26','D-39'):('tools/v39.py:692','一致','proj-firstは投影を優先、投影がなければ穴埋めの曖昧さを判定。'),
('2026-09-26','D-40'):('tools/fixorder2.py:1','一致','構造の順で候補の整合を解く差し替え。'),
('2026-09-26','D-41'):('abm/definition.py:104','一致','見た名前は経験の相対頻度、未見だけlambda_mixを使う。'),
('2026-09-26','D-42'):('tools/v310be.py:459','不一致（Eで置換）','nsim 0.7は引数にあるが、B＋Eはこの閾値による同定を止める。'),
('2026-09-26','D-45'):('tools/fastledger.py:1; tools/nohist.py:1; tools/v3_run.py:338','一致（設定）','本番fastとno-public-historyを指定。今回の台帳の同一性比較の新走行はしていない。'),
('2026-09-26','D-49'):('tools/v3_run.py:418','一致（設定）','今回checksを指定しない。'),
('2026-09-26','D-50'):('tools/v3_run.py:603','一致（設定）','本番dump-slot-historyを指定。'),
('2026-09-27','D-57'):('tools/fillunseen.py:1; tools/fillnorestate.py:31','不一致（D-60で変更）','fill-unseenは現本番に入らない。'),
('2026-09-27','D-60'):('tools/fillnorestate.py:31; tools/v39.py:437','一致','元と同じ可視名の言い直しを抑え、他の名前が同じ物の組にあっても候補を消さない。'),
('2026-09-27','D-63'):('tools/fillnorestate.py:31','不一致（D-64で撤回）','現本番ではfill-visibleを指定しない。'),
('2026-09-27','D-64'):('tools/fillnorestate.py:31','一致（設定）','現本番のfill-norestate。'),
('2026-09-29_30','D-29b'):('tools/v39.py:363; tools/v39.py:789; tools/v39.py:870','一致（現行部分）','Hの頻度、使用Rだけ、初期評価、U覚え直し、Uを支持から除く、全U退役をS表に分けて確認。忘却の同点は後続D-30h。'),
('2026-09-29_30','D-29c'):('tools/v39.py:220','一致','時定数τの−0.5乗の重みを合計1へ正規化。'),
('2026-09-29_30','D-29d'):('—','見つからない（今回対象外）','旧Dの定義丸ごとの忘却。対象fe8d567のD-最小とは別方式。'),
('2026-09-29_30','D-29e'):('tools/v310be.py:172; tools/v310be.py:299; tools/v310be.py:345','一致（S13を除く）','V、K、取消を独立計算。引数の採点の小例はS13不一致。'),
('2026-09-29_30','D-29f'):('tools/histrole.py:49; tools/v310be.py:79; tools/v310be.py:116','一致（対応先の指定）','親の対応と同じ位置の子IDを控える。引数を含む費用判定はS13。'),
('2026-09-29_30','D-30d'):('tools/answerlog.py:91','見つからない（この版）','88e0e38の記録は候補の支持を控えるが、全候補の正答を再計算するこの三分類の列は見つからない。別のCodex解析・記録版の作業は対象88e0e38と分ける。'),
('2026-09-29_30','D-30e'):('tools/worldvariant.py:33','一致','二部分木の最初の葉の述語を同時に切り替え、既定p_A=.8。'),
('2026-09-29_30','D-30f'):('—','見つからない（対象版外）','集団化は対象88e0e38の実装に含まれない。集団化枝をこの監査で再走行しない。'),
('2026-09-30_午後','D-30h'):('tools/ustruct.py:1; tools/relearninit.py:57; tools/tiestruct.py:73; tools/v39.py:712','一致','本番の四つの旗の小例・実走行を確認。'),
('2026-09-30_午後','D-30i'):('tools/answerlog.py:91','一致','可視・不可視ID・対応なしと、名前一致を候補ごとに記録。'),
('2026-09-30_午後','D-30j'):('abm/accounting.py:71; tools/v39.py:220','一致','予定Tの3倍を最大時定数とする決定が明記。最小は.3。B＋E文書の固定5220より後の決定。'),
('2026-09-30_午後','D-30m'):('tools/probeworld.py:37','一致（保存・戻しの規則）','状態と部品の保存・戻しを行う診断。今回の旗なし対照は追加しない。'),
('2026-09-30夜_10-01','D-01a'):('tools/answergap.py:50; tools/answergap.py:92','一致','欠けたIDに対して候補を絞り、削った場合だけno_gap_candidate。'),
('2026-09-30夜_10-01','D-01b'):('tools/strictpc.py:111; tools/strictpc.py:288','一致','親子の直接対応、不可視の子、Uの型の検査を本番旗つき5＋7小例。'),
('2026-09-30夜_10-01','D-01c'):('tools/strictpc.py:263; tools/strictpc.py:302; tools/strictpc.py:347','一致','可視・開示された行で種類を控え、定義の照合・構造費用に反映。'),
('2026-09-30夜_10-01','D-01d'):('tools/shopworld.py:27; tools/shopworld.py:56','一致','M1/M2、T1最初の葉、sig_n/eとattach、既定例外.2、シール非伏せ。設定hide1。専用定義の小例3通過。'),
('2026-09-30夜_10-01','D-01e'):('tools/v3_run.py:439','一致','Eの値段をL50に固定。今回lambda0でもBの値段だけ0。'),
('2026-09-30夜_10-01','D-01f'):('tools/v310be.py:116; tools/cflearn.py:36; tools/useforget.py:150','一致（S13を除く）','A/C/DはS表に分けた。F保護はこの委任書の新走行で指定しない。'),
('2026-09-30夜_10-01','D-01g'):('—','一致（実行の範囲）','D混成としきい値二つのDの走行をしない。'),
('2026-10-01夕_10-02昼','D-02h'):('—','一致（実行の範囲）','開始前の余裕を確認、最大同時2本。他の重いPython0。'),
('2026-10-01夕_10-02昼','D-02i'):('—','一致（実行の範囲）','世界生成を変えず、引数が逆の手作りグラフの小例に限定。'),
}
for it in items:
 for (doc,id),val in mapping.items():
  if doc in it['document'] and id==it['id']:it['location'],it['status'],it['evidence']=val;break
 # Older measured constants are not predictions for a revised model.
 if 'M-xx'==it['id']:it['evidence']='番号未確定の研究・解析・実験の手順。今の本番の模型の一つの実行規則ではない。'
 # Requested current result records already compared in this turn.
 if '2026-09-29_30' in it['document'] and it['id']=='C-30k':it.update(location='abm/feedback.py:39; abm/loop.py:500',status='一致',evidence='f(agent,t)と実現値の記録。6本10440試行で独立照合の相違0。')
 if '2026-09-26' in it['document'] and it['id']=='C-5':it.update(location='tools/v39.py:548',status='一致（U除外後の規則）',evidence='支持比→F+H数→新しさ→名前、選択後の門。本番はUを分母から外す。')
 if '2026-09-20' in it['document'] and it['id']=='D-A4':it.update(location='abm/agent_runtime.py:189',status='一致',evidence='ceil(0.67×F+H)。S32。')
 if '2026-09-20' in it['document'] and it['id']=='D-A1':it.update(location='abm/domains.py:89; abm/accounting.py:269',status='一致（順序の記録・世界の採点）',evidence='引数順を保ち、世界の採点でtupleを比較。Aの役割採点で名前だけを比べる別の箇所はS13。')
# Verify that located files exist at one of the exact audited revisions.
source=R/'source'; extras={'tools/useforget.py':R/'useforget_fe8d567.txt'}
for it in items:
 for f,n in re.findall(r'([\w/]+\.py):(\d+)',it['location']):
  p=extras.get(f,source/f)
  if not p.exists():it['location']='—';it['status']='見つからない（部品の場所未取得）';break
  assert int(n)<=len(p.read_text().splitlines()),(f,n)
(R/'analysis/ledger_addenda_audit.json').write_text(json.dumps(items,ensure_ascii=False,indent=2)+'\n')
with (R/'analysis/ledger_addenda_audit.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=['document','line','id','rule','location','status','evidence']);w.writeheader();w.writerows({k:v for k,v in x.items() if k!='body'} for x in items)
md=['# 台帳追記13件の対応表\n\n取得元：results枝 2ed5cb97。番号は文書ごとに分ける。過去の実測・実験の段取りには、現版の実行規則の場所を無理に割り当てない。種21〜40の結果は再照合しない。\n\n']
for doc in dict.fromkeys(x['document'] for x in items):
 md+=['## '+Path(doc).name+'\n\n','| 行・番号 | 決まり／確定事項 | コード | 一致／不一致／見つからない | 根拠 |\n|---|---|---|---|---|\n']
 for x in [i for i in items if i['document']==doc]:
  cells=[str(x['line'])+'・'+x['id'],x['rule'],x['location'],x['status'],x['evidence']]
  md.append('| '+' | '.join(str(c).replace('|','&#124;') for c in cells)+' |\n')
 md.append('\n')
(R/'analysis/ledger_addenda_audit.md').write_text(''.join(md))
print(len(items),'declared clauses',sum(x['status'].startswith('一致') for x in items),'matches',sum(x['status'].startswith('不一致') for x in items),'old clause changes')
