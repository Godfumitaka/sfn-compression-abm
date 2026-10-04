"""固定16問だけを実行し、既存の費用帳簿へ追記する。"""
from common import *
import fcntl
import os
import time
import urllib.error
import urllib.request
import api
import memo as mm
import stage4 as s4

label = sys.argv[1]
assert label in ('A', 'B')
out = DEST / label
planned = read_rows(out / 'planned_requests.jsonl')
stimuli = json.loads((DEST / 'stimuli.json').read_text())
assert len(planned) == 16 and os.environ.get('ANTHROPIC_API_KEY')
assert not (out / 'requests.jsonl').exists(), '走行済みか未確定の要求を再送しない'
api.set_ledger(str(LEDGER))
api.LIMIT = 4.0
api.spent = lambda: float(known_spent())
mm.MODEL[0] = MODEL
mm.EFFORT[0] = 'medium' if label == 'A' else 'max'
mm.DISPLAY[0] = 'summarized'
current = {'q': None, 'attempt': 0, 'reservation': None}

def event(value):
    append(out / 'budget_events.jsonl', {'time': now(), **value})

def guarded_post(url, body, headers, timeout=600):
    assert url == 'https://api.anthropic.com/v1/messages', '試験以外のAPIを禁止'
    assert body['model'] == MODEL
    q = current['q']
    current['attempt'] += 1
    attempt = current['attempt']
    expected = json.loads(json.dumps(planned[q]['body']))
    if attempt > 1:
        expected['messages'][0]['content'] += '\n' + s4.STRICT
    assert body == expected, '指定以外の変更がある'
    raw = json.dumps(body).encode()
    # 前担当と同じ入力の上側の確保。出力は32000全てを確保する。
    maximum = (Decimal(len(raw) * 4 + 4096) * Decimal('2') + Decimal(body['max_tokens']) * Decimal('10')) / Decimal(1000000)
    assert current['reservation'] is None
    if known_spent() + maximum > CAP:
        raise api.Budget('次の要求の最大費用を確保すると今回の4ドルを超える')
    reservation = {'q': q, 'attempt': attempt, 'maximum_dollars': str(maximum), 'status': 'pending'}
    current['reservation'] = reservation
    event({'event': 'reserve', 'reservation': reservation, 'known_dollars': str(known_spent())})
    append(out / 'requests.jsonl', {'time': now(), 'q': q, 'attempt': attempt, 'url': url,
                                  'body_utf8': raw.decode(), 'body_sha256': sha(raw)})
    request = urllib.request.Request(url, data=raw, headers={**headers, 'User-Agent': api.UA, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            r = json.load(response)
            reservation.update(status='response_received', http_status=response.status)
    except Exception as error:
        reservation.update(status='uncertain', error_type=type(error).__name__)
        if isinstance(error, urllib.error.HTTPError):
            reservation['http_status'] = error.code
        event({'event': 'stop_without_transport_retry', 'reservation': reservation})
        raise
    save(out / 'responses' / f'q{q:02d}_try{attempt}.json', r)
    assert r.get('model') == MODEL, '応答の模型が指定と異なる'
    u = r.get('usage') or {}
    assert isinstance(u.get('input_tokens'), int) and isinstance(u.get('output_tokens'), int)
    assert not u.get('cache_creation_input_tokens') and not u.get('cache_read_input_tokens')
    assert u['input_tokens'] <= len(raw) * 4 + 4096 and u['output_tokens'] <= body['max_tokens']
    return r

def guarded_book(model, usage_in, usage_out, price, what):
    reservation = current['reservation']
    assert model == MODEL and price == {'input': 2.0, 'output': 10.0}
    assert reservation and reservation['status'] == 'response_received'
    cost = (Decimal(usage_in) * 2 + Decimal(usage_out) * 10) / Decimal(1000000)
    assert cost <= Decimal(reservation['maximum_dollars']) and known_spent() + cost <= CAP
    row = {'t': time.strftime('%H:%M:%S'), 'model': model, 'in': usage_in, 'out': usage_out,
           'cost': float(cost), 'what': what}
    # 既存と同じ欄を、排他ロックを取って末尾へ追加する。
    data = (json.dumps(row, ensure_ascii=False) + '\n').encode()
    fd = os.open(LEDGER, os.O_WRONLY | os.O_APPEND)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert os.write(fd, data) == len(data)
    finally:
        os.close(fd)
    append(out / 'ledger_rows.jsonl', row)
    reservation.update(status='booked', actual_dollars=str(cost))
    event({'event': 'booked', 'reservation': reservation, 'known_dollars': str(known_spent())})
    current['reservation'] = None
    return float(cost)

api._post = guarded_post
api._book = guarded_book
save(out / 'run.json', {'start': now(), 'condition': label, 'task_dollars_before': str(known_spent()),
     'training_calls': 0, 'transport_retry': False,
     'format_retry': '既存と同じ初回＋最大2回。上限切れは再試行しない'})
try:
    for q, t in enumerate(stimuli['tests']):
        current.update(q=q, attempt=0)
        row = mm.predict(planned[q]['body']['messages'][0]['content'], t['answer'], f'{PREFIX} {label} 試験 {q}')
        row.update({'段': '最後の試験', 'i': q, '場合': t['case'], 'condition': label})
        append(out / 'trials.jsonl', row)
        print(json.dumps({'time': now(), 'condition': label, 'q': q, 'completed': q + 1,
                          'task_dollars': str(known_spent())}, ensure_ascii=False), flush=True)
    assert current['reservation'] is None
    save(out / 'finished.json', {'time': now(), 'complete': True, 'questions': 16, 'task_dollars': str(known_spent())})
except Exception as error:
    # エラー本文に鍵やヘッダを出さない。
    result = {'time': now(), 'complete': False, 'error_type': type(error).__name__,
              'task_dollars': str(known_spent()), 'reservation': current['reservation']}
    save(out / 'stopped.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    raise SystemExit(1)
