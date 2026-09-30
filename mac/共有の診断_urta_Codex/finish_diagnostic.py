"""220本の照合済み記録をまとめ、公開用の表と保存一覧を作る。"""
from pathlib import Path
import collections
import csv
from datetime import datetime
import gzip
import hashlib
import io
import json
import os
import shutil
from zoneinfo import ZoneInfo
from aggregate_diagnostic import distribution, METRICS

ROOT=Path(__file__).resolve().parent
EXPORT=ROOT/'diagnostic_export'
TABLES=ROOT/'diagnostic_tables'
ARMS=[a['arm'] for a in json.loads((ROOT/'material_inventory.json').read_text())['arms']]
LAM={a['arm']:a['lambda'] for a in json.loads((ROOT/'material_inventory.json').read_text())['arms']}

def num(v):
    if v is None:return '未定義'
    return str(v) if isinstance(v,int) else f'{v:.6g}'

def table(header,rows):
    return '\n'.join(['| '+' | '.join(header)+' |','|'+'|'.join('---' for _ in header)+'|']+
                     ['| '+' | '.join(num(v) if isinstance(v,(int,float)) or v is None else str(v) for v in row)+' |' for row in rows])+'\n'

def read_all():
    aggregates=sorted(TABLES.glob('*/seed*.aggregate.json'))
    assert len(aggregates)==220
    result={a:dict(arm=a,lambda_=LAM[a],runs=[],counts=collections.Counter(),
                  levels={lev:dict(counts=collections.Counter(),values={k:[] for k in METRICS}) for lev in ('A','B')}) for a in ARMS}
    inventory={h['path']:h for a in json.loads((ROOT/'material_inventory.json').read_text())['arms'] for h in a['headers']}
    for p in aggregates:
        run=json.loads(p.read_text());arm=run['arm'];seed=run['seed'];group=result[arm]
        assert 1<=seed<=20
        export_meta=json.loads((EXPORT/arm/f'seed{seed:03d}.summary.json').read_text())
        assert export_meta['text_sha256']==run['decision_text_sha256']
        original=inventory[str(Path('/Users/tatsu-admin/v310urtaprod')/arm/'ledgers/cells/f0.5000_th2.1000_vt0.3842_first_order'/f'seed{seed:03d}.jsonl.gz')]
        assert (original['bytes'],original['mtime_ns'])==(run['input_summary']['source_bytes'],run['input_summary']['source_mtime_ns'])
        group['runs'].append(run);group['counts'].update(run['input_summary']['counts'])
        for lev in ('A','B'):group['levels'][lev]['counts'].update(run['counts'][lev])
        with gzip.open(TABLES/arm/f'seed{seed:03d}.quantities.csv.gz','rt',encoding='utf-8',newline='') as stream:
            for row in csv.DictReader(stream):
                lev=row['level'];values=group['levels'][lev]['values']
                def val(key):return float(row[key]) if row[key] else None
                original_existing=bool(row['original'])
                if original_existing:values['required_net_saving'].append(val('required_net_saving'))
                if row['changed']=='0':
                    values['remaining_unchanged'].append(val('remaining_bits'))
                    if original_existing:values['remaining_unchanged_existing'].append(val('remaining_bits'))
                if row['new_available']=='1':
                    orig=val('new_dC_original');net=val('net_memory_saving')
                    gl=val('gross_selected_min');gh=val('gross_selected_max')
                    for key in ('gross_selected_min','gross_selected_max','gross_max','net_memory_saving','net_memory_saving_ratio'):
                        values[key].append(val(key))
                    values['gross_selected_ratio_min'].append(gl/orig if orig else None)
                    values['gross_selected_ratio_max'].append(gh/orig if orig else None)
                    values['reference_selected_min'].append(gl-net)
                    values['reference_selected_max'].append(gh-net)
    for arm,group in result.items():
        assert sorted(r['seed'] for r in group['runs'])==list(range(1,21))
        assert group['counts']['trials']==34800
        for lev in ('A','B'):
            level=group['levels'][lev]
            level['distributions']={k:distribution(v) for k,v in level.pop('values').items()}
    return result

