import csv,json,re,collections
from pathlib import Path
from datetime import datetime
R=Path(__file__).parent; results=R.parent/'codex_worldv4_2026-10-01/results'; p=results/'control/2026-10-03_仕様と実装の照合_Codex.md'
def j(n):return json.loads((R/'analysis'/n).read_text())
def esc(s):return str(s).replace('|','&#124;').replace('\n',' ')
def loc(s,version='88e0e38'):
 def one(m):
  f,n=m.group(1),m.group(2)
  return f'[{f}:{n}](https://github.com/Godfumitaka/sfn-compression-abm/blob/{version}/{f}#L{n})'
 return re.sub(r'([\w/]+\.py):(\d+)',one,s)
def table(head,rows):
 return '\n'.join(['| '+' | '.join(head)+' |','|'+'|'.join('---' for _ in head)+'|']+['| '+' | '.join(esc(c) for c in row)+' |' for row in rows])+'\n\n'
receipt='\n'.join(p.read_text().splitlines()[:3])
s=[receipt+'\n\n',f'集計終了：{datetime.now().astimezone().isoformat(timespec="seconds")}。模型の修正なし。\n\n']
s.append('## 対象と用語\n\n')
s.append('Fは固定の名前と履歴を持つ席、Hは名前と回数の履歴だけを持つ席、Uは席の内容を忘れた状態。Bは忘却、Eは新規と同化（既存の定義へ取り込む）の費用の比較。A腕は問われた席自身の書き直し費用、C腕は席を薄くした写しの最終回答の書き直し費用で保持を評価する。\n\n')
s.append('ビットは記憶・書き直しの費用の単位。Vは席を薄くして増える書き直し費用を、空く記憶のビットで割った値。λは忘れる値段、`--e-price`はEだけの値段。L50＝0.01873710622997919、L90＝0.09900039055209096。\n\n')
s.append('支持の割合は、場面の照合に写ったF・H席数／F・H席数。門は発話を認める支持の条件。棄権は答えを言わなかった試行。時定数は古い観察の重みが減る速さを決める値。N3は名前・引数・親子の対応を定義と場面の大きさで割った選択の値。\n\n')
s.append(table(['対象','コード','範囲'],[
 ['本番','88e0e38bbd4f8ebbdc3f087de36801ce64a673e2','strict-pc-2026-10-01。新しい6本はこの版のA。'],
 ['shopdoor','da80915','tools/shopworld.py・道具の差し替え'],
 ['D-最小 use-forget','fe8d567','tools/useforget.py・既存の小例9件'],
 ['N3','3380344','n3-2026-10-02、tools/selectn3.py・既存の小例6件']]))
