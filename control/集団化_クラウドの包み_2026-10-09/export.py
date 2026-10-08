"""原出力はS3へ渡す。GitHub用は時間・SHA・比較・起動の証拠だけ。"""
import argparse
import csv
import hashlib
from pathlib import Path
import shutil
from run import read

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def export(root,dest):
    dest.mkdir(parents=True,exist_ok=False)
    with (dest/'sha256.tsv').open('x') as f:
        w=csv.writer(f,delimiter='\t');w.writerow(['relative_path','bytes','sha256'])
        for p in sorted(root.rglob('*')):
            if p.is_file():w.writerow([str(p.relative_to(root)),p.stat().st_size,digest(p)])
    with (dest/'runs.tsv').open('x') as f:
        w=csv.writer(f,delimiter='\t');w.writerow(['name','commit','host','trials','models','parallel','seconds','rss_sum_peak_bytes','exitcode','warnings'])
        for ev in sorted((root/'evidence').glob('*')):
            if not (ev/'resource.json').exists():continue
            r=read(ev/'resource.json');s=read(ev/'runtime.json')
            w.writerow([s['name'],s['commit'],s['host'],s['model_argv'][s['model_argv'].index('--trial-count')+1],
             s['models'],s['parallel'],r['elapsed_seconds'],r['rss_sum_peak_bytes'],r['exitcode'],';'.join(r['warnings'])])
            d=dest/s['name'];d.mkdir()
            for name in ('runtime.json','start.json','process.json','resource.json','time.log','admission-command.json'):
                shutil.copyfile(ev/name,d/name)
    for p in (root/'gates').glob('*.json'):shutil.copyfile(p,dest/p.name)
    if (root/'STOP.json').exists():shutil.copyfile(root/'STOP.json',dest/'STOP.json')
    if (root/'component-evidence').exists():
        shutil.copytree(root/'component-evidence',dest/'component-evidence',ignore=shutil.ignore_patterns('pytest-temp'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('destination',type=Path)
    a=p.parse_args();export(a.root.resolve(),a.destination.resolve())
