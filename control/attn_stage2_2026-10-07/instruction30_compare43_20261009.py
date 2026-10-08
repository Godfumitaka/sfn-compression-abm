"""指示30の任意の確かめ：完走済みのMac43とクラウド43の原較正だけを読む。"""
from pathlib import Path
import gzip,hashlib,json,subprocess,resource
import aggregate as A
root=A.ROOT;manifest=json.loads((root/'selection_manifest.json').read_text())
m=A.safe_start()
ref='ataru-0608/cloud_runs/calib_prune_w2_seed043/researcher/seed043.calibration.jsonl.gz'
head=manifest['report_commit']
target=root/'raw/cloud_w2_seed043.calibration.jsonl.gz'
assert not target.exists() and not (root/'mac_cloud_seed43_comparison.json').exists()
with target.open('xb') as f:subprocess.run(['git','show',head+':'+ref],cwd=A.REPORT,stdout=f,check=True)
expected=subprocess.check_output(['git','show',head+':'+ref+'.sha256'],cwd=A.REPORT,text=True).split()[0]
assert A.sha(target)==expected
left=Path(next(i['path'] for i in manifest['items'] if (i['world'],i['seed'])==(2,43)))
sha_left=hashlib.sha256();sha_right=hashlib.sha256();line_no=0;size=0
# calibration.pyの原行には時間欄が無いので、除外無しで一行ずつ全バイトを比較。
with gzip.open(left,'rb') as x,gzip.open(target,'rb') as y:
 while True:
  a,b=x.readline(),y.readline()
  if a!=b:raise RuntimeError(('原較正の最初の不一致',line_no,len(a),len(b)))
  if not a:break
  sha_left.update(a);sha_right.update(b);size+=len(a);line_no+=1
assert line_no==1740
A.watch();assert not (root/'warning.json').exists()
out=dict(at=A.stamp(),Mac=str(left),cloud_git_path=ref,cloud_compressed_sha256=expected,
 cloud_copy_sha256=A.sha(target),trials=1740,passed=True,uncompressed_bytes=size,
 Mac_uncompressed_sha256=sha_left.hexdigest(),cloud_uncompressed_sha256=sha_right.hexdigest(),
 exclusions=[],time_fields_present=False,model_runs=0,original_records_changed=False,
 selection_remains_Mac=True,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
A.write(root/'mac_cloud_seed43_comparison.json',out);print(json.dumps(out,ensure_ascii=False))