s.append('4版の`abm/`の木の指紋は同じ`d2918ac3d81cd7a3322364ab367abe95d2e26a98`。作業用の複製の`abm/`・`tools/`に88e0e38からの差分は0。種21〜40は読まず、再走行しない対称性の集計は種1〜20に限定した。\n\n')
s.append('## 取得した決定の範囲\n\n')
s.append('当初、リポジトリとcontrol/で見つかったハイフン付き番号は61種類。コードだけにある3番号と、B1のハイフンなし13番号を加え、77件の対応を表にした。`台帳追記7 2026-09-03 rev4.md`は「承認待ち」の文書であり、そのC番号は確定候補、そのD番号は旧実験判断として分けた。9-28のD-01等は文書に「このセッションの設計判断記録に付けた番号」と明記されている。ハイフンあり／なし・文書内の番号を同一の決定として統合しない。\n\n')
s.append('送信前の取得で、resultsの2ed5cb97に9-17〜10-02の台帳追記13件が届いた。これらに宣言された276条文（未付番の項目を含む）を文書ごとに分けて追加の表にした。[追加の全対応表](../mac/spec_audit_20261003/analysis/ledger_addenda_audit.md)・[CSV](../mac/spec_audit_20261003/analysis/ledger_addenda_audit.csv)。古い実測・実験手順・研究上の主張と、今の模型の実行規則を区別する。s21を対象にする結果の項目は再照合しない。古い番号の元の統合台帳と`sfn_budget_decisions_2026-09-28.md`そのものは未取得で、本文がない参照は見つからないと記録。全統合台帳の網羅を保証するとは記載しない。当初の番号参照の元の行は[decision_references.json](../mac/spec_audit_20261003/analysis/decision_references.json)に保存。\n\n')
s.append('## 委任書・現在の仕様とコード\n\n')
a=j('audit_rows.json')
s.append(table(['番号','決まり／出典','実装の場所','照合','根拠'],[[x['key'],x['rule']+'（'+x['spec']+'）',loc(x['location'],x['version']),x['status'],x['evidence']] for x in a]))
s.append('「一致」は表の条文と指定箇所の照合、または欄に記した検査の範囲。「旧経路」「後続方式で置換」は、旧条文と今の本番の旗を分けるための記載。\n\n')
s.append('### Aの役割による採点：引数が逆の小例\n\n')
s.append('固定の定義は`fold(x,y)`・`lock(x,y)`・`cause(r0,r1)`。可視場面は`lock(a,b)`と`cause(hid,s1)`、正解は`fold(b,a)`。本番の4直しと`--strict-pc --answer-gap`を適用した実際の予測を用いた。\n\n')
s.append(table(['量','結果'],[['支持','3/3'],['予測','fold(a,b)'],['正解','fold(b,a)'],['世界の採点','外れ'],['AのFの書き直し費用（仕様）','4ビット'],['AのFの書き直し費用（実装）','0ビット'],['Cの同じ実答の費用','4ビット'],['本物の記憶の指紋','Aの例の前後・Cの写しの再予測前後とも一致']]))
s.append('B＋E仕様§2・§6は名前と引数が一致したときだけ0ビット。`score_answers_role`は対応先IDを調べるが、その後の費用は述語だけを比較する（v310be.py:142）。位置一致の判定は統計`score_role_scored_pos_differs`だけに使う。小例の入力・対応・三答えは[role_args_example.json](../mac/spec_audit_20261003/analysis/role_args_example.json)、Cの写しの結果は[cf_args_example.json](../mac/spec_audit_20261003/analysis/cf_args_example.json)。これは手作りの引数が逆の小例であり、世界2の生成記録で起きた事例としては扱わない。コードは直していない。\n\n')
s.append('既存のマックの世界1・2、A/C、L50/L90の160本で、役割採点79,158席に対し`score_role_scored_pos_differs`は0件。今回の6本も0件。この統計の対象の位置不一致は0で、上の手作り例から本番の成績変化の数は算出していない。[走行別の確認](../mac/spec_audit_20261003/analysis/existing_role_score_checks.json)。\n\n')
s.append('### 古さの重みと走行長\n\n')
s.append('時定数は`τ_i=0.3×(3T/0.3)^(i/15)`（i＝0〜15）、減衰率は`exp(-1/τ_i)`。最小0.3はTによらず、最大3TのみTに正比例し、中間はT^(i/15)に比例する。T＝1740では最大5220、式にT＝3480を代入すると10440。長い走行は追加していない。\n\n')
s.append('B1の489行・891行に走行長Tの式があり、700行には同じ梯子の根拠としてU-001、892行にはTを明示するD14の参照がある。**後から届いた台帳追記_2026-09-30_午後.mdの21行（D-30j）に「時間の尺度は今のコードの決まり（予定試行数の3倍）が正」と明記されていた。実装はこの後続決定と一致する。** B＋E仕様§6は5220と固定して記載しており、今回のT＝1740では同じ式。古い文書の記載差をS37に残し、模型の不通としては数えない。\n\n')
s.append('### 決定番号ごとの表\n\n')
ds=j('decision_audit.json')
for ns,group in __import__('itertools').groupby(ds,key=lambda x:x['namespace']):
 s.append('#### '+ns+'\n\n')
 s.append(table(['番号','決まり／参照','場所','照合','根拠／参照元'],[[x['id'],x['rule'],loc(x['location']),x['status'],x['evidence']+' '+x['document']] for x in group]))
