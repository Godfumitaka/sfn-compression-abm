"""全40本の終了後に、名前の対応・旗・台帳の指紋を結果枝へ保存する。"""
from pathlib import Path
import gzip
import json
import shutil

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source'
RESULTS = ROOT.parent / 'codex_worldv4_2026-10-01/results'
DEST = RESULTS / 'mac/holes_20261001'


def main():
    rows = []
    for world in (1, 2):
        for seed in range(1, 21):
            name = f'hole2_w{world}_renamed'
            measured = json.loads((ROOT / 'metrics' / name / f'seed{seed:03d}.json').read_text())
            assert measured['trials'] == measured['original']['trials'] == 1740
            assert measured['header']['run_seed'] == seed
            run = ROOT / 'runs' / name / f'seed{seed:03d}'
            mapping = json.loads((run / 'relabel/map.json').read_text())
            flag = json.loads((run / 'flag.json').read_text())
            rows.append({'world': world, 'seed': seed, 'metrics': measured,
                         'flag': flag, 'mapping': mapping})
    out = DEST / 'candidate2_provenance_40.json.gz'
    assert not out.exists()
    out.write_bytes(gzip.compress((json.dumps(rows, ensure_ascii=False, separators=(',', ':'))+'\n').encode(), mtime=0))
    # 小例と台帳比較は公開の探索枝にも置く。出力先は明示する。
    target = SOURCE / 'tools/holes_20261001'
    code = (ROOT / 'probe_relabel_small.py').read_text()
    code = code.replace("ROOT=Path(__file__).resolve().parent;SOURCE=ROOT/'source'",
                        "SOURCE=Path(__file__).resolve().parents[2];ROOT=SOURCE.parent")
    code = code.replace("p=ROOT/'candidate2_small_192_v2.json'", "p=Path(sys.argv[1])")
    paths = [(target / 'probe_relabel_small.py', code),
             (target / 'compare_machine_ledgers.py', (ROOT / 'compare_machine_ledgers.py').read_text())]
    for path, contents in paths:
        assert not path.exists()
        path.write_text(contents)
    for filename in ('run_stage1.py', 'analyze_stage1.py', 'verify_relabel_worlds.py', 'publish_stage1_provenance.py'):
        dst = DEST / 'scripts' / filename
        dst.parent.mkdir(exist_ok=True)
        assert not dst.exists()
        shutil.copy2(ROOT / filename, dst)
    print(json.dumps({'runs': len(rows), 'provenance_bytes': out.stat().st_size}, ensure_ascii=False))


if __name__ == '__main__':
    main()
