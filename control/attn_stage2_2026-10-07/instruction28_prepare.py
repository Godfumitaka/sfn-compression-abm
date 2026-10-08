"""指示28の命令の下書き。模型・受付・監督を起動しない。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import ast
import copy
import hashlib
import json
import subprocess

B = Path('/Users/tatsu-admin/Documents/ChatGPT/New project/codex_attn_2026-10-03')
S = B / 'stage2_attention_2026-10-08'
R = B / 'report'
P = R / 'control/attn_stage2_2026-10-07'
ROOT = Path(__file__).resolve().parent
TEMPLATE = S / 'instruction19_speed_gate/first_wave_command_preparation/w2_seed001'
VERSIONS = {
    'e9': (B / 'cstar_stage2_preparation_source', 'e9ed84ae3ee6c458f392cd58cadf9fc030639900'),
    '4cea': (B / 'cstar_stage2_cache_prune_source', '4ceadf63f6924bdab8013d3e39b1549a8c5c0966'),
}
ROWS = {'1a': '全部入り', '2a': '基準', '3a': '注意を外す',
        '4a': '第二段をCに', '5a': 'C*を外す', '6a': 'log Pを外す',
        '7a': '名前の忘却なし'}
L50 = '<L50_ref未確定>'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def set_value(command, flag, value):
    i = command.index(flag)
    command[i + 1] = value


def remove(command, flag, valued=False):
    i = command.index(flag)
    del command[i:i + (2 if valued else 1)]


def parser_from_source(path):
    # 元のCLI宣言だけを読む。mainや模型のimport・本体は実行しない。
    tree = ast.parse(path.read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    declarations = []
    for n in main.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'args' for t in n.targets):
            break
        declarations.append(n)
    assert all(isinstance(n, ast.Assign) or
               (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and
                isinstance(n.value.func, ast.Attribute) and n.value.func.attr == 'add_argument')
               for n in declarations)
    namespace = {'argparse': argparse}
    exec(compile(ast.Module(body=declarations, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['ap']


def main():
    at = datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
    template = json.loads((TEMPLATE / 'native_command_draft.json').read_text())
    config = json.loads((TEMPLATE / 'config.json').read_text())
    assert template[template.index('--v39-price') + 1] == L50
    assert '--no-forget-exec' not in template
    # 細部未確定の数値を保存済み命令へ埋めず、CLIの型確認時だけ一時的に0へ置換する。
    plans = []
    sources = {}
    for version, (source, commit) in VERSIONS.items():
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
        status = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=source, text=True).strip()
        assert head == commit and not status
        parser = parser_from_source(source / 'tools/v3_run.py')
        sources[version] = dict(commit=commit, cwd=str(source), cli_sha256=hashlib.sha256((source / 'tools/v3_run.py').read_bytes()).hexdigest())
        for seed in range(1, 11):
            for world in (1, 2):
                cfg = copy.deepcopy(config)
                cfg['seeds'] = dict(count=1, start=seed)
                cfg_path = ROOT / version / f'w{world}_seed{seed:03d}_config.json'
                write(cfg_path, cfg)
                for row, label in ROWS.items():
                    command = list(template)
                    command[2] = str(cfg_path)
                    command[3] = str(ROOT / version / row / f'w{world}_seed{seed:03d}' / 'output')
                    set_value(command, '--shop-world', str(world))
                    set_value(command, '--seeds', str(seed))
                    if row == '2a':
                        for flag in ('--score-logp', '--match-cstar', '--match-cstar-e', '--attn-allin'):
                            remove(command, flag)
                        for flag in ('--attn-sme', '--attn-position', '--attn-eta'):
                            remove(command, flag, True)
                        set_value(command, '--stage2', 'off')
                        set_value(command, '--stage2-loss', 'alpha')
                        set_value(command, '--stage2-init', 'A')
                        set_value(command, '--stage2-birth-hu', 'off')
                    elif row == '3a':
                        command.append('--attn-fixed-zero')
                    elif row == '4a':
                        set_value(command, '--stage2-scope', 'chosen')
                    elif row == '5a':
                        remove(command, '--match-cstar')
                        remove(command, '--match-cstar-e')
                    elif row == '6a':
                        remove(command, '--score-logp')
                        set_value(command, '--stage2-loss', 'alpha')
                    elif row == '7a':
                        command.append('--no-forget-exec')
                    optimized = version == '4cea' and row not in ('2a', '5a')
                    if version == '4cea':
                        command.extend(['--stage2-speed', 'on' if optimized else 'off',
                                        '--stage2-cache-prune', 'on' if optimized else 'off'])
                    temporary = list(command[2:])
                    temporary[temporary.index('--v39-price') + 1] = '0'
                    args = parser.parse_args(temporary)
                    assert args.workers == 1 and args.trial_count == args.horizon == 1740
                    assert args.e_price == float(template[template.index('--e-price') + 1])
                    assert args.h_dirichlet == 1 and args.birth_score == 'seq' and args.logp_eps == .01
                    if args.stage2 == 'on':
                        assert args.attn_sme and args.v310_be
                    if optimized:
                        assert args.stage2 == 'on' and args.attn_allin and args.match_cstar and args.sme_call_seed
                    assert (args.no_forget_exec is True) == (row == '7a')
                    assert command[command.index('--v39-price') + 1] == L50
                    plans.append(dict(version=version, commit=commit, cwd=str(source), row=row,
                        configuration=label, world=world, seed=seed,
                        environment={'PYTHONHASHSEED': '0'}, argv=command,
                        source_of_configuration='走行の列1a〜7aと承認済み走行計画の機構の軸',
                        speed_and_prune_enabled=optimized,
                        speed_disabled_reason='第二段off又はC*offは高速化onのCLI条件外' if version == '4cea' and not optimized else None,
                        mechanism_confirmation_first=seed in (1, 2),
                        seeds_3_to_10_require_mechanism_confirmation=seed > 2,
                        runnable=False, model_started=False,
                        blocked_by=['L50_refの所定16本集計', '該当条件の全関門と独立点検',
                                    'Claudeによる列の版・旗・出力先と未着手の確定',
                                    '開始直前の受付・資源・期限条件']))
    assert len(plans) == 280
    assert len({(x['version'], x['row'], x['world'], x['seed']) for x in plans}) == 280
    result = dict(instruction=28, at=at, sources=sources, commands=plans,
        command_count=280, configuration_count=40, L50_ref_filled=False,
        cli_declarations_checked_without_model_import=True,
        numerical_zero_used_only_in_unsaved_cli_type_check=True,
        production_started=False, models_receipts_or_controllers_started=0,
        running_sources_or_tools_modified=False,
        row2_note='注意なし・第二段offの既存A・旧照合・0/ℓ。HのDirichletと誕生seqは保持。出生HU旗は第二段offなのでoff。',
        row6_note='注意/C*は維持し、保持の採点旗を外し第二段の損をalpha（0/ℓ）にする。',
        row7_note='価格欄は共通L50_refの未確定のまま、no-forget-execで実変換を止める。',
        new_flags_not_assumed_gated_for_ablations=True)
    write(ROOT / 'first_wave_commands.json', result)
    write(P / 'instruction28_first_wave_commands_20261008.json', result)
    print(json.dumps({k: result[k] for k in ('at', 'command_count', 'configuration_count', 'L50_ref_filled', 'production_started')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