def report(groups):
    stamp=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
    total=collections.Counter()
    for g in groups.values():total.update(g['counts'])
    text=[f'## {stamp}：第1段・全11腕の後づけ計算\n',
          '対象は v3.10urta の11腕、各20本、種1〜20、各1740試行。材料の台帳220本を読むだけで処理した。模型の走らせ直し0本、模型の変更0件、種21〜40の読み取り0本。\n',
          '水準Bは構造と同じ名前の集合を共有する主の結果。水準Aは構造だけを共有する参考。席の状態・履歴の回数・固定名の指定・成績・定義の頭は共有しない。U は中身を忘れた席で、共有の照合から除いた。\n',
          '変わる定義だけに、既にある一つの定義からの共有を許した。同化は変更前・変更後を同じ条件で数えた。すべての候補の届け先・書き直し費用は元の値のまま。符号表は判断前の値。共有先ごとに条件を満たす行を全部使い、部分集合は探さない。一回の判断の費用だけを置き換え、その後の学習を追わない近似。B の忘却で解放する量は置き換えていない。\n',
          f"状態の差分の連鎖・最終状態の指紋・場面の指紋と1740試行の提示・伏せ辺が、全220本で一致。記録された候補費用・選択・選ばれた定義の履歴が全{total['decisions']}判断で記録と一致。材料のファイルの大きさ・更新時刻が、最初の確認・計算前・計算後で一致。小さな定義による符号の確認7件が通った。\n",
          '### 判断の数と入れ替わり\n']
    header=['腕','λ','判断','元は同化','元は新規','型またぎ同化','B 同化→新規','B 全入替','A 同化→新規','A 全入替']
    text.append(table(header,[[a,str(LAM[a]),g['counts']['decisions'],g['counts']['existing'],g['counts']['new'],g['counts']['cross'],g['counts']['B_existing_to_new'],g['counts']['B_changed'],g['counts']['A_existing_to_new'],g['counts']['A_changed']] for a,g in groups.items()]))
    text.append('型またぎは、選ばれた既存の定義が生まれた場面の型と、今回の場面の型が違う判断。研究者側の記録だけで数えた。\n')
    text.append(table(['腕','水準','型またぎ→新規','新規→既存','既存→別の既存','新規が比較に無い'],[[a,lev,g['levels'][lev]['counts']['cross_to_new'],g['levels'][lev]['counts']['new_to_existing'],g['levels'][lev]['counts']['existing_to_other_existing'],g['counts']['new_unavailable']] for a,g in groups.items() for lev in ('B','A')]))
    text.append('### 記憶の節約の分布\n')
    text.append('差し引きの節約は、元の新規候補の記憶増分−共有符号での記憶増分。共有しない場合も印を1ビット払うので−1になりうる。割合はこの節約を元の新規候補の記憶増分で割った値。新規候補を比較できた判断が分母。分位点は値を小さい順に並べて指定の位置に来る値。中央値は中央の値。値の間は線形に補間した。\n')
    for metric,label,scale in [('net_memory_saving','差し引きの節約（ビット）',1),('net_memory_saving_ratio','新規の元の増分に対する割合（%）',100)]:
        text.append(label+'\n')
        text.append(table(['腕','水準','数','未定義','最小','25%点','中央値','75%点','90%点','最大','平均'],[[a,lev,g['levels'][lev]['distributions'][metric]['n'],g['levels'][lev]['distributions'][metric]['undefined']]+[None if g['levels'][lev]['distributions'][metric][key] is None else scale*g['levels'][lev]['distributions'][metric][key] for key in ('min','p25','median','p75','p90','max','mean')] for a,g in groups.items() for lev in ('B','A')]))
    text.append('### 必要な節約と、参照を引く前の共有できる量\n')
    text.append('必要な差し引きの節約は、元が同化の判断で (元の新規の比較費用−元の選択の比較費用)÷λ。同点では既存が残るため、この値を超える必要がある。λ＝0では割れないので未定義とした。共有できる量は、新規候補と既存の共有先の組ごとの参照を引く前の節約の最大値。共有先の採用前の量で、全共有先の数値も保存した。\n')
    for metric,label in [('required_net_saving','必要な差し引きの節約'),('gross_max','共有できる量（参照を引く前）'),('remaining_unchanged_existing','入れ替わらなかった同化判断で、新規が勝つために不足したビット')]:
        text.append(label+'\n')
        text.append(table(['腕','水準','数','未定義','最小','中央値','90%点','最大','平均'],[[a,lev,g['levels'][lev]['distributions'][metric]['n'],g['levels'][lev]['distributions'][metric]['undefined']]+[g['levels'][lev]['distributions'][metric][key] for key in ('min','median','p90','max','mean')] for a,g in groups.items() for lev in ('B','A')]))
    text.append('不足したビットは、共有符号での新規の比較費用と、その符号で選ばれた最小費用との差をλで割った値。入れ替わりが無く元も新規だった判断を含む分布は保存した表の remaining_unchanged。\n')
    text.append('### 共有先の候補と、除外したUの行\n')
    text.append('U の除外は、候補を評価したたびに数えた延べ本数。同じ定義が別の判断・候補で現れれば再び数える。共有先候補二つ以上は、共有する行が1本以上ある既存の定義が二つ以上あった場合。\n')
    text.append(table(['腕','水準','どれかの候補で共有先2以上の判断','新規候補で共有先2以上','新規で共有採用','新規のU除外','新規の共有先U除外（延べ）'],[[a,lev]+[g['levels'][lev]['counts'][k] for k in ('any_candidate_multiple_sources','new_multiple_sources','new_shared','new_excluded_U_N','new_excluded_U_S_exposures')] for a,g in groups.items() for lev in ('B','A')]))
    text.append('### 走行ごとの数\n')
    text.append(table(['腕','種','判断','元は同化','型またぎ同化','B 同化→新規','B 全入替','B 型またぎ→新規','A 同化→新規','A 全入替','A 型またぎ→新規'],[[a,r['seed']]+[r['input_summary']['counts'][k] for k in ('decisions','existing','cross','B_existing_to_new','B_changed','B_cross_to_new','A_existing_to_new','A_changed','A_cross_to_new')] for a,g in groups.items() for r in sorted(g['runs'],key=lambda r:r['seed'])]))
    text.append('### 保存した量と再計算\n')
    text.append('`mac/共有の診断_urta_Codex/` に、判断ごとの全候補・全共有先・対応する行・穴・共有量・参照(a)〜(e)・変更前後の費用・選択を保存。Zstandard は、元の文字列に戻せる圧縮形式。各 jsonl.zst の復元文字列が、手元の jsonl.gz と SHA-256 で一致。SHA-256 はファイルの中身を照合する指紋。各 summary.json に元の台帳本体の指紋と保存ファイルの指紋を記録。\n')
    text.append('CSV は表を文字で保存する形式。各 quantities.csv.gz は新規候補の必要量・共有量・参照内訳・不足量、各 aggregate.json は走行ごとの分布、summary.json は腕ごとの分布。最大差し引きが同点の共有先は全部残し、共有量・参照の表では最小と最大を保存。符号や一つまでという制限を変える場合も、元の候補費用と各共有先の対応・量を読んで計算し直せる。\n')
    return '\n'.join(text)

