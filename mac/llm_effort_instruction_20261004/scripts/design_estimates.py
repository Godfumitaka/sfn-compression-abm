"""未実行の三案を、保存済みの使用量で較正して見積もる。API呼び出し0。"""
from common import *
import copy
import math
import re
import urllib.request
import memo as mm
import stage_d as sd
import world as w
import writeback as wb

def forbidden(*args, **kwargs):
    raise AssertionError('設計と見積もりではAPIを呼ばない')
urllib.request.urlopen = forbidden

baseline = read_rows(DEST / 'baseline/trials.jsonl')
import gzip
captured = [json.loads(x) for x in gzip.decompress((PREVIOUS / 'gate_after/S基準.requests.jsonl.gz').read_bytes()).splitlines()]
bodies = [json.loads(r['body_utf8']) for r in captured if r['url'].endswith('/messages')]
xs = [len(b['messages'][0]['content']) for b in bodies]
ys = [r['試み'][0]['使用量']['input_tokens'] for r in baseline]
assert len(xs) == len(ys) == 56
xbar, ybar = sum(xs) / 56, sum(ys) / 56
slope = sum((x-xbar)*(y-ybar) for x, y in zip(xs, ys)) / sum((x-xbar)**2 for x in xs)
intercept = ybar - slope*xbar
residuals = [y-(slope*x+intercept) for x, y in zip(xs, ys)]

def estimate_input(text):
    return max(0, math.ceil(slope*len(text)+intercept))

def cost(input_tokens, output_tokens):
    return (input_tokens*2 + output_tokens*10)/1000000

def scenario(calls, inputs, memo_outputs=0):
    # 予測のJSON25トークン。更新のJSONの包みも25を足す。推論は全要求に同じ仮定。
    low_out = 25*calls + memo_outputs + 100*calls
    high_out = 25*calls + memo_outputs + 2000*calls
    return {'calls': calls, 'input_tokens_estimate': inputs, 'memo_output_tokens_assumed': memo_outputs,
            'reasoning_100_per_call_dollars': cost(inputs, low_out),
            'reasoning_2000_per_call_dollars': cost(inputs, high_out),
            'output_limit_32000_per_call_dollars': cost(inputs, 32000*calls)}

memo_records = []
eligibility = {}
for world in (1, 2):
    st = w.make_set(1, world, 'v2', 1, True)
    assert all(s['research']['door_hidden'] for s in st['series'])
    eligibility[str(world)] = [wb.examples(st, t) for t in (10, 20, 30, 40)]
    for cond, limit in [('full', None), ('long', 1000), ('short', 150)]:
        inputs = 0
        predict_calls = update_calls = writeback_calls = 0
        for i, s in enumerate(st['series']):
            if cond == 'full':
                inputs += estimate_input(sd.prompt(st['series'][:i], s))
            else:
                inputs += estimate_input(mm.predict_prompt('', s['text'])) + (limit if i else 0)
                # 更新の形は別のJSON schema。上側に100トークンの余白を追加。
                inputs += estimate_input(mm.update_prompt('', s, limit)) + (limit if i else 0) + 100
                update_calls += 1
            predict_calls += 1
            t = i+1
            if t not in (10, 20, 30, 40):
                continue
            for q in st['tests']:
                inputs += estimate_input(sd.prompt(st['series'][:t], q)) if cond == 'full' else estimate_input(mm.predict_prompt('', q['text'])) + limit
                predict_calls += 1
            if cond == 'short':
                ex = wb.examples(st, t)
                if ex['実施']:
                    for kind in ('書き戻し', '対照'):
                        for q in st['tests']:
                            if q['kind'] != 'ドア':
                                continue
                            inputs += estimate_input(mm.predict_prompt(ex[kind], q['text'])) + limit
                            predict_calls += 1
                            writeback_calls += 1
        calls = predict_calls + update_calls
        memo_records.append({'world': world, 'condition': cond, 'memo_limit_provisional': limit,
                             'prediction_calls': predict_calls, 'update_calls': update_calls,
                             'writeback_and_control_calls': writeback_calls,
                             **scenario(calls, inputs, update_calls*(limit or 0))})