s.append('### 新着の台帳追記：現在の実行規則\n\n')
add=j('ledger_addenda_audit.json')
selected=[x for x in add if ('2026-09-29_30' in x['document'] or '2026-09-30_' in x['document'] or '2026-09-30夜' in x['document']) and x['id'].startswith('D-') and x['location']!='—']
s.append(table(['文書・行・番号','条文','コード','照合','根拠'],[[Path(x['document']).name+':'+str(x['line'])+' '+x['id'],x['rule'],loc(x['location'],'fe8d567' if 'useforget' in x['location'] else '88e0e38'),x['status'],x['evidence']] for x in selected]))
s.append('旧記録の参照D-25等と、新着文書の同じ番号は、出典を明示して別の行で照合した。D-30dの候補の全答えの再計算、D-30fの集団化、D-02eの原因分類は、対象88e0e38の模型そのものに含まれる処理と、別枝／研究者側の解析の処理を分けて記載した。今回その別枝を走らせ直していない。\n\n')
s.append('## 対称性：既存記録だけの集計\n\n')
s.append('全てデスクトップWSL側の種1〜20、各腕34,800試行から集計し、機械を混ぜていない。世界2のA/C×L50/L90はf格子のf＝0.5（88e0e38）、例外0.5のCはC格子（da80915）、世界1はN3の比較腕`now_w1_*`（3380344、`--select-n3`なし、`--select-log`あり）。世界1にA/C×両λがそろう同じ機械の記録を用いた。\n\n')
s.append('率の分母は該当する全課題（正解・外れ・棄権を含む）。差は甲−乙、または例外−通常。ppは百分率の差を表す単位で、1ppは1%の差。種ごとに同じ種の率を引き、その20値の平均、標本標準偏差SD（種の間のばらつき）、最小・最大を併記。範囲は観測された種の分布で、信頼区間とはしていない。\n\n')
s.append('種ごとの分子・分母・差と全体の分位点は[symmetry_by_seed.csv](../mac/spec_audit_20261003/analysis/symmetry_by_seed.csv)・[symmetry_summary.csv](../mac/spec_audit_20261003/analysis/symmetry_summary.csv)。入力の旗・コードは[symmetry_inputs.json](../mac/spec_audit_20261003/analysis/symmetry_inputs.json)。各入力は種1〜20だけ、試行0〜1739だけであることを確認した。\n\n')
ss=list(csv.DictReader((R/'analysis/symmetry_summary.csv').open()))
def num(x):return f'{float(x):.3f}'
def triple(arm,kind,group):
 rr={x['outcome']:x for x in ss if x['arm']==arm and x['kind']==kind}
 return [str(rr['c'][f'n{group}'])]+[str(rr[k][f'count{group}']) for k in ['c','w','a']]
rows=[]
for x in ss:
 if '/f_grid/' not in x['arm'] or x['outcome'] not in ('w','a'):continue
 arm=x['arm'].split('fg_f050_')[1];n0,n1=int(x['n0']),int(x['n1']);c0,c1=int(x['count0']),int(x['count1'])
 rows.append([arm,x['kind'],'外れ' if x['outcome']=='w' else '棄権',f'{c0}/{n0} ({100*c0/n0:.3f}%)',f'{c1}/{n1} ({100*c1/n1:.3f}%)',num(x['pooled_diff_pp']),num(x['paired_mean_pp'])+' ± '+num(x['paired_sd_pp']),num(x['min_pp'])+' 〜 '+num(x['max_pp'])])
