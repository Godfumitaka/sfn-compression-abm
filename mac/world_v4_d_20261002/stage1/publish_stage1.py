"""関門の三点と、仕様確認で止まる理由をcontrolへ保存する。"""
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT.parent/'codex_worldv4_2026-10-01/results'
REPORT=RESULTS/'control/2026-10-02_世界v4の確かめとD_Codex.md'
DEST=RESULTS/'mac/world_v4_d_20261002/stage1'
small=json.loads((ROOT/'stage1/small_examples.json').read_text())
binding=json.loads((ROOT/'stage1/binding_counts.json').read_text())
example=json.loads((ROOT/'stage1/classification_overlap_example.json').read_text())
assert small['point1_passed'] and small['point2_passed'] and binding['point3_passed']
assert not DEST.exists()
DEST.mkdir(parents=True)
for p in sorted((ROOT/'stage1').glob('*.json')):
    shutil.copyfile(p,DEST/p.name)
for name in ('stage1_examples.py','stage1_classification_example.py','publish_stage1.py'):
    shutil.copyfile(ROOT/name,DEST/name)
code=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT/'source',text=True).strip()
diff=subprocess.check_output(['git','diff','88e0e38',code,'--','abm/'],cwd=ROOT/'source',text=True)
assert not diff
scope={'code':code,'base':'88e0e38','branch':'codex/world-v4-d-2026-10-02',
       'python':'3.12.13','new_world_runs':0,'manual_prediction_examples':17,
       'previous_run_seeds':list(range(1,21)),'previous_runs':180,'previous_tasks':313200,
       'gate1_passed':True,'point4_pending_specification':True,'stage2_started':False,
       'abm_diff':False}
(DEST/'scope.json').write_text(json.dumps(scope,ensure_ascii=False,indent=1)+'\n')
lines=['\n## 段1：世界v4の動作確認\n',
       '保存時刻：'+datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')+'。土台strict-pc-2026-10-01の先頭88e0e38に、10月1日の世界v4の復元と履歴キーの解析修正を重ねた。コード '+code+'。Python3.12.13。自分の新しい作業場所 '+str(ROOT)+'。abm/の差分0。新しい世界の走行0。',
       '',
       'Fは固定名を持つ席、Hは名前と回数の履歴を持つ席、Uはその中身を忘れた席。支持の割合は、名前の残るF・Hの席のうち、場面の対応が取れた席の割合。',
       '',
       '| 点 | 確認の件数 | 結果 |', '|---|---|---|',
       '| 1 専用の定義 | 4型×2変種×伏せる葉2位置＝16例 | 正解16、誤答0、棄権0。正しい型・変種の定義の選択16 |',
       '| 2 他方の葉が見分けの手がかり | 同じ16例 | 全例で正しい専用定義の支持15/15、反対の変種の定義11/15。割合に差がある16例 |',
       '| 3 欠けた位置への結びつき | 10月1日の9腕×種1〜20＝180本、313200課題 | 誤答1986。対応先(i)伏せた関係1986、(ii)見えている関係0、(iii)対応先なし0 |',
       '| 4 外れの種類を分ける | 現行の予測による重なりの小例1件 | 分類の扱いと専用定義の判定基準が未指定。集計を保留 |',
       '',
       '1・2・3から、指定された関門1は通過。(i)以外の誤答は0/1986＝0%（基準10%以下）。',
       '',
       '### 1・2の小例',
       '',
       '型の木の骨組みを手で関係グラフへ置き、型×変種の8本の専用定義を保持させた。各定義は15席すべてF。物の名前・関係IDは定義と質問の場面で別。二つの切り替わる葉の一方を伏せ、他方を見せた。周縁の関係は足していない。現在の照合・定義選択・投影／穴埋め・--answer-gap・--strict-pcで予測し、その後で正誤を比較。予測に正解や型・変種の印を渡していない。全16例で予測前後の状態の指紋が一致。',
       '',
       '| 型 | 変種 | 伏せる部分木 | 正解と予測 | 選ばれた専用定義の支持 | 反対の変種の支持 |',
       '|---|---|---:|---|---|---|']
for c in small['cases']:
    lines.append(f"| {c['motif']} | {c['variant']} | {c['hidden_subtree']} | {c['prediction']['predicate']} | 15/15 | 11/15 |")
lines += ['', '### 3の腕ごとの数', '',
          '| 腕 | 試行 | 誤答 | (i)伏せた関係 | (ii)見えている関係 | (iii)対応先なし |',
          '|---|---:|---:|---:|---:|---:|']
for a in binding['arms']:
    n=a['total']
    lines.append(f"| {a['arm']} | {n['tasks']} | {n['wrong']} | {n.get('held_out',0)} | {n.get('visible',0)} | {n.get('none',0)} |")
lines += ['',
          '既存の試行別表 analysis/<腕>/seed<種>/trials.csv.gz を再集計した。表中の対応先は、前回に台帳の予測直前の状態と世界を復元し、実際の採点・回答の記録と突き合わせたもの。180本を走らせ直していない。腕と種ごとの数もbinding_counts.jsonに保存。',
          '', '## 仕様の確認で停止（段1の4）', '',
          '委任書の「仕様に無い判断は、決めずに小さな例と一緒に書いて止まる」に従い、以下を決めずに停止。段2のDの載せ直し・旗切りの検査・本番走行は未開始。',
          '',
          '小例：M1・変種Bの専用定義の二つの切り替わる葉だけをUにした。一方の葉hold_bを伏せ、他方のbreak_bを見せた。残る13席はF。定義の支持は13/13＝1。現在の予測はUからholdを答え、hold_bに対して誤答になった。予測前後の状態は同じ。',
          'この一件は「変種を見分ける席がU」と「忘れた席の既定値による外れ」の両方の条件に入る。重なりを残して複数該当を数えるか、どちらかを先に分けて一分類にするかは本文に指定がない。',
          '',
          '専用の定義の判定：同じ小例の定義は、作ったときは変種Bの専用定義だったが、現在は切り替わる名前を二つとも忘れている。現在の席の中身を判定に使うか、出生時の型・変種を判定に使うかで「専用の定義がある」の件数が変わる。現在はHでA・B両方の名を覚える場合もあり、その場合の専用性の基準も未指定。',
          '',
          '確認事項：①三分類の重なりを複数該当として別にも数えるか、優先順を決めるか。②「正しい専用の定義」「変種の区別を持つ定義」を、現在の席の中身と出生時の型・変種のどちらで判定するか。',
          '',
          '保存先：mac/world_v4_d_20261002/stage1/。全16例の提示・予測・全候補の支持、三点目の腕・種ごとの数、分類の重なりの小例、実行した解析のコード、コードの指紋と範囲を保存。既存の台帳は全て保持。種21〜40は解析していない。Dと門の曲線は未計測。']
with REPORT.open('a') as f:f.write('\n'.join(lines)+'\n')
records=[{'path':str(p.relative_to(DEST)),'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
         for p in sorted(DEST.iterdir()) if p.is_file()]
(DEST/'files.json').write_text(json.dumps(records,ensure_ascii=False,indent=1)+'\n')
print(json.dumps(scope,ensure_ascii=False))
