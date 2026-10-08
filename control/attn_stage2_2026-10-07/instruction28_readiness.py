"""指示28の集計の入口。原gzipを開かず、完成と掲載の有無を記録する。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import subprocess

B = Path('/Users/tatsu-admin/Documents/ChatGPT/New project/codex_attn_2026-10-03')
R = B / 'report'
P = R / 'control/attn_stage2_2026-10-07'
N = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    with path.open('x') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    at = datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
    report = R / 'control/2026-10-08_クラウドの開始_走行の係.md'
    txt = report.read_text()
    table = txt[txt.rfind('### 使う本の表'):]
    git_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=R, text=True).strip()
    tree = subprocess.check_output(['git', 'ls-tree', '-r', '-l', 'HEAD',
        'ataru-0608/cloud_runs'], cwd=R, text=True).splitlines()
    blobs = []
    for line in tree:
        if line.endswith('.calibration.jsonl.gz'):
            info, path = line.split('\t', 1)
            mode, kind, blob, size = info.split()
            blobs.append(dict(path=path, git_blob=blob, compressed_bytes=int(size), contents_not_opened=True))
    assert len(blobs) == 1 and 'seed047' in blobs[0]['path']
    checkpoint = read(P / 'inbox_check_20261008_2321.json')
    slots = []
    for world in (1, 2):
        for seed in range(41, 49):
            item = dict(world=world, seed=seed, selection_pending=True, raw_record_verified=False)
            if world == 2 and seed in (41, 42, 44):
                case = checkpoint['cases'][str(seed)]
                m, f = case['records']['measurement'], case['records']['worker_finished']
                assert m['trials'] == 1740 and m['native_loop_returned'] and f
                item.update(selection_pending=False, selected='Macの原e9', native_completed=True,
                    path=case['raw_calibration_stat'][0]['path'],
                    compressed_bytes=case['raw_calibration_stat'][0]['bytes'],
                    original_light_v_counts=m['v_counts'],
                    raw_V_counter_independently_matched=False)
            elif world == 1 and seed == 47:
                sha = subprocess.check_output(['git', 'show',
                    'HEAD:ataru-0608/cloud_runs/calib_w1_seed047/researcher/seed047.calibration.jsonl.gz.sha256'],
                    cwd=R, text=True).split()[0]
                assert sha == 'f45e2d165f473bdfa6995d04d32b6b53c9dbf022908ad37c5bc37994191edb24'
                item.update(selection_pending=False, selected='使う本の表：クラウド旗なしw1_seed047',
                    native_finished_at_from_table='2026-10-08T12:06:22Z',
                    git_path=blobs[0]['path'], git_blob=blobs[0]['git_blob'],
                    compressed_bytes=blobs[0]['compressed_bytes'], declared_sha256=sha,
                    working_tree_absent_due_to_sparse_checkout=True, git_blob_present=True)
            elif world == 2 and seed == 43:
                item['selection_rule'] = '使う本の表でMacと適格なクラウドの先着を確認する。Macは未完走。'
            slots.append(item)
    agg = B / 'cstar_stage2_preparation_source/tools/calibration_summary.py'
    policy = dict(
        world_seed_weight='正に絞る前に各世界×種へ1/16、組内の候補機会を等重み',
        positive_quantiles='重みつき一般逆関数でL25/L50/L90',
        leave_out='同じ種を両世界から一組ずつ除き各分位比を確認。>1.25又は<0.8なら41〜60へ一度だけ拡張',
        counts='正/0/負、実候補FH/HU、参照HU、非正の解放ビットによる除外を別記',
        raw_checks='選定した原記録のsha256、world/seed、全1740行のtrial順、Vの比と分母、軽いVカウンタとの一致',
        admissibility='旗つきは該当全長関門合格済みの本だけ。同じ組は適格なうち先に実1740完走した本。指定の使う本の表に従う。')
    result = dict(instruction=28, at=at, report_git_commit=git_head,
        selection_report=str(report), selection_report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
        selection_table=table, cloud_raw_blobs_present=blobs, slots=slots,
        required_pairs=16, confirmed_selected_raw_paths_or_blobs=4, all16_ready=False,
        aggregate_started=False, official_prices_computed=False, grades_not_read=True,
        raw_gzip_not_opened=True, sparse_checkout_unchanged=True, policy=policy,
        existing_weighted_aggregator=str(agg),
        existing_weighted_aggregator_sha256=hashlib.sha256(agg.read_bytes()).hexdigest(),
        aggregate_receipt_required=True,
        aggregate_mem_gb='実測の所要量と×1.2以上を確認後に決める。未確定。',
        final_manifest_not_generated=True, output=str(N / 'formal_calibration_summary.json'),
        preparation_tool_repair='準備台本のmeasurementの項目名を元のtrialsに合わせた。模型・関門・原記録は変更無し。')
    write(N / 'calibration_readiness.json', result)
    write(P / 'instruction28_calibration_readiness_20261008.json', result)
    write(P / 'instruction28_preparation_artifacts_20261008.json', dict(at=at,
        scripts={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (N / 'prepare.py', N / 'readiness.py')},
        command_count=280, configuration_count=40, source_code_changed=False,
        production_or_calibration_models_started=False, new_receipts_started=False))
    print(json.dumps(dict(at=at,selected_raw_paths_or_blobs=4, all16_ready=False, aggregate_started=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
