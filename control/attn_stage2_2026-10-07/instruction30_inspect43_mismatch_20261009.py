"""既に止まった任意比較の、報告済みの一行だけを読んで不一致の字句を保全する。"""
from pathlib import Path
import gzip,hashlib,json,resource
import aggregate as A
R=A.ROOT;manifest=json.loads((R/'selection_manifest.json').read_text());A.safe_start()
left=Path(next(i['path'] for i in manifest['items'] if (i['world'],i['seed'])==(2,43)))
right=R/'raw/cloud_w2_seed043.calibration.jsonl.gz'
def line(p):
 with gzip.open(p,'rb') as f:
  for _ in range(869):out=f.readline()
 return out
a,b=line(left),line(right);x,y=json.loads(a),json.loads(b);assert x['trial']==y['trial']==868 and a!=b
def differences(x,y,path='$'):
 if type(x)!=type(y):return [dict(path=path,Mac=x,cloud=y)]
 if isinstance(x,dict):
  assert x.keys()==y.keys()
  return [v for k in x for v in differences(x[k],y[k],path+'.'+k)]
 if isinstance(x,list):
  assert len(x)==len(y)
  return [v for i in range(len(x)) for v in differences(x[i],y[i],path+f'[{i}]')]
 return [] if x==y else [dict(path=path,Mac=x,cloud=y)]
diff=differences(x,y);first=next(i for i in range(min(len(a),len(b))) if a[i]!=b[i])
out=dict(at=A.stamp(),passed=False,comparison='任意のMac43対cloud43・原較正だけ',first_line_one_based=869,first_trial=868,
 first_byte_zero_based=first,Mac_line_bytes=len(a),cloud_line_bytes=len(b),
 first_Mac_lexeme_context=a[max(0,first-90):first+130].decode(),
 first_cloud_lexeme_context=b[max(0,first-90):first+130].decode(),value_differences=diff,
 Mac_line_sha256=hashlib.sha256(a).hexdigest(),cloud_line_sha256=hashlib.sha256(b).hexdigest(),
 failed_comparison_receipt_pid=44581,actual_exit_code=1,first_line_only_inspection=True,
 original_records_changed=False,comparison_repeated=False,automatic_retry=False,
 formal_selected_seed43='Mac',unused_cloud43_not_in_formal_aggregate=True,
 platform_cause_not_established=True,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
A.write(R/'mac_cloud_seed43_comparison_failure.json',out);print(json.dumps(out,ensure_ascii=False))
