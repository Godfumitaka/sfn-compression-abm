"""八体300の実測の有無と指定条件を検査する。全長の安全上限にしない。"""
from pathlib import Path
import sys
from compare import complete
from run import C,host,read,save

root=Path(sys.argv[1]).resolve();r,res,out,headers,completion=complete(root,'on8_measure300')
assert r['host']==host() and r['models']==8 and r['parallel']
assert '--v311c-audit' not in r['model_argv'] and r['argv'][r['argv'].index('--v311c-probe-every')+1]=='100'
assert res['rss_sum_peak_bytes']>0
for name in r['requires']:
    proof=read(root/'gates'/name);assert proof['passed'] is True and proof['candidate']==C and proof['host']==r['host']
save(root/'gates/gate-measure.json',dict(passed=True,candidate=C,host=r['host'],name=r['name'],
  elapsed_seconds=res['elapsed_seconds'],rss_sum_peak_bytes=res['rss_sum_peak_bytes'],
  note='300試行だけの実測。1740の安全上限・予約・較正価格・列取得の代わりにしない。'))
