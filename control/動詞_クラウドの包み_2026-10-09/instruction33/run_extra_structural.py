"""前回99件のXMLで確認した残り四ファイルと、新しい比較の人工記録検査。"""
from pathlib import Path
import argparse
import fcntl
import run_structural as S

EXTRA=['test_attnallin.py','test_attnsme.py','test_sme_record_keys.py','test_verbworld.py']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source');p.add_argument('runtime');p.add_argument('--test-python',required=True)
    p.add_argument('--receipt',required=True);p.add_argument('--mode',choices=('serial',),default='serial')
    p.add_argument('--admitted',action='store_true');a=p.parse_args()
    S.SERIAL=[*EXTRA,str(Path(__file__).parent/'test_compare100.py')]
    if a.admitted:
        raise SystemExit(S.admitted(a))
    # dispatchは元のS.__file__でなく、この入口を使う。同じ資源条件の元関数は不変。
    S.__file__=__file__
    with Path(a.runtime).with_suffix('.dispatch.lock').open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        raise SystemExit(S.dispatch(a))
