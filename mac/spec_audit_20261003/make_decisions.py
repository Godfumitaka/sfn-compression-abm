import json,re
from pathlib import Path
R=Path(__file__).parent; rows=[]
def add(ns,id,rule,loc,status,evidence,doc=''):
 rows.append(dict(namespace=ns,id=id,rule=rule,location=loc,status=status,evidence=evidence,document=doc))
ns='9-28の予算判断（セッション内の番号）'
budget=[
('D-01','墓石も予算に含める','tools/v39.py:119; tools/v39.py:154','一致','H/Uの行を構造費用から外さない。'),
('D-02','曖昧化後も経験の偏りを保持し、定義群全体で節約を数える','tools/v39.py:98; tools/v39.py:163','一致','Hの名前と回数、全定義と全体表の費用。'),
('D-03','場面の記憶は定義群の予算と別枠','tools/v39.py:163; abm/agent_runtime.py:263','一致','total_bitsにprototypeを加えない。'),
('D-04','予算の価格を現在の経験から更新','tools/v39.py:71; tools/v39.py:894','一致','変換の試行でp̂からLを作る。Eは候補のループ前に凍結。'),
('D-05','複数の候補名は観察に基づく','abm/filling.py:266; tools/histrole.py:48','一致','履歴はvisible/revealedの観察。Uの全体既定値は履歴へ仮に足さない。'),
('D-06','現実的な更新から設計する','—','見つからない','設計の手順。特定の実行時規則としてのコード対応はない。'),
('D-07','経験を既存へ取り込めない場合を許す','tools/v310be.py:381; tools/v39.py:1042','一致','Eに新規案。共通部2行未満では新規が作られない。'),
('D-08','開示で確認された関係を確認実績に入れる','tools/v38.py:75; tools/v310be.py:116','一致（旧経路）','v38は述語と引数を照合。現在のB＋Eは別の席成績へ置換。引数の差はS13。'),
('D-09','未確認は加点・減点しない','tools/v38.py:99; tools/v310be.py:116','一致','v38の評価分母は充足・反証だけ。B＋Eの誕生後分は開示が対応する席だけ。'),
('D-10','開示された正しい穴埋めの席の観察を足す','tools/v38.py:151; tools/histrole.py:48','一致','v38はID由来の席を更新。hist-roleで他の席の観察も役割の対応を使う。'),
('D-11','使用定義内の確認できた不成立も評価','tools/v38.py:88; tools/v39.py:1027','不一致（後続方式で置換）','旧v38は反証を評価。B＋E・Aは開示IDの席だけに成績を加える（S14）、Cは最終回答で全非U席を評価（S21）。')]
for x in budget:add(ns,*x,doc='control/sfn_claude_handoff_2026-09-28.md:63; :356; :514')
other=[
('D-31','extend-rule noneは同化で行を足さない','tools/v31.py:123','一致','本番の指定はnone。profitの規則はtools/v31.py:162、今回は実行対象外。'),
('D-32','投影と穴埋めの誤答で罰の届け先を分ける','tools/v31.py:78','一致（旧経路）','D32処理は存在。本番B＋EのVはこの罰Qを足さない（S16）。'),
('D-38','Hの子の位置に可視名が履歴にあれば対にできる','tools/v39.py:289; tools/strictpc.py:111','一致','Hの候補と、strict-pcの親子の検査。模型層の本番旗つき7小例。'),
('D-59','二階も伏せ候補に入れる（仮決定の参照）','abm/world.py:236; abm/domains.py:182','一致（実装の条文）','設定holdout_include_second_order=true。決裁の台帳本文は未取得。')]
for x in other:add('後続の番号参照',*x,doc='docs/意図した変更_v3_v31.md／control/判断_0927_1630.md')
for id in ['D-25','D-27','D-28','D-41','D-48']:
 add('台帳本文未取得',id,'委任書に番号の参照がある','—','見つからない','確定事項の本文を取得していない。D-27は9-19委任書に「落とす」と記録、実行規則の原文は未取得。','委任書_2026-09-19_第4版.md:95; :187; :205; :223')
