"""完了した記録集計を、指定された報告に追記する。"""
from collections import Counter
import csv
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
NAME='2026-10-05_腕Lのシールと記憶の量_Codex'
SRC=ROOT.parent/'codex_explore3_2026-10-04/source'
P=ROOT/'public'

def read(name):
    with (P/name).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

def link(name,title):return f'[{title}]({NAME}/{name})'

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
                     ['| '+' | '.join(str(x) for x in r)+' |' for r in rows])

def label(a):
    if a=='n3_w2_A_L50':return 'N3・世界2・λ主'
    if a=='n3_w1_A_L50':return 'N3・世界1・λ主'
    return 'L-B・世界'+('2' if 'w2' in a else '1')+'・'+('λ=0.065' if a.endswith('0.065') else 'λ主')

def main():
    q=json.loads((ROOT/'aggregate_summary.json').read_text());assert q['stage2_pass']
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SRC,text=True).strip()
    out=[]
    out.append('## 段2全項目完了（2026-10-05）\n')
    out.append('五条件×20種の保存記録から、誕生9518件、例外の日のドア3060件、記憶400時点を集計した。段1の既報との全セル一致、記憶量のsideとの全件一致、先行表の最終100時点との一致を確認した。種21〜40は開かず、模型の再走行は行っていない。模型・照合・既存分類のファイルは変更していない。'+link('aggregate_summary.json','完了の検証記録')+'。\n')
    out.append('λ主は0.01873710622997919、保持はすべてA、ε=1/2は固定の仮定。比較材料のλ=0.065は全20種の記憶がなく欠測とした。L-Bの選び方は現在の支持割合、比較材料の選び方はN3なので、この比較には採点と選択規則の両方の違いがある。\n')
    gate=read('stage1_counts.csv')
    out.append('### 段1の全件一致\n')
    out.append(table(['腕','日','正解','外れ','黙り','選び間違い','区別の喪失'],
                     [[label(r['arm']),'例外' if r['day']=='e' else '通常',*[r[k] for k in ('正解','外れ','黙り','選び間違い','区別の喪失')]] for r in gate])+'\n')
    out.append(link('stage1_counts.csv','全セルのCSV')+'。誕生は全9518件で材料の試行と保持直後の記憶が結べた。同じ試行の定義全体の退役は0件。採点関数を返した直後の初期状態は、シールの席が作られたものではFである。以下の「誕生の状態」は、その試行の保持の変換を終えた状態を指す。件別CSVにはこの二時点を別欄に記録した。\n')
    out.append('### 1. 材料の日と誕生のシール\n')
    births=read('birth_summary.csv')
    day={'n+n':'通常＋通常','e+e':'例外＋例外','e+n':'混在'}
    out.append(table(['腕','材料の日','F','H','U','シール席なし','複数','誕生総数'],
                     [[label(r['arm']),day[r['material_days']],*[r[k] for k in ('F','H','U','席なし','複数','total')]] for r in births])+'\n')
    out.append('二材料の日はsideのbase_written_atと台帳のshop_cueから読む。異なる名前から共通部分を作り、シールの席自体を持たない定義も全誕生の分母に含める。'+link('birth_counts_per_seed.csv','腕・世界・λ・種別の件数（ゼロ件も含む）')+'、'+link('birth_records.csv','全誕生の試行・F/H/U・名前・履歴')+'。\n')
    out.append('三つの手計算は上の段2先行表の2、および'+link('hand_examples.csv','全数値')+'にある。この三例ではlog PによるF→Hの費用増加が閾値を上回り、Fが残った。同一材料を0/ℓで局所計算するとF/H/Uすべて当たりで費用0となり、F→H→Uの判断になる。0/ℓ欄は同じ出生材料に対する算術であり、対照腕の同一試行を新しく走らせた値ではない。誕生時のP_H=P_Uという空履歴の扱いも、この走行の実装どおり明記した。\n')
    out.append('### 3. 例外ドアの選択シールと正解定義\n')
    doors=read('exception_doors.csv')
    arms=list(dict.fromkeys(r['arm'] for r in doors))
    available=[]
    for a in arms:
        for outcome in ('正解','外れ','黙り'):
            x=[r for r in doors if r['arm']==a and r['outcome']==outcome]
            yes=sum(r['correct_exception_definition_exists']=='True' for r in x)
            available.append([label(a),outcome,len(x),yes,len(x)-yes])
    out.append(table(['腕','実際の答え','課題数','正解できる定義あり','なし'],available)+'\n')
    out.append('正解できる定義とは、その予測前の記憶で、既存の門とその腕の答え方を通って当該ドアを正しく答える候補である。世界1は通常と例外のドア名が同じなので「共通」の答えとして記録した。実際に採用された定義のシールは、予測前の記憶から F sig_n / F sig_e / H[sig_n] / H[sig_e] / H[両方] / U を読む。R_selectedはsideのv39.R_usedと台帳R_usedを全件照合して読む。これは門通過後の採用の記録で、黙りでも採用された定義があればシールを数える。両方が空の試行は記録に採用なしとする。シール席なし、複数、選択なしは別欄に残す。'+link('exception_doors.csv','3060件のCSV（種・試行で接続可能）')+'、'+link('exception_door_seal_summary.csv','全結果と選択シールの内訳')+'、'+link('selected_seals_summary.json','sideの選択と予測前の記憶の全件照合')+'。\n')
    out.append('外れの三分類は次のとおり。136件の診断との照合はN3・世界2の選び間違いの行を使う。三分類に含まれない状態も分母から除かない。\n')
    wrong=read('wrong_seal_summary.csv');wt=[]
    for a in arms:
        for classification in ('選び間違い','区別の喪失'):
            x={r['seal_class']:int(r['count']) for r in wrong if r['arm']==a and r['classification']==classification}
            total=sum(x.values())
            extras=', '.join(f'{s}:{n}' for s,n in x.items() if n and s not in ('H[sig_n]','U','H[sig_e]')) or '0'
            wt.append([label(a),classification,total,x['H[sig_n]'],x['U'],x['H[sig_e]'],extras])
    out.append(table(['腕','分類','外れ','H[sig_n]','U','H[sig_e]','ほかの状態（件数）'],wt)+'\n')
    out.append(link('wrong_seal_summary.csv','外れの分類とシール状態のCSV')+'。全外れで、正解候補ありなら選び間違い、なしなら区別の喪失という既存分類と再一致した。\n')
    out.append('既存のL-Bの候補記録に含まれなかった例外ドアの黙り212件だけ、e15ef19由来の既存の分類手続きへ凍結記憶を渡して候補の答えを数えた。元の黙りは全件再現した。この読込手続きは静的な場面と識別子を復元するが、学習・忘却・記憶更新・模型の台帳の生成を行わない。段1と主集計は保存状態だけを読む。入力のsha256は前後で全件一致した。'+link('silent_candidates_summary.json','黙りの再現と入力の不変の検証')+'。\n')
    out.append('### 4. 500試行ごとの記憶\n')
    mem=read('memory_summary_500.csv')
    out.append('各値は20種の平均。1740は最終時点。種ごとの整数値はCSVに保存した。\n')
    out.append(table(['腕','試行終了数','総ビット','定義数','F席','H席','U席'],
                     [[label(r['arm']),r['trials_completed'],*[f'{float(r[k]):.2f}' for k in ('total_mean','defs_mean','nF_mean','nH_mean','nU_mean')]] for r in mem])+'\n')
    out.append('総ビットは骨組み・二ビットの席状態・F/Hの内容・辞書等を含む。旧照合のstrict-pcに合わせ、骨組みの引数が定義内の行に無くても関係IDである場合は関係位置として費用を数えた。この算術だけを診断側で復元し、400時点の総ビット、定義数、F/H/U数をsideと一件ずつ照合した。'+link('memory_500.csv','400時点の全個体・費用内訳')+'、'+link('memory_summary_500.csv','20種の合計と平均')+'。\n')
    definitions=read('definition_summary_500.csv');ds=[]
    for a in arms:
        groups=list(dict.fromkeys(r['door_group'] for r in definitions if r['arm']==a))
        for group in groups:
            x={r['seal_class']:int(r['count']) for r in definitions if r['arm']==a and r['trials_completed']=='1740' and r['label_basis']=='birth_door_group' and r['door_group']==group}
            if not sum(x.values()):continue
            extras=', '.join(f'{s}:{n}' for s,n in x.items() if n and s not in ('F sig_n','F sig_e','H[sig_n]','H[sig_e]','H[両方]','U')) or '0'
            ds.append([label(a),group,sum(x.values()),*[x[k] for k in ('F sig_n','F sig_e','H[sig_n]','H[sig_e]','H[両方]','U')],extras])
    out.append('最終記憶の定義とシールの内訳を、出生材料のドアの名前による分類で示す。件数は20種合計。\n')
    out.append(table(['腕','出生のドアの種類','定義数','F sig_n','F sig_e','H[sig_n]','H[sig_e]','H[両方]','U','ほか'],ds)+'\n')
    out.append('世界2の通常/例外は出生材料の店・ドア名から区別し、世界1は同じ名前なので共通とする。現在のF/Hのドアの答えから分類する版も別に置いた。Uは保持した答えの名前がないという群であり、実際のUの既定の答えを変更した意味ではない。シールやドアの席を持たない定義も残す。'+link('definition_counts_per_seed_500.csv','全種・各時点の定義の種類とシール内訳（出生/現在の二通り）')+'、'+link('definition_summary_500.csv','同内訳の20種合計')+'、'+link('definition_records_500.csv','定義ごとの名前・履歴と識別子')+'。\n')
    out.append('### 5. 記憶量と外れの比較の範囲\n')
    out.append('四点の表は上の段2先行表の5と'+link('final_memory_errors.csv','比較CSV')+'にある。同じλ主で最終総ビットはL-Bが187400、N3が214468、例外の外れは11と179だった。最終量だけを指して「L-Bが多く残した」という順序には一致しない。選択規則も異なり、λ=0.065の対照は欠測なので、記憶量を揃えた介入の結果としては扱わない。\n')
    out.append('### 記録・コード・受付の確定情報\n')
    out.append(f'旧照合3380344、L-B実装e0a1f2ed0f3a62c8396f346e4f39ef4802c35237、診断前の作業枝2ee8eccf1b5c9cf0d7101aa059a1c07b37a80348。今回の独立診断の最終保存コミットは `{head}`。作業枝の `tools/logp_seals_diag_2026_10_05/` に作業場所と同じバイトの最終版と仕様を保存した。模型・照合・既存分類のファイル差分は0。'+link('code_check.json','差分と構文の確認')+'、'+link('diagnostic_code_sha256.csv','作業場所と保存版のsha256')+'、'+link('execution_code_versions.json','処理ごとの実行版のコミットと指紋')+'。\n')
    out.append('入力のパスとsha256は'+link('input_sha256.csv','元記録の指紋')+'、件別中間出力の指紋は'+link('derived_inputs_sha256.csv','診断出力の指紋')+'。コマンドと受付枠は'+link('commands.json','コマンド記録')+'。全件の段1は0.7GB・二並列、誕生/記憶集計は0.3GB・二並列、黙り候補の既存診断は1.0GB・二並列で、すべてjobs.py run --waitと実出力先のdisk-pathを指定した。\n')
    out.append(f'最大実測RSSは誕生/記憶の一処理 {q["stage2_max_worker_rss_bytes"]:,} バイト、黙り候補の一処理 {q["silent_max_worker_rss_bytes"]:,} バイト。'+link('stage2_summary.json','全100処理の検算と実測')+'。T/L-BEの受付・走行は本診断のために停止していない。\n')
    report=ROOT/(NAME+'.md');text=report.read_text()
    assert '## 段2全項目完了' not in text,'重複の追記を避ける'
    first,rest=text.split('\n',1)
    status='\n最終更新：段1の全件一致を確認し、段2の1〜5を完了した。下の「段2全項目完了」が確定した表と検証記録である。lg・λ=0.065の一点は欠測。\n'
    report.write_text(first+status+rest+'\n'+'\n'.join(out))
    print(report)

if __name__=='__main__':main()
