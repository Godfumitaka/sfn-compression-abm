"""門の後づけの表と図だけを、指定された結果と報告へ保存する。"""
import argparse
import csv
import json
from pathlib import Path
import shutil

from aggregate_v4d import RESULTS,REPORT,PUBLIC,manifest


def main():
    ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);ap.add_argument('name');ap.add_argument('title')
    a=ap.parse_args();dest=PUBLIC/a.name;assert not dest.exists();shutil.copytree(a.folder,dest)
    for name in ('gate_curves.py','plot_gate_curves.py','publish_curves.py'):
        shutil.copyfile(Path(__file__).resolve().parent/name,dest/name)
    manifest(dest)
    with (dest/'curves.csv').open() as f:rows=list(csv.DictReader(f))
    strata={'all':'全課題','switch_A':'切り替わる葉A','switch_B':'切り替わる葉B'}
    lines=['\n## '+a.title+'\n',
           '門gは、答えるために必要な支持の割合の下限。現在の答えの支持がg未満ならその答えを黙らせたとして数えた。元の棄権はそのまま。定義の選び直しと、その後の学習は追っていない。種1〜20だけを集計。',
           '', '無作為の期待値は、表の各層の実際の回答から、門で黙らせた件数と同数を無作為に選んだ場合。期待する誤答の件数＝黙らせた件数×元の誤答/(元の正解＋元の誤答)。正解も同じ式。各層の元の分母はcurves.csvに保存。',
           '', '失った正解の型：(a)定義の出生型・土台型・予測時点までの同化型に含まれない型、(b)含まれるが出生型と違う型、(c)その他。型の印は解析だけに使う。',
           '', '| 腕 | 課題 | g | 避けた誤答 | 失った正解 | 無作為：誤答 | 無作為：正解 | 正解の損失a | b | c |',
           '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['arm']} | {strata[r['stratum']]} | {float(r['gate']):.2f} | {r['avoided_wrong']} | {r['lost_correct']} | {float(r['random_avoided_wrong']):.6f} | {float(r['random_lost_correct']):.6f} | {r['lost_correct_a']} | {r['lost_correct_b']} | {r['lost_correct_c']} |")
    lines+=['',f'![門の曲線](../mac/world_v4_d_20261002/{a.name}/gate_curves.png)',
            '',f'![失った正解の型](../mac/world_v4_d_20261002/{a.name}/lost_correct_types.png)',
            '',f'保存先：mac/world_v4_d_20261002/{a.name}/。数表、図（PNG・SVG）、計算と描画のコード、ファイルの指紋。']
    with REPORT.open('a') as f:f.write('\n'.join(lines)+'\n')
    print(json.dumps({'destination':str(dest),'table_rows':len(rows)},ensure_ascii=False))


if __name__=='__main__':main()