ms=[
('M-008','照合参加を通じてVが下がるという参照','abm/accounting.py:201','見つからない','全文なし。現在のB＋EはP・aを使わない。旧式は残る。'),
('M-011','比率Pは0から1','abm/accounting.py:138; tools/v38.py:68','一致（旧量）','同じ分子・分母の16列。B＋EのVはPを使わない。'),
('M-016','模型内部の意味論の一貫性','—','見つからない','B1:709の理由の参照だけで決定本文なし。'),
('M-030','課金時点のm_liveを凍結する','abm/loop.py:358; abm/definition.py:72','一致（旧量）','既存の課金額を後から再価格化しない。B＋EのVはQを使わない。'),
('M-040','m1の入力はprototypeと現在場面の整列','tools/v310be.py:467','一致','同定先とは別の元の材料から共通部を作る。'),
('M-041','同定閾値に届く定義なしなら新規','abm/abstraction.py:14; tools/v310be.py:345','不一致（後続Eで置換）','旧同定は存在。本番は閾値による同定をNoneにし、費用最小の案を選ぶ。'),
('M-042','高階優先・S2最大の核を上書きしたという参照','—','見つからない','B1:1093に変遷だけ。上書きした決定全文なし。'),
('M-051','①②の課金を同じ累積器へ','abm/loop.py:358; abm/definition.py:72','一致（旧量）','共通のExceptionAccumulator。本番のB＋EはQをVに使わない。'),
('M-058','旧種の6構成素の仮定でcを定める','abm/accounting.py:42; abm/abstraction.py:202','一致（旧量）','旧価格は残る。本番の定義費用は構造・履歴等の実際のビット。'),
('M-060','実際の可視先に写った行を充填しない','abm/filling.py:118; tools/v39.py:437','一致','可視の対応先を先に除く。欠けた位置はanswer-gapで追加制限。'),
('M-062','誕生のP初期値は上端1で≥.5','abm/accounting.py:80','一致（旧量）','二材料の同じ重みを分子と分母に初期化。B＋Eは別のRF/RH/RUを用いる。'),
('M-067','同定の走査は取り込み回数→新しさ','abm/abstraction.py:30; tools/v39.py:650','不一致（後続Eで置換）','旧経路の順は残る。Eはmin Kで同定し、同点に回数と新しさと名前を使う。'),
('M-068','予測のR_identifiedをm1の名前へ流用しない','tools/v310be.py:459; tools/v310be.py:467','一致','予測で使ったRからではなくEの候補で同化先を選ぶ。'),
('M-069','採択したR_used一本だけ功績を加算','abm/loop.py:240; tools/v39.py:1027','一致','他候補の席は誕生後の採点をしない。'),
('M-070','位置不明は分子0、分母+1、課金なし','tools/v38.py:99','不一致（D-09で置換）','D-09以降は未確認・不明の評価分母を増やさない。'),
('M-071','同じ位置に複数関係なら課金符号長の平均','abm/loop.py:311','一致（旧量）','ell_rの衝突の平均。本番B＋Eは開示した述語一つのℓで採点。'),
('M-018','R外使用を同じ古さの梯子で貯める','abm/accounting.py:119; abm/loop.py:198','一致（旧量）','ext_basisを同じ16列で減衰・加算。本番beta=0。'),
('M-020','外使用の分母は全試行−R適用','abm/accounting.py:184','一致（旧量）','total_opportunityからopportunity_basisを引く。B＋EのVでは使わない。')]
for x in ms:add('B1またはコードの決定参照',*x,doc='SPEC_B1_impl_2026-08-28.md／abm/accounting.py')
add('仮確定の参照','C-55','腕は設定パスと種ファイルの指紋で同定','abm/seed.py:39; tools/v3_run.py:465','一致（記録の対象）','種の指紋・設定・旗を保存。腕名だけで判定しない。','config/readings_2026-09-15.md:34')
add('仮確定の参照','C-82','旧fan_in_rawが0でκが効かない','abm/accounting.py:196; abm/abstraction.py:120','一致（旧量の初期化）','初期fan_in_raw=0。今回のB＋EのVにはembed項自体がない。旧走行の全件は再計数しない。','config/readings_2026-09-15.md:61')
add('コードの確定参照','C-33','高階述語の集合は種から計算し必須で渡す','abm/seed.py:58; abm/filling.py:135','一致','Noneを受け付けずコード定数で凍結しない。','abm/seed.py:64')
# 追記7は承認待ちの旧記録。実測値は今回の再検査と混同しない。
p=R/'source/台帳追記7 2026-09-03 rev4.md';lines=p.read_text().splitlines()
locs={1:'abm/abstraction.py:58',4:'abm/abstraction.py:161',6:'abm/loop.py:377',7:'abm/world.py:44',8:'abm/sme.py:364',9:'abm/accounting.py:201',12:'tools/strictpc.py:111',13:'abm/definition.py:23',14:'abm/abstraction.py:229',15:'sweep.py:304',16:'abm/accounting.py:262'}
for i in range(1,17):
 text=next(s.split('　',1)[1].strip('★ ') for s in lines if s.startswith(f'### C-{i}　'))
 st='見つからない';e='旧走行の実測・設計の記録。今回のコードだけからその過去の数は確定しない。'
 if i in (6,7,8,9,13,14,15):st='一致（旧経路の記述）';e='指定箇所に対応する旧処理が残る。本番のB＋E・strict-pcの差し替えはS表に別記。'
 if i==12:st='不一致（strict-pcで制限）';e='旧写像器の小例。今は可視の子の名前を親子の検査で調べる。strict-pc小例5件通過。'
 add('追記7 rev4：承認待ちの確定候補',f'C-{i}',text,locs.get(i,'—'),st,e,f'{p.name}:{next(j for j,s in enumerate(lines,1) if s.startswith(f"### C-{i}　"))}')