stimuli = json.loads((DEST / 'stimuli.json').read_text())
st = w.make_set(1, 2, 'v2')
tests = stimuli['tests']
voc = stimuli['vocab']
role_words = {voc['supported'], voc['carried']}
role_line = re.compile(r'^\s*r\d+: (?:' + '|'.join(sorted(role_words)) + r')\(o\d+\)$', re.M)
row_records = []
for label, add in [('0行', -1), ('今のまま', 0), ('増やす', 16)]:
    hist = copy.deepcopy(st['series'])
    qs = copy.deepcopy(tests)
    for s in hist + qs:
        original = s['text']
        assert len(role_line.findall(original)) == 1
        if add == -1:
            s['text'] = '\n'.join(line for line in original.splitlines() if not role_line.fullmatch(line))
        elif add > 0:
            used_r = set(re.findall(r'\br(\d+)\b', original))
            used_o = set(re.findall(r'\bo(\d+)\b', original))
            new_r = [r for r in range(10,100) if str(r) not in used_r][:add]
            new_o = next(o for o in range(1,10) if str(o) not in used_o)
            # 費用用の長さの代表。正式案の行順・番号は専用乱数で事前固定する。
            s['text'] += '\n' + '\n'.join(f'r{r}: zanu(o{new_o})' for r in new_r)
        assert s['text'].count('?') == 1
    input_sum = sum(estimate_input(sd.prompt(hist, q)) for q in qs)
    input_full_run = sum(estimate_input(sd.prompt(hist[:i], s)) for i, s in enumerate(hist)) + input_sum
    row_records.append({'condition': label, 'independent_root_lines': 0 if add == -1 else 1+add,
                        'scene_lines': len(qs[0]['text'].splitlines()),
                        'final16_only': scenario(16, input_sum),
                        'training40_plus_final16': scenario(56, input_full_run)})

meaning = {p: p for p in w.all_predicates()}
meaning.update({'govern': 'store', 'attach': 'has_sticker', 'sig_n': 'round_sticker', 'sig_e': 'square_sticker',
                'hold': 'red_door', 'hold_b': 'blue_door'})
assert len(set(meaning.values())) == len(meaning)
reverse = {symbol: meaning[p] for p, symbol in voc.items()}
def translate(text):
    return re.sub(r'\b(?:'+'|'.join(sorted(reverse))+r')\b', lambda m: reverse[m.group()], text)
hist_words = copy.deepcopy(st['series'])
test_words = copy.deepcopy(tests)
for s in hist_words + test_words:
    s['text'] = translate(s['text'])
    s['answer'] = reverse[s['answer']]
    assert s['text'].count('?') == 1
input_words = sum(estimate_input(sd.prompt(hist_words, q)) for q in test_words)
input_words_full = sum(estimate_input(sd.prompt(hist_words[:i], s)) for i, s in enumerate(hist_words)) + input_words
result = {'time': now(), 'API_calls': 0,
          'calibration': {'basis': '既存medium 0.5の56要求。入力tokens = slope×指示本文の文字数＋intercept',
                          'observations':56, 'slope':slope, 'intercept':intercept,
                          'max_absolute_residual':max(abs(r) for r in residuals),
                          'RMSE':math.sqrt(sum(r*r for r in residuals)/56),
                          'tokenizer_measurement':False,
                          'limitations':'新しい語彙・メモは未測定。費用の設計値であり、トークンAPIによる確定値や請求の保証ではない'},
          'output_assumptions': {'JSON_tokens':25, 'thinking_tokens_per_call':[100,2000],
                                 'memo_output_tokens':'更新ごとに仮の上限分を出すとして計算',
                                 'retry_included':False, 'additional_planning_margin':0.25},
          'memo': memo_records, 'writeback_eligibility':eligibility,
          'distractor_rows':row_records, 'meaning_words':{'mapping':meaning,
              'final16_only':scenario(16,input_words), 'training40_plus_final16':scenario(56,input_words_full)},
          'future_common_settings':{'model':MODEL, 'effort':'medium','thinking':'adaptive','display':'summarized',
                                    'instruction':OLD,'max_tokens':32000}}
save(DEST / 'design_estimates.json', result)
print(json.dumps({'API_calls':0,'memo_calls':sum(r['calls'] for r in memo_records),
                  'calibration_max_residual':result['calibration']['max_absolute_residual']},ensure_ascii=False))
