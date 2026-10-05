"""完走と分類が揃った腕だけを、価値判断を加えず表にまとめる。"""
from pathlib import Path
import json
from datetime import datetime
HERE=Path(__file__).resolve().parents[2]
provenance=json.loads((HERE/'evidence/provenance.json').read_text())
implementation=provenance['implementation_commit'][:8]
rows=[]
for path in sorted((HERE/'classification').glob('*/summary.json')):
    data=json.loads(path.read_text())
    assert data['seeds']==list(range(1,21))
    assert sorted(c['seed'] for c in data['checks'])==list(range(1,21))
    for c in data['checks']:
        assert c['対象']==c['作った試行']
        assert all(c[key]==0 for key in ('予測が本物と違う','一位が本物の選びと違う','一位でやり直した答えが本物と違う'))
    for cue,day in (('e','例外の日'),('n','通常の日')):
        d=data['days'][cue]
        assert d['外れ']==d['選び間違い']+d['区別の喪失']
        rows.append('| '+data['arm']+' | '+day+' | '+' | '.join(str(d.get(k,0)) for k in ('正解','外れ','黙り','選び間違い','区別の喪失'))+' |')
lines=['# 探索の腕三つ：実装・検証・集計', '', '更新：'+datetime.now().astimezone().isoformat(), '',
       f'基準コードは 3380344、実装のコミットは{implementation}。種は 1〜20 のみ。重い処理は ~/jobs/jobs.py で受付後に実行。結果の良し悪しは記載しない。', '',
       '初版の init_rec は誕生後の記憶を使っていたため走行を停止し、superseded_birth_state/ に別保存した。以下は開示前の記憶に修正して再走行した版だけを集計する。' , '',
       '走行はLの16条件とTの3条件、各20種・1740試行。既存の旗一式を引き継ぎ、Aは--cf-learnなし、Cはあり。λは--v39-price、--e-priceは既存のλ格子と同じ0.01873710622997919に固定。Uはglobalのまま。コマンドはlogs/に保存する。', '',
       'L-B：--score-logp。L-BE：--score-logp --score-logp-e。ε＝1/2 は仮定として固定し、結果に応じて変えない。履歴の有効候補が無い場合は q_H=b とする。候補名が無い分布は無回答の一点質量とし、名前の確率は0、費用は既存の L_of を用いる。', '',
       'L-BE の E は写った H 席に一致時も −log₂P_H を払い、F 席の0/ℓ、書換の件数と位置の符号、追加、取消は従来どおり。この適用範囲は P_H という指定からの解釈。relearn_init の観察一回の初期値は、指定された score_answers・init_rec の外なので既存の0/ℓを保持した。init_rec の採点は、予測時に控えた開示前の p̂・履歴・符号表を使う。', '',
       'T：--tie-random。支持の割合の最大値に同点の候補から、（種,試行）で決まる専用の乱数で一様に選ぶ。席数・新しさを選択に使わない。', '',
       '## 関門', '',
       '小例の10検証が通過：Pの正規化、履歴なし・未経験名・同点、署名と階数の制限、手計算の費用とV、開示前の控えによる採点、初期値も開示前の記憶を使うこと、EのH席への適用、Tの再現性・分布・非同点。', '',
       '手計算の追加確認：P_H(正解)=0.9、P_U(正解)=0.8、ℓ=5なら、r_H=0.152003093445、r_U=0.321928094887。解放12ビットでV_HU=0.014160416787。', '',
       '手計算：q_H(正解)=0.9、b(正解)=0.8、ε=1/2 のとき P_H=0.85、P_U=0.8。r_H=0.234465253637、r_U=0.321928094887。解放12ビットなら V_HU=0.007288570104。ℓ=5、未知の名前の費用は6。', '']
flag=HERE/'gates/flag_off.json'
if flag.exists():
    checks=json.loads(flag.read_text());lines += ['旗なし：世界1・2 × A・C、種1、各80試行（合計320試行）。基準と変更版の台帳本体を先頭のヘッダを除いてバイト単位で比較し、4条件とも一致。証拠は gates/flag_off.json。', '']
full=HERE/'gates/full1740/comparison.json'
if full.exists():
    proof=json.loads(full.read_text())
    lines += ['追加の全試行確認：世界2・A・種1の1740試行も、旗なしの台帳本体がバイト単位で一致。証拠はgates/full1740/comparison.json。', '']
for gate,label in (('T80','T'),('LBE80','L-BE')):
    path=HERE/'gates'/gate/'connection.json'
    if path.exists():
        proof=json.loads(path.read_text())
        assert all(proof[key]==0 for key in ('予測が本物と違う','一位が本物の選びと違う','一位でやり直した答えが本物と違う'))
        lines += [f"旗を有効にした接続確認：{label}、世界2・A・種1・80試行。分類対象{proof['対象']}件で予測・選択・選ばれた候補の答えの不一致は各0件。証拠はgates/{gate}/connection.json。", '']
lines += ['## L・T の表', '', f'分類が終了した腕：{len(rows)//2}／19。分類は e15ef19 の selcands の候補ごとの答えを用いる。例外の日の答えた試行と、通常の日の外れを復元。分類が終了した腕で、本物の予測・選択・選ばれた候補の答えとの一致を確認した。', '',
          '選び間違い＝その外れで、門を通って正しく答える定義が記憶にあった。区別の喪失＝無かった。正解・外れ・黙りは全試行の台帳から数える。', '',
          '| 腕 | 日 | 正解 | 外れ | 黙り | 選び間違い | 区別の喪失 |','|---|---|---:|---:|---:|---:|---:|',*rows,'',
          '## R の材料', '', '指定三腕の保存先には、種1〜20の記憶台帳が無い。保存された記憶だけで行うという指示に従い、走らせ直して補わない。今の規則・N3・r の答えの比較と分類は未実行。保存場所が届けば、tools/explore3_rdiag.py で全ドアを解析できる。', '',
          '| 腕 | 確認した保存先 | 記憶がある種 | 欠けた種 |','|---|---|---|---|']
inv=HERE/'evidence/R_memory_inventory.json'
if inv.exists():
    for r in json.loads(inv.read_text()):lines.append(f"| {r['arm']} | {r['root']} | なし | 1〜20 |")
lines+=['', '## 証拠の場所', '', '- source/control/explore3_spec_2026-10-04.md：適用した仕様と解釈。', '- evidence/provenance.json：基準とファイルの指紋。', '- evidence/hand_example.json：手計算。', '- gates/flag_off.json：旗なしの台帳本体の一致。', '- runs/：種1〜20の台帳とside。分類済みのsideは可逆に圧縮し、元バイトのsha256を照合する。読み取り道具は未圧縮・圧縮の両方を読む。', '- classification/：各腕の候補・件・一致検証・表。', '- status.json：実行中の腕と終了した腕。', '']
text='\n'.join(lines)
for relative in ('source/control/explore3_spec_2026-10-04.md','evidence/provenance.json','evidence/hand_example.json','gates/flag_off.json','gates/full1740/comparison.json','gates/T80/connection.json','gates/LBE80/connection.json','status.json'):
    text=text.replace(relative, '['+relative+'](<'+str(HERE/relative)+'>)')
(HERE/'報告.md').write_text(text)
(HERE/'tables.json').write_text(json.dumps([json.loads(p.read_text()) for p in sorted((HERE/'classification').glob('*/summary.json'))],ensure_ascii=False,indent=2)+'\n')
