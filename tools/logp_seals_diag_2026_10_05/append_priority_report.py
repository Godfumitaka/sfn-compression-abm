"""手計算と量の先行報告。"""
from pathlib import Path
import json
import shutil

ROOT=Path(__file__).resolve().parent
NAME='2026-10-05_腕Lのシールと記憶の量_Codex'
d=json.loads((ROOT/'priority_summary.json').read_text())
p=ROOT/(NAME+'.md')
lines=['','## 段1完了と段2の先行表（2026-10-05 14時台）','',
       '五条件・100本の全件照合を終え、既報の10行×5項目がすべて一致した。誕生直後のシールの状態・名前・履歴も全件識別できた。入力のsha256も解析前後で一致。[段1の記録]('+NAME+'/stage1_summary.json)。段2を開始した。','',
       '### 2. 同じ誕生の三つの手計算','',
       'ε=1/2は固定した仮定であり、結果から変更していない。世界2のL-B・λ主・種1で、通常＋通常、誕生観察の履歴が `{sig_n:1}`、保持処理後にFが残る最初の三例（試行4・5・6、0始まり）を選んだ。','',
       'この走行の誕生採点では、確率の計算に渡す予測前の控えに、新しい定義Rの履歴がまだない。実装の空履歴規則 q_H=b により、P_H=P_U になる。`H答え`の記録は誕生の観察を含む状態から計算されてsig_nだが、対数費用の確率はその予測前の控えから計算される。Fの確率は (1+b)/2 である。','',
       '| 試行 | P_H(sig_n)=P_U(sig_n) | r_H=r_U | r_F | 旧材料の重み | R_H=R_U | R_F | ΔC_FH | λΔC_FH | V_FH | log P | 0/ℓ |',
       '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|']
for e in d['examples']:
    lines.append('| '+str(e['trial'])+' | '+' | '.join(f'{e[k]:.9f}' for k in ['P_H_sig_n','r_H','r_F','old_material_weight','R_H','R_F'])+f" | 3 | {e['lambda_dC_FH']:.9f} | {e['V_FH']:.9f} | F保持 | Uへ |")
lines+=['', 'R_s は旧材料の費用をACT-Rの16本の減衰重みで加え、今の材料を重み1で加えた値である。R_H−R_F は順に2.840122916・2.785054659・2.990833215で、λΔC_FH=0.056211319を上回りFが残る。記録のRF/RH/RU・Vと計算値は2×10⁻¹²以内で一致した。','',
        '同じ三つの誕生を0/ℓで計算すると、F/H/Uの答えはすべてsig_nで当たり、費用は0。ℓ=5、F→Hの解放量3、H→Uの解放量11で、どちらのVも0。λ>0なのでF→H、H→Uを経てUになる。対数採点でもH→Uの費用差はこの三例では0だが、先のF→Hが起きない。[手計算の全数値と識別子]('+NAME+'/hand_examples.csv)。','',
        '### 5. 最終記憶量と例外の日の外れ','',
        '世界2・保持A・全20種。各個体の1740試行終了時の総ビットを足し、平均も示す。記憶量の平均の順に並べた。','',
        '| 腕 | λ | 最終総ビット（20種合計） | 1種平均 | 例外の日の外れ（20種合計） |',
        '|---|---:|---:|---:|---:|']
for q in d['points']:
    lines.append('| '+q['arm']+' | '+str(q['lambda'])+' | '+str(q['bits_sum'] if q['available'] else '欠測')+' | '+str(q['bits_mean'] if q['available'] else '欠測')+' | '+str(q['exception_wrong'] if q['available'] else '欠測')+' |')
lines+=['', 'λ=0.065の比較点は全20種の記憶がないため欠測とした。L-Bは現在の支持割合、比較の注意材料はN3という選択規則の違いも含む。[比較表]('+NAME+'/final_memory_errors.csv)、[全個体の最終内訳]('+NAME+'/final_memory_per_seed.csv)、[入力パスとsha256]('+NAME+'/input_sha256.csv)。','',
        '残る1・3・4を集計中。L-Bの既存の候補記録では黙りが対象外だったため、その例外ドア212件は既存の分類手続きへ凍結記憶を渡して候補の答えだけを診断している。新しい模型の走行・学習・忘却は作らない。元の棄権の再現と入力の不変を検証する。']
if '## 段1完了と段2の先行表' not in p.read_text():p.write_text(p.read_text()+'\n'.join(lines)+'\n')
shutil.copyfile(ROOT/'stage1_summary.json',ROOT/'public/stage1_summary.json')