s.append('### 世界2：甲と乙\n\n')
s.append(table(['腕','対象','結果','甲','乙','全体の差pp','種差の平均±SD pp','種差の最小〜最大pp'],rows))
s.append('### 世界2：C・例外割合0.5\n\n')
s.append('dはドアを問う位置へ選び直す確率。noneはその選び直しなし。\n\n')
rows=[]
for arm in dict.fromkeys(x['arm'] for x in ss if '/c_grid/' in x['arm']):
 for g in [0,1]:rows.append([arm.split('cg_C_')[1],'例外' if g==0 else '通常']+triple(arm,'例外割合0.5ドア' if '/c_grid/' in arm else '世界1ドア',g))
s.append(table(['腕（λ・d）','日','全ドア課題','正解','外れ','棄権'],rows))
rows=[]
for x in ss:
 if '/c_grid/' not in x['arm'] or x['outcome']!='w':continue
 rows.append([x['arm'].split('cg_C_')[1],num(x['pooled_diff_pp']),num(x['paired_mean_pp']),num(x['paired_sd_pp']),num(x['min_pp']),num(x['max_pp']),x['positive_seeds']+'/'+x['negative_seeds']+'/'+x['zero_seeds']])
s.append(table(['腕（λ・d）','外れの全体差pp','種差平均pp','SD pp','最小pp','最大pp','正／負／0の種数'],rows))
s.append('### 世界1：例外の日と通常の日のドア\n\n')
rows=[]
for arm in dict.fromkeys(x['arm'] for x in ss if '/n3/' in x['arm']):
 for g in [0,1]:rows.append([arm.split('now_w1_')[1],'例外' if g==0 else '通常']+triple(arm,'例外割合0.5ドア' if '/c_grid/' in arm else '世界1ドア',g))
s.append(table(['腕','日','全ドア課題','正解','外れ','棄権'],rows))
rows=[]
for x in ss:
 if '/n3/' not in x['arm'] or x['outcome'] not in ('w','a'):continue
 rows.append([x['arm'].split('now_w1_')[1],'外れ' if x['outcome']=='w' else '棄権',num(x['pooled_diff_pp']),num(x['paired_mean_pp']),num(x['paired_sd_pp']),num(x['min_pp']),num(x['max_pp']),x['positive_seeds']+'/'+x['negative_seeds']+'/'+x['zero_seeds']])