for i in range(1,8):
 text=next(s.split('|')[2].strip(' *★') for s in lines if s.startswith(f'| D-{i} |'))
 add('追記7 rev4：承認待ちの旧実験判断',f'D-{i}',text,'—','見つからない','段階の選び方・実験の配置・過去の設計判断。今の実行規則の単一のコード箇所に対応させない。',p.name+':177')
old=[
('D1','台帳write-only、研究者の真の世界をエージェントが読まない','abm/loop.py:48; abm/loop.py:500','一致','predictには部分場面を渡し、loopが台帳へappend。'),
('D2','照合のbaseは箱・入出力を変えない','abm/sme.py:1; tools/v39.py:345','一致（部品の接続）','map_graphsのbase/targetとAlignmentを使用。全文未取得。'),
('D3','ID・名前の辞書順を同点割りに使わないという抜粋','tools/v39.py:565; tools/v310be.py:391','不一致（後続仕様の同点順）','本番は名前を最後の鍵に明記する。tiestructは忘却の同点だけを構造化。前後の仕様を混同しない。'),
('D5','行は(slot_index,registered_at)、逐語の仮答えは研究者だけ','abm/definition.py:34; abm/loop.py:415','一致（旧欄）','B＋EのSeatRecはさらに世代番号で覚え直しを分離。'),
('D7','ID・名前の辞書順を同点割りに使わないという抜粋','tools/v39.py:565','不一致（後続仕様の同点順）','D3と同じ抜粋。現在の選択順はS30。'),
('D8','可視の不一致はfに無関係に②を発火','abm/loop.py:286','一致（旧経路）','本番no-charge2とB＋Eでは②をVへ加えない。'),
('D9','predictはAgentStateを変えない','abm/loop.py:81; tools/cflearn.py:90','一致','小例の本物の状態の指紋は不変。Cは照合後にも検査。'),
('D10','旧削除はV<θ′だけ','abm/accounting.py:256; tools/v39.py:894','不一致（後続Bで置換）','現B＋Eは変換V<λ、Dは使用S<τ。旧θ′による刈り込みを本番に使わない。'),
('D11','記憶の変異は登録・削除・統計の三種','—','見つからない','現在は履歴の役割観察・Uの覚え直し等を後続仕様で実行。元の全文の範囲未取得。'),
('D12','意味論の一貫性という理由の参照','—','見つからない','B1:709の理由だけで本文未取得。'),
('D13','p̂はエージェントごとに一つ','abm/domains.py:320; tools/v39.py:71','一致','同じstate.p_hatを回答と価格に使用。'),
('D14','設定値を名で渡し、走行長Tを明示する','sweep.py:46; abm/accounting.py:71','一致（取得した抜粋）','取得したD14の抜粋はT等を明示する規則。時定数の上端3Tの根拠は、新着の9-30午後D-30jに確認した。'),
('D23','台帳に再計算のための欄を必須とする','abm/ledger.py:1; abm/loop.py:500','一致（対象の記録）','実現f、種・世界の指紋と状態・旗を記録。6本の独立再計算の対象欄を照合。完全なD23本文未取得。')]
for x in old:add('B1のハイフンなし番号の抜粋',*x,doc='SPEC_B1_impl_2026-08-28.md:181; :1044; :1268')
# Exact line corrections for the main rule table.
a=json.loads((R/'analysis/audit_rows.json').read_text())
for r in a:
 if r['key']=='S29':r['location']='tools/v3_run.py:439'
 if r['key']=='S45':r['location']='tools/selectn3.py:34'
 if r['key']=='S46':r['location']='tools/selectn3.py:64; tools/selectn3.py:70'
 if r['key']=='S47':r['location']='tools/selectn3.py:113'
(R/'analysis/audit_rows.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')

fix={'D-05':'abm/filling.py:266; tools/histrole.py:49','D-10':'tools/v38.py:151; tools/histrole.py:49','M-030':'abm/loop.py:358; abm/definition.py:74','M-051':'abm/loop.py:358; abm/definition.py:74','M-058':'abm/accounting.py:42; abm/abstraction.py:177','C-55':'abm/seed.py:39; sweep.py:161; sweep.py:350','C-4':'abm/abstraction.py:192','C-14':'abm/abstraction.py:251','C-15':'sweep.py:316; sweep.py:379','D13':'abm/domains.py:254; tools/v39.py:71'}
for r in rows:
 if r['id'] in fix:r['location']=fix[r['id']]
(R/'analysis/decision_audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
ids=set(r['id'] for r in rows); refs=json.loads((R/'analysis/decision_references.json').read_text())
assert not(set(refs)-ids),(set(refs)-ids)
print(len(rows),len(refs),len(ids))
