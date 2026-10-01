"""完了した候補2の台帳と付記を読むだけで比較する。"""
import collections, importlib.util, json, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('relabel_compare',ROOT/'source/tools/histrole_checks/relabel_compare.py')
rc=importlib.util.module_from_spec(spec);spec.loader.exec_module(rc)
FIELDS=('coverage','hit','path','pred','reg')


def one(metric):
    m=json.loads(metric.read_text());renamed=Path(m['ledger']).parents[3];original=Path(m['original']['ledger']).parents[3]
    mp=json.loads((renamed/'relabel/map.json').read_text());inv={v:k for k,v in mp['predicates'].items()}
    lo,vo,bo,ao=rc.load(str(original),m['seed'],{});lr,vr,br,ar=rc.load(str(renamed),m['seed'],inv)
    assert len(lo)==len(lr)==1740
    vkey=lambda x:None if x is None else {k:v for k,v in x.items() if k!='conv_slots'}
    comparisons={}
    for name,a,b,key in [('台帳の比較対象',lo,lr,lambda x:x),('席と定義と変換',vo,vr,vkey),('新規・同化の選択',bo,br,lambda x:x),('回答の出どころと当たり',ao,ar,lambda x:x)]:
        diff=[t for t in sorted(a.keys()|b.keys()) if key(a.get(t))!=key(b.get(t))]
        comparisons[name]={'異なる試行数':len(diff),'最初の試行_0始まり':diff[0] if diff else None}
        if diff:comparisons[name]['最初の内容']={'元':key(a.get(diff[0])),'付け替え':key(b.get(diff[0]))}
    summary={'world':m['world'],'seed':m['seed'],'trials':1740,'outcomes':m['outcomes'],'original_outcomes':m['original']['outcomes'],'door':m['door'],'original_door':m['original']['door'],'comparisons':comparisons,
             '最終定義数':{'元':vo[max(vo)]['defs'],'付け替え':vr[max(vr)]['defs']},
             '変換数':{'元':sum(len(x['conv']) for x in vo.values()),'付け替え':sum(len(x['conv']) for x in vr.values())},
             '台帳本体':{'元':m['original']['body_sha'],'付け替え':m['body_sha']},
             '比較する数値': 'v39・v310beの浮動小数は既存のrelabel_compareに従い小数第9位で丸める。費用は参考、回答の比較は丸めなし。'}
    return summary


def main():
    watch='--watch' in sys.argv
    dest=ROOT/'analysis';dest.mkdir(exist_ok=True)
    while True:
        for p in sorted((ROOT/'metrics').glob('hole2_w*_renamed/seed*.json')):
            out=dest/f'{p.parent.name}_{p.stem}.json'
            if out.exists():continue
            row=one(p);out.write_text(json.dumps(row,ensure_ascii=False,indent=1)+'\n')
            print(f"世界{row['world']} 種{row['seed']} 比較完了 {row['comparisons']}",flush=True)
        n=len(list(dest.glob('hole2_w*_renamed_seed*.json')))
        if n==40 or not watch:return
        time.sleep(10)


if __name__=='__main__':main()