def main():
    groups=read_all()
    output=ROOT/'diagnostic_report.md'
    if output.exists():raise FileExistsError(output)
    output.write_text(report(groups))
    summary=EXPORT/'summary.json'
    if summary.exists():raise FileExistsError(summary)
    compact={a:{k:v for k,v in g.items() if k!='runs'} for a,g in groups.items()}
    summary.write_text(json.dumps(compact,ensure_ascii=False,indent=2)+'\n')
    for a in ARMS:
        for p in sorted((TABLES/a).glob('*')):
            dest=EXPORT/a/p.name
            if dest.exists():raise FileExistsError(dest)
            os.link(p,dest)
    for name in ('shared_diagnostic.py','aggregate_diagnostic.py','compress_diagnostic.py','finish_diagnostic.py','check_shared_codec.py','shared_codec_checks.json','shared_codec_checks_v2.json','material_inventory.json','example_1691_shared_v2.json','source_provenance.json'):
        dest=EXPORT/name
        if dest.exists():raise FileExistsError(dest)
        shutil.copy2(ROOT/name,dest)
    files=[]
    for p in sorted(EXPORT.rglob('*')):
        if p.is_file():files.append(dict(path=str(p.relative_to(EXPORT)),bytes=p.stat().st_size,sha256=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()))
    (EXPORT/'manifest.json').write_text(json.dumps(dict(files=files,code_tag='v3.10urta-main',material_commit='9d7db1f94321efe7d61c0b15caf7d8b780e10184',model_reruns=0,seeds=list(range(1,21))),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'runs':220,'files':len(files),'bytes':sum(f['bytes'] for f in files),'report':str(output)},ensure_ascii=False))

if __name__=='__main__':main()
