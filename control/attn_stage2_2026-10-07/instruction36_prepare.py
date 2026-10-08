"""指示36の四模型と二比較を結果前に固定する。模型をimportしない。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.util
import json
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
B = ROOT.parents[1]
S = ROOT.parent
R = B / 'report'
P = R / 'control/attn_stage2_2026-10-07'
SOURCE = B / 'cstar_stage2_memo_source'
CODE = '8ed8cf2b2920787e55b6f5134300fc350dffe5e7'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def main():
    at = datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip() == CODE
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=SOURCE, text=True).strip()
    assert not subprocess.check_output(['git', 'diff', 'c79215980a913cc426a63f25048e0dfc6fd1f758', '--', 'abm/', 'tools/v39.py'], cwd=SOURCE)
    check = ET.parse(ROOT / 'component_tests_attempt1.xml').getroot().find('testsuite')
    assert check.attrib['tests'] == '55' and check.attrib['failures'] == check.attrib['errors'] == '0'
    spec = importlib.util.spec_from_file_location('declarations', S / 'instruction28_wave1_preparation/prepare.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parser = module.parser_from_source(SOURCE / 'tools/v3_run.py')
    old = json.loads((P / 'instruction31_wave1_a_commands_20261009.json').read_text())
    wave = next(v for v in old['commands'] if v['selected_for_use_by_instruction31']
                and v['row'] == '1a' and v['world'] == 2 and v['seed'] == 1)
    calibration_path = S / 'instruction27_p10_parallel/p10_on_1740/native_command.json'
    calibration = json.loads(calibration_path.read_text())
    cases = {}
    originals = {}
    immutable = {}
    for family, original, seed, no_forget in (
        ('forget', wave['argv'], 1, False), ('calibration', calibration, 41, True),
    ):
        originals[family] = dict(argv=original, configuration_sha256=sha(original[2]))
        cfg = ROOT / f'w2_seed{seed:03d}_config.json'
        cfg.write_bytes(Path(original[2]).read_bytes())
        assert sha(cfg) == sha(original[2])
        immutable[str(cfg)] = sha(cfg)
        for flag in ('off', 'on'):
            name = f'{family}_{flag}_200'
            folder = ROOT / name
            argv = list(original)
            argv[2], argv[3] = str(cfg), str(folder / 'output')
            argv[argv.index('--trial-count') + 1] = '200'
            expected = list(original)
            expected[2:4] = argv[2:4]
            expected[expected.index('--trial-count') + 1] = '200'
            argv.extend(['--stage2-memo', flag])
            assert argv[:-2] == expected
            args = parser.parse_args(argv[2:])
            assert args.shop_world == 2 and args.seeds == str(seed)
            assert args.trial_count == 200 and args.horizon == 1740 and args.workers == 1
            assert args.stage2_speed == args.stage2_cache_prune == 'on' and args.stage2_memo == flag
            assert args.stage2_reuse == 'off' and args.sme_gc_threshold is None and not args.sme_fast_encode
            assert args.stage2_birth_hu == 'on' and bool(args.no_forget_exec) == no_forget
            assert argv[argv.index('--e-price') + 1] == '0.01873710622997919'
            assert argv[argv.index('--v39-price') + 1] == (
                '0.01873710622997919' if no_forget else '0.00035129738499384776')
            native = folder / 'native_command.json'
            write(native, argv)
            immutable[str(native)] = sha(native)
            cases[name] = dict(source=str(SOURCE), code=CODE, world=2, seed=seed, trials=200,
                horizon=1740, mem_gb=4, observer='observe.py', compare_observer=True,
                memo=flag, no_forget_exec=no_forget, reference=str(ROOT / f'{family}_off_200') if flag == 'on' else None,
                native_command=argv, configuration_sha256=sha(cfg), production_started=False)
    for name in ('controller.py', 'observe.py', 'compare_records.py', 'prepare.py'):
        immutable[str(ROOT / name)] = sha(ROOT / name)
    resources = S / 'instruction19_speed_gate/gate.py'
    immutable[str(resources)] = sha(resources)
    immutable[str(B / 'sme_attention_2026-10-07/priority25_reserve6_2026-10-06/hold_dispatchers.py')] = sha(
        B / 'sme_attention_2026-10-07/priority25_reserve6_2026-10-06/hold_dispatchers.py')
    comparison = S / 'instruction26_basic_gate_7294389d/compare_records.py'
    assert sha(comparison) == sha(ROOT / 'compare_records.py')
    scope = dict(at=at, authority='自分の受け箱 指示36（07:57、Claude）と従来の指示34/26の比較基準',
        ledger='見出し一行だけ除く', timing='第二段の既定の指定時間数値欄だけ',
        all_model_categories=['ledgers', 'side', 'attention', 'stage2', 'researcher', 'evictions'],
        strictpc_counter='元の字句の全バイト', observer='tie_state/saved_matcherの原全バイト・順つき',
        provenance_separate=['flag', 'manifest（strictpcは必須比較）', 'done'],
        rounding_or_tolerance=False, additional_exclusions=False, comparison_source_sha256=sha(comparison),
        both_P10_on=True, P10_guard_required='enabled/native_loop_returned、200境界、forbidden_reads=0')
    write(ROOT / 'comparison_scope_confirmed.json', scope)
    immutable[str(ROOT / 'comparison_scope_confirmed.json')] = sha(ROOT / 'comparison_scope_confirmed.json')
    manifest = dict(instruction=36, at=at, code=CODE, source=str(SOURCE),
        base='c79215980a913cc426a63f25048e0dfc6fd1f758', flag='--stage2-memo off|on（既定off、P5・P7r）',
        cases=cases, original_commands=originals, immutable_sha256=immutable,
        original_non_source_flags_values_order_unchanged=True, configuration_bytes_unchanged=True,
        component_checks=dict(tests=55, failures=0, errors=0, seconds=1.37, jobs_pid=11692,
            jobs_exit_code=0, mem_gb=1, xml_sha256=sha(ROOT / 'component_tests_attempt1.xml')),
        abm_and_bit_calculation_diff_empty=True, cli_checked_without_model_import=True,
        memory_basis='新しい試行内の控えの常駐は未計測。既存Mac模型の最大常駐2870755328bytesの1.2倍以上を確保し各4GB。従来200約350MBを上限とせず余裕を置く。',
        deadline='2026-10-11 09:00 JST', new_models_started=0,
        full_cloud_gate_pending=True, adoption_decided=False)
    write(ROOT / 'preparation_manifest.json', manifest)
    write(P / 'instruction36_preparation_manifest_20261009.json', manifest)
    write(P / 'instruction36_comparison_scope_confirmed_20261009.json', scope)
    print(json.dumps(dict(at=at, code=CODE, cases=list(cases), fixed_files=len(immutable), tests=55,
                         source_flags_models_unchanged_except_P5_P7r=True, model_imports_runs=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
