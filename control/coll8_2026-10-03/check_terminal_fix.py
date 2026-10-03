"""終了処理修正の検査結果と、模型の計算部分が不変である証拠を保存する。"""
from pathlib import Path
import ast, json, subprocess

root = Path(__file__).resolve().parent
source = root / 'source'
ev = root / 'evidence'
before = subprocess.check_output(['git', 'show', '93c5dd6:tools/v311c.py'], cwd=source, text=True)
after = (source / 'tools/v311c.py').read_text()

def calculations(text):
    tree = ast.parse(text)
    tree.body = [node for node in tree.body
                 if not (isinstance(node, ast.FunctionDef) and node.name == '_agent_main')]
    return ast.dump(tree, include_attributes=False)

unchanged = not subprocess.check_output(['git', 'diff', '93c5dd6', '--', 'abm/',
    'tools/v3_run.py', 'tools/v311c_lineage.py', 'config/'], cwd=source)
proof = {'comparison_commit': '93c5dd6', 'other_model_files_unchanged': unchanged,
         'v311c_except_agent_main_ast_identical': calculations(before) == calculations(after)}
(ev / 'terminal-fix-model-proof.json').write_text(json.dumps(proof, indent=1) + '\n')
(ev / 'terminal-fix-code.diff').write_bytes(subprocess.check_output(
    ['git', 'diff', '93c5dd6', '--', 'tools/v311c.py'], cwd=source))
assert all(proof[key] for key in ('other_model_files_unchanged', 'v311c_except_agent_main_ast_identical'))
files = [row['file'] for row in json.loads((ev / 'previous-unit-suite-isolated.json').read_text())]
files += ['test_v311c_terminal.py']
results = []
for file in files:
    argv = ['/opt/homebrew/bin/uv', 'run', '--offline', '--no-project', '--python',
        '/opt/homebrew/opt/python@3.12/bin/python3.12', '--with', 'pytest==9.1.1',
        'python', '-m', 'pytest', '-q', 'tests/' + file]
    p = subprocess.run(argv, cwd=source, text=True, capture_output=True)
    results.append({'file': file, 'argv': argv, 'returncode': p.returncode, 'output': p.stdout+p.stderr})
    (ev / 'terminal-fix-unit-suite.json').write_text(json.dumps(results, ensure_ascii=False, indent=1)+'\n')
    print(file, p.returncode, p.stdout.strip().splitlines()[-1], flush=True)
    assert p.returncode == 0
