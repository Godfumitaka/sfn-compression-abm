"""APIを呼ばず、既存の履歴・試験・要求本体と変更範囲を照合する。"""
from common import *
import copy
import gzip
import subprocess
import urllib.request
import api
import stage_d as sd
import world as w

def forbidden(*args, **kwargs):
    raise AssertionError('準備ではAPIを呼ばない')
urllib.request.urlopen = forbidden

assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip() == SOURCE_COMMIT
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=SOURCE, text=True).strip()
assert not DEST.exists(), '既存の試験記録を上書きしない'
DEST.mkdir(parents=True)
st = w.make_set(1, 2, 'v2', 1, False)
_, tests = sd.build(1, 2, 4)
baseline_path = PREVIOUS / 'baselines/段階S基準_w2.jsonl'
all_baseline = read_rows(baseline_path)
baseline = [r for r in all_baseline if r['段'] == '最後の試験']
assert len(st['series']) == 40 and sum(s['research']['door_hidden'] for s in st['series']) == 20
assert len(baseline) == len(tests) == 16
assert [r['i'] for r in baseline] == list(range(16))
captured_path = PREVIOUS / 'gate_after/S基準.requests.jsonl.gz'
captured = [json.loads(line) for line in gzip.decompress(captured_path.read_bytes()).splitlines()]
bodies = [json.loads(r['body_utf8']) for r in captured if r['url'].endswith('/messages')]
assert len(bodies) == 56
assert [sd.prompt(st['series'][:i], s) for i, s in enumerate(st['series'])] == [b['messages'][0]['content'] for b in bodies[:40]]
checks = []
for q, (t, r, b) in enumerate(zip(tests, baseline, bodies[40:])):
    assert r['正解'] == t['answer'] and r['場合'] == t['case']
    assert b['messages'] == [{'role': 'user', 'content': sd.prompt(st['series'], t)}]
    assert b['model'] == MODEL and b['max_tokens'] == 32000
    assert b['thinking'] == {'type': 'adaptive', 'display': 'summarized'}
    assert b['output_config'] == {'format': {'type': 'json_schema', 'schema': sd.SCHEMA}, 'effort': 'medium'}
    assert len(r['試み']) == 1
    text = b['messages'][0]['content']
    assert text.count(OLD) == 1 and text.endswith(OLD)
    a = copy.deepcopy(b)
    a['messages'][0]['content'] = text[:-len(OLD)] + NEW
    back = copy.deepcopy(a)
    back['messages'][0]['content'] = back['messages'][0]['content'][:-len(NEW)] + OLD
    assert back == b
    other = copy.deepcopy(b)
    other['output_config']['effort'] = 'max'
    back_b = copy.deepcopy(other)
    back_b['output_config']['effort'] = 'medium'
    assert back_b == b
    for label, body in [('baseline', b), ('A', a), ('B', other)]:
        raw = json.dumps(body).encode()
        append(DEST / label / 'planned_requests.jsonl', {'q': q, 'case': t['case'], 'body': body, 'body_utf8': raw.decode(), 'body_sha256': sha(raw)})
    checks.append({'q': q, 'case': t['case'], 'history_and_question_identical': True,
                   'A_only_final_sentence': True, 'B_only_effort': True,
                   'baseline_body_sha256': sha(json.dumps(b).encode())})
save(DEST / 'stimuli.json', {'history': st['series'], 'tests': tests, 'vocab': st['vocab']})
(DEST / 'baseline/trials.jsonl').write_bytes(baseline_path.read_bytes())
ledger_raw = LEDGER.read_bytes()
save(DEST / 'ledger_before.json', {'time': now(), 'path': str(LEDGER), 'bytes': len(ledger_raw),
     'sha256': sha(ledger_raw), 'rows': len(ledger_raw.splitlines()), 'task_limit_dollars': 4,
     'existing_total_dollars': str(sum((Decimal(str(json.loads(x)['cost'])) for x in ledger_raw.splitlines()), Decimal(0)))})
save(DEST / 'offline_checks.json', {'time': now(), 'API_calls': 0, 'checks': checks,
     'source_commit': SOURCE_COMMIT, 'source_clean': True, 'baseline_rows_sha256': sha(baseline_path.read_bytes()),
     'capture_sha256': sha(captured_path.read_bytes()), 'history_scenes': 40, 'door_hidden_scenes': 20,
     'tests': 16, 'source_files': {str(p.relative_to(SOURCE)): sha(p.read_bytes()) for p in sorted((SOURCE / 'llm_trial').glob('*.py'))}})
save(DEST / 'scope.json', {'date': '2026-10-04', 'model': MODEL, 'world': 2, 'set_seed': 1,
     'door_fraction': 0.5, 'run_training': False, 'tests_per_condition': 16, 'thinking': 'adaptive',
     'display': 'summarized', 'max_tokens': 32000, 'format': sd.SCHEMA, 'task_limit_dollars': 4,
     'A': {'effort': 'medium', 'replace_from': OLD, 'replace_to': NEW},
     'B': {'effort': 'max', 'instruction': OLD}, 'ledger': str(LEDGER),
     'pricing': api.CLAUDE_PRICE[MODEL], 'pricing_source': 'https://platform.claude.com/docs/en/about-claude/pricing',
     'effort_source': 'https://platform.claude.com/docs/en/build-with-claude/effort',
     'thinking_source': 'https://platform.claude.com/docs/en/build-with-claude/thinking-steering-and-cost',
     'summary_matching': {'case_sensitive': True, 'word_boundary': 'ASCII英数字と下線を記号の前後に許さない',
                          'count': '各問の最終試みのsummarized欄だけ。今のシールの語と通常・例外いずれかの語を別々に数える'}})
print(json.dumps({'API_calls': 0, 'checks': len(checks), 'prepared': str(DEST)}, ensure_ascii=False))
