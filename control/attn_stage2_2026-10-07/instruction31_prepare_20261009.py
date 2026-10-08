"""指示31の命令を書き出す。模型・受付・監督を起動しない。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import copy
import hashlib
import importlib.util
import json
import subprocess

B = Path('/Users/tatsu-admin/Documents/ChatGPT/New project/codex_attn_2026-10-03')
S = B / 'stage2_attention_2026-10-08'
R = B / 'report'
P = R / 'control/attn_stage2_2026-10-07'
ROOT = Path(__file__).resolve().parent
L50 = '0.00035129738499384776'
E_PRICE = '0.01873710622997919'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    at = datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
    original = json.loads((P / 'instruction28_first_wave_commands_20261008.json').read_text())
    original_configs = json.loads((P / 'instruction28_first_wave_configurations_20261008.json').read_text())
    gate_path = S / 'instruction29_forget_parallel/p10_forget_exec_on_200_required_gate.json'
    gate = json.loads(gate_path.read_text())
    assert gate['passed'] and gate['trials'] == 200 and gate['code'] == original['sources']['4cea']['commit']
    assert gate['guard']['boundaries'] == 200 and gate['guard']['forbidden_reads'] == 0
    assert gate['guard']['native_loop_returned']
    # CLIの宣言だけを読む既存の道具。模型本体はimportしない。
    spec = importlib.util.spec_from_file_location('draft', S / 'instruction28_wave1_preparation/prepare.py')
    draft = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(draft)
    parsers = {}
    for version, source in original['sources'].items():
        path = Path(source['cwd'])
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=path, text=True).strip() == source['commit']
        assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=path, text=True).strip()
        assert digest(path / 'tools/v3_run.py') == source['cli_sha256']
        parsers[version] = draft.parser_from_source(path / 'tools/v3_run.py')

    configurations = {}
    artifacts = {}
    selected = {'1': '4cea', '2': 'e9', '3': '4cea', '4': '4cea', '5': 'e9', '6': '4cea', '7': '4cea'}
    for half, offset in [('a', 0), ('b', 10)]:
        plans = []
        for old in original['commands']:
            plan = copy.deepcopy(old)
            version = old['version']
            row = old['row'][0] + half
            seed = old['seed'] + offset
            world = old['world']
            argv = list(old['argv'])
            cfg = copy.deepcopy(original_configs['configurations'][argv[2]]['content'])
            cfg['seeds'] = {'count': 1, 'start': seed}
            relative_config = f'{version}/w{world}_seed{seed:03d}_config.json'
            cfg_path = ROOT / relative_config
            if relative_config not in configurations:
                write(cfg_path, cfg)
                configurations[relative_config] = {'content': cfg, 'sha256': digest(cfg_path)}
            else:
                assert configurations[relative_config]['content'] == cfg
            argv[2] = str(cfg_path)
            argv[3] = str(ROOT / 'outputs' / version / row / f'w{world}_seed{seed:03d}' / 'output')
            argv[argv.index('--seeds') + 1] = str(seed)
            argv[argv.index('--v39-price') + 1] = L50
            assert argv[argv.index('--e-price') + 1] == E_PRICE
            # 元の命令から変更するのは価格・指定の種・設定/出力の場所だけ。
            expected = list(old['argv'])
            expected[2:4] = argv[2:4]
            expected[expected.index('--seeds') + 1] = str(seed)
            expected[expected.index('--v39-price') + 1] = L50
            assert argv == expected
            args = parsers[version].parse_args(argv[2:])
            assert args.v39_price == float(L50) and args.e_price == float(E_PRICE)
            assert args.workers == 1 and args.trial_count == args.horizon == 1740
            assert args.seeds == str(seed) and args.shop_world == world
            assert args.h_dirichlet == 1 and args.birth_score == 'seq' and args.logp_eps == .01
            assert args.stage2_reuse == 'off' and args.sme_gc_threshold is None and not args.sme_fast_encode
            if row[0] == '2':
                assert args.stage2 == 'off' and args.stage2_loss == 'alpha' and args.stage2_init == 'A'
                assert not args.score_logp and not args.match_cstar and not args.match_cstar_e and not args.attn_allin
                assert not args.attn_sme and args.stage2_birth_hu == 'off'
            elif row[0] == '3':
                assert args.attn_fixed_zero
            elif row[0] == '4':
                assert args.stage2_scope == 'chosen'
            elif row[0] == '5':
                assert not args.match_cstar and not args.match_cstar_e
            elif row[0] == '6':
                assert not args.score_logp and args.stage2_loss == 'alpha' and args.attn_allin
            assert bool(args.no_forget_exec) == (row[0] == '7')
            if version == '4cea':
                optimized = row[0] not in ('2', '5')
                assert (args.stage2_speed == 'on') == optimized
                assert (args.stage2_cache_prune == 'on') == optimized
            portable = list(argv)
            portable[0] = '<PYTHON>'
            portable[2] = '<CONFIG_ROOT>/' + relative_config
            portable[3] = f'<OUTPUT_ROOT>/{version}/{row}/w{world}_seed{seed:03d}/output'
            plan.update(row=row, seed=seed, argv=argv, portable_argv=portable,
                        configuration_relative_path=relative_config,
                        configuration_sha256=configurations[relative_config]['sha256'],
                        command_ready=True, selected_for_use_by_instruction31=version == selected[row[0]],
                        mechanism_confirmation_first=half == 'a' and seed in (1, 2),
                        seeds_3_to_10_require_mechanism_confirmation=half == 'a' and seed > 2,
                        seeds_11_to_20_require_claude_mechanism_table_confirmation=half == 'b',
                        runnable=False, model_started=False,
                        blocked_by=['走行する機械での独立点検・列の取得と開始前確認',
                                    '種3以後は所定の種1・2の機構確認、種11〜20はClaudeの表の確認',
                                    '受付・資源・2026-10-11 09:00 JSTの期限'],
                        gate_evidence_for_version_selection=str(gate_path) if row[0] in ('1', '3', '4', '6') else '指示31の明示指定')
            plans.append(plan)
        assert len(plans) == 280
        assert len({(v['version'], v['row'], v['world'], v['seed']) for v in plans}) == 280
        assert sum(v['selected_for_use_by_instruction31'] for v in plans) == 140
        result = dict(instruction=31, at=at, half=half, seed_range=[1 + offset, 10 + offset],
                      L50_ref=L50, E_price=E_PRICE, sources=original['sources'],
                      commands=plans, command_count=280, selected_command_count=140,
                      selected_version_by_row={k + half: v for k, v in selected.items()},
                      all_configurations_in_separate_bundle=True,
                      portable_argv_requires_host_python_config_output_paths=True,
                      cli_declarations_checked_without_model_import=True,
                      price_authority='自分の受け箱 指示31（2026-10-09 03:32、Claude）',
                      forget_exec_gate_sha256=digest(gate_path),
                      production_started=False, new_models_receipts_controllers=0,
                      runnable_is_false_until_local_run_conditions_checked=True,
                      unused_versions_preserved_as_prepared_alternatives=True)
        target = P / f'instruction31_wave1_{half}_commands_20261009.json'
        write(ROOT / f'wave1_{half}_commands.json', result)
        write(target, result)
        artifacts[str(target.relative_to(R))] = {'sha256': digest(target), 'bytes': target.stat().st_size,
                                                'commands': 280, 'selected': 140}
    assert len(configurations) == 80
    configs_path = P / 'instruction31_wave1_configurations_20261009.json'
    write(configs_path, dict(instruction=31, at=at, configuration_count=80,
                            configurations=configurations, model_started=False))
    artifacts[str(configs_path.relative_to(R))] = {'sha256': digest(configs_path), 'bytes': configs_path.stat().st_size}
    write(P / 'instruction31_wave1_export_manifest_20261009.json',
          dict(at=at, instruction=31, artifacts=artifacts, command_count=560,
               selected_command_count=280, configuration_count=80,
               price_text_preserved=True, all_560_cli_declarations_checked=True,
               old_command_non_price_flags_unchanged=True, model_imports_or_runs=0,
               notes='portable_argvの三つの場所だけを実際の機械に割り当てる。数値・旗・順・設定は変更しない。'))
    print(json.dumps({'at': at, 'artifacts': artifacts, 'command_count': 560,
                      'configuration_count': 80, 'model_imports_or_runs': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