s.append(table(['腕','結果','全体差pp','種差平均pp','SD pp','最小pp','最大pp','正／負／0の種数'],rows))
s.append('世界1の棄権率の例外−通常の全体差は、A L50＝4.784pp、A L90＝10.961pp、C L50＝6.682pp、C L90＝11.669pp。対応する種差SDは4.697・7.813・7.474・7.977pp。正解・外れ・棄権の計数と種の分布を上表に記録した。\n\n')
s.append('## 極端な値：世界2・A・種1〜2\n\n')
s.append('1本1740試行、3条件×2種＝6本。忘れる値段以外のEの値段はL50。f0の条件だけ開示確率を0、それ以外f＝0.5。例外0の条件以外の例外割合は0.2。`--cf-learn --use-forget --select-n3`はいずれもなし。本番のB＋E・4直し・`--dump-answers --dump-routing --answer-gap --strict-pc --cf-value --probe-world`を用いた。正確な引数・設定を添付。\n\n')
e=j('extremes_summary.json')
s.append(table(['条件','種','試行','正解','外れ','棄権','開示','誕生後採点席','F→H','H→U','最大U席数','例外場面'],[[x[k] for k in ['mode','seed','trials','correct','wrong','abstain','disclosed','scored_seats','FH','HU','U_max','exception_scenes']] for x in e]))
s.append(table(['条件','検査','結果'],[['lambda0','Uの席が生まれないか','2本とも最大U数0、F→H 0・H→U 0'],['f0','開示からの学習・席採点がないか','開示0、Feedbackの開示内容0、誕生後採点0（3480試行）'],['exc0','例外の場面・sig_eがないか','例外場面0、真の世界全体の関係にsig_e 0（3480試行）']]))
s.append('f＝0でも可視場面からの学習は行う。種1・2の誕生は131・125件、初期値を与えた席は2007・1965、覚え直しの初期評価は1556・1644件。開示に基づく誕生後の採点0とは別の量。[初期評価の小例](../mac/spec_audit_20261003/analysis/extremes_examples.json)。\n\n')
s.append('例外0では真の世界を同じ種・旗で作り直し、全試行の世界の指紋と一致した。`--probe-world`が固定で問う例外の試験は実際の学習場面に数えない。三条件の上表の検査で、予想と異なる試行は0。λ＝0で常にUがないという一般命題にはせず、この2本の結果を記録した。\n\n')
c=j('independent_checks.json');by=collections.defaultdict(lambda:[0,0])
for x in c:by[x['check']][0]+=x['n'];by[x['check']][1]+=x['mismatches']
s.append('### 記録からの独立計算\n\n')
s.append(table(['検査','対象数','相違'],[[k]+v for k,v in by.items()]))
s.append('Eは保存されたA・書換／追加／取消の内訳・ΔCからKを独立計算し、採用した案の記憶の実増分とも比べた。台帳の丸められたA/Kだけは絶対差1.01×10⁻⁶以内、未丸めのΔCは同値で照合。Vは保存されたRF/RH/RUと解放量から数え直し、採用された全変換でV<λを確認した。誕生初期分と誕生後分は別に扱った。fは各試行の実値とcoinの比較を数え直した。[全検査の記録](../mac/spec_audit_20261003/analysis/independent_checks.json)。\n\n')
s.append('### 小さな例と既存の検査\n\n')
s.append(table(['対象','通過数','範囲'],[['旧V39の席・費用等','32/32','uniform・actr各16関数。B＋Eの実走行検査とは分ける。'],['候補ごとの曖昧さ','6/6','既存の小例'],['D-最小','9/9','fe8d567の小例。既存の試験の出力先だけ自分の場所へ変更。'],['N3','6/6','3380344の小例。手作りグラフの並び替えであり長い走行なし。'],['お店の専用定義・F/H名照合','3/3','世界生成の種は1。記録だけの2項目は通過数に入れない。'],['strict-pc','5/5','4直しの旗を適用した小例'],['模型の層','7/7','4直しの旗を適用した小例'],['Cの引数違いと写し','通過','3席のF/H/Uとも誤答として4ビット。6再予測、本物の記憶不変。']]))
s.append('pytestはPython3.12.13の環境に無く、追加インストールせず、既存のassert付き試験関数を直接実行した。模型の層の初回は4直しの環境設定なしでU例が不通だった。本番の`u_struct,relearn_init,tie_struct,amb_local`を設定した再検査は7/7。初回の記録も保存した。\n\n')
s.append('## 機械の余裕と保存\n\n')
s.append('開始前10:08 JSTの空き63.245GiB、スワップ使用965.50MiB、他のPythonの重い処理0、熱・性能の警告なし。走行は同時2本、条件は順に実行。3条件の2本ずつの経過時間は103.128秒・59.036秒・109.754秒。完了後の確認はスワップ949.50MiB、熱・性能の警告なし、走行中のPython0。途中の観測での常駐値はlambda0約102MB、f0約114MB。全期間の最大値を測った値とはしていない。\n\n')
s.append('台帳6本を残し、見出しの1行目を除いた本体のSHA-256（内容が同じか確かめる指紋）を[ledger_manifest.json](../mac/spec_audit_20261003/analysis/ledger_manifest.json)・[extremes_summary.json](../mac/spec_audit_20261003/analysis/extremes_summary.json)に保存。台帳の複製は`mac/spec_audit_20261003/extremes/`、元の全記録は自分の作業場所`codex_spec_audit_2026-10-03/runs/`に残す。削除なし。\n\n')
s.append('結果の解析と表は[mac/spec_audit_20261003/analysis/](../mac/spec_audit_20261003/analysis/)、再集計の道具・設定・実行ログも同じ場所に保存。模型の本番枝への直しなし。\n')
p.write_text(''.join(s))
print(p,len(p.read_text()),'chars')
