"""指示32の実台本の開始前判定を、模型を起動せず確認する。"""
from pathlib import Path
import ast
import pytest

PACK = Path(__file__).resolve().parent.parent / 'instruction27'
RUNNERS = ['run_registered.py', 'run_registered21.py', 'run_registered22.py']


def actual_guards(name):
    tree = ast.parse((PACK / name).read_text())
    fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'registered')
    start = next(i for i, x in enumerate(fn.body) if isinstance(x, ast.Assign)
                 and isinstance(x.targets[0], ast.Name) and x.targets[0].id == 'dedicated_gcp')
    nodes = fn.body[start:start + 4]
    assert isinstance(nodes[-1], ast.Assert)
    return compile(ast.Module(body=nodes, type_ignores=[]), str(PACK / name), 'exec')


def evaluate(name, *, linux, marker, models, children, cpu, outside, unknown=0):
    ctx = dict(linux=linux, proof={'dedicated_google_cloud_gate_and_production_machine': marker},
               limit=cpu, counts=dict(model_process_count=models, outside_heavy=outside,
               unknown_active_spawn=unknown), children=children)
    exec(actual_guards(name), ctx)
    return ctx['model_limit']


@pytest.mark.parametrize('name', RUNNERS)
def test_dedicated_cloud_can_use_twenty_children_but_model_and_cpu_boundaries_remain(name):
    assert evaluate(name, linux=True, marker=True, models=41, children=20, cpu=62, outside=40) == 62
    with pytest.raises(AssertionError):
        evaluate(name, linux=True, marker=True, models=42, children=20, cpu=62, outside=40)
    with pytest.raises(AssertionError):
        evaluate(name, linux=True, marker=True, models=20, children=20, cpu=62, outside=41)
    with pytest.raises(AssertionError):
        evaluate(name, linux=True, marker=True, models=20, children=20, cpu=62, outside=20, unknown=1)


@pytest.mark.parametrize('name', RUNNERS)
def test_mac_and_unconfirmed_or_other_cloud_still_use_eight(name):
    for linux, marker in [(False, True), (True, False), (True, None), (True, 'true'), (True, 1)]:
        assert evaluate(name, linux=linux, marker=marker, models=7, children=0, cpu=62, outside=1) == 8
        with pytest.raises(AssertionError):
            evaluate(name, linux=linux, marker=marker, models=8, children=0, cpu=62, outside=1)


@pytest.mark.parametrize('name', RUNNERS)
def test_existing_admission_and_same_machine_gates_stay_before_spawn(name):
    s = (PACK / name).read_text()
    spawn = s.index('child = subprocess.Popen')
    for guard in ["proof['memory_admission_ok']", "proof['swap_stable_10min']", "proof['thermal_ok']",
                  "limit == proof['physical_cpu_count']-2", "counts['unknown_active_spawn'] == 0",
                  'free >= 20*2**30', "spec['ready_to_start'] is True", "claim['normal_push_succeeded']"]:
        assert s.index(guard) < spawn
    assert 'SIGSTOP' not in s and 'SIGCONT' not in s and 'killpg' not in s
