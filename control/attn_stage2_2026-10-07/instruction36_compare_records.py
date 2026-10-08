"""模型の原バイトを流し、指定された時間値だけを同じ印にする。"""
from pathlib import Path
import gzip
import hashlib
import json
import re

TIMING = frozenset(('seconds', 'wrapper_seconds', 'engine_seconds', 'measure_seconds',
                    'rematch_fraction_of_stage2_seconds'))
KEY = re.compile(rb'"(?:[^"\\]|\\.)*"\s*:')
LITERAL = re.compile(rb'(?:-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|null)')


def time_values(data):
    # 再直列化しない。語順、空白、数の表記、非時間のバイトは全て残す。
    spans = []
    for match in KEY.finditer(data):
        token = match.group().rstrip()[:-1].rstrip()
        if json.loads(token) not in TIMING:
            continue
        start = match.end()
        while start < len(data) and data[start:start+1] in b' \t\r\n':
            start += 1
        value = LITERAL.match(data, start)
        if value is None or (value.end() < len(data) and data[value.end():value.end()+1] not in b',} \r\n\t]'):
            raise RuntimeError('時間欄が既知の数又はnullでない')
        spans.append((start, value.end()))
    result = bytearray(); before = 0
    for start, end in spans:
        result.extend(data[before:start]); result.extend(b'0'); before = end
    result.extend(data[before:])
    return bytes(result)


def opening(path):
    return gzip.open(path, 'rb') if path.suffix == '.gz' else path.open('rb')


def chunks(path, ledger=False, timings=False):
    with opening(path) as stream:
        if ledger:
            header = stream.readline()
            if json.loads(header).get('record_type') != 'run_header':
                raise RuntimeError(('台帳の先頭が見出しでない', str(path)))
        if timings:
            for line in stream:
                yield time_values(line)
        else:
            while block := stream.read(2**20):
                yield block


def compare(left, right, ledger=False, timings=False):
    # 行・gzip境界によらず、最後の一バイトまで同じ流れにそろえる。
    def blocked(path):
        buffer = bytearray()
        for block in chunks(path, ledger, timings):
            buffer.extend(block)
            while len(buffer) >= 2**20:
                yield bytes(buffer[:2**20]); del buffer[:2**20]
        if buffer:
            yield bytes(buffer)
    a, b = iter(blocked(left)), iter(blocked(right))
    digest = hashlib.sha256(); length = offset = 0
    while True:
        x, y = next(a, None), next(b, None)
        if x != y:
            raise RuntimeError(('非時間のバイト不一致', str(left), str(right), offset))
        if x is None:
            break
        digest.update(x); length += len(x); offset += len(x)
    return dict(passed=True, compared_bytes=length, sha256=digest.hexdigest(),
                time_value_keys=sorted(TIMING) if timings else [],
                ledger_header_excluded=ledger)


def files(root):
    return {str(p.relative_to(root / 'output')):p
            for category in ('ledgers', 'side', 'attention', 'stage2', 'researcher', 'evictions')
            for p in (root / 'output' / category).rglob('*')
            if p.is_file() and p.suffix != '.done'}


def manifest_counters(left, right):
    # 付帯の版・圧縮長等とは別に、漏れを含むstrictpcを丸ごと順つきで比べる。
    decoder = json.JSONDecoder()
    def counter_bytes(root):
        data = (root / 'output/manifest.jsonl').read_bytes()
        for match in KEY.finditer(data):
            if json.loads(match.group().rstrip()[:-1].rstrip()) == 'strictpc':
                start = match.end()
                while data[start:start+1] in b' \t\r\n': start += 1
                text = data[start:].decode()
                _, end = decoder.raw_decode(text)
                return text[:end].encode()
        raise RuntimeError('manifestのstrictpcが無い')
    a,b = counter_bytes(left),counter_bytes(right)
    if a != b: raise RuntimeError('strictpcの入れ子Counterを含む記録が不一致')
    return dict(passed=True, bytes=len(a), sha256=hashlib.sha256(a).hexdigest())


def tree(left, right, trials, observer):
    lf,rf = files(left),files(right)
    if lf.keys() != rf.keys():
        raise RuntimeError(('模型の全ファイル集合が違う', sorted(lf.keys() ^ rf.keys())))
    records = []
    for name in sorted(lf):
        ledger = name.startswith('ledgers/')
        timing = name.startswith('stage2/')
        records.append(dict(file=name, **compare(lf[name],rf[name],ledger,timing)))
    if observer:
        for name in ('tie_state.jsonl','saved_matcher.jsonl.gz'):
            records.append(dict(file=name, **compare(left / name,right / name)))
    ledgers = [p for name,p in rf.items() if name.startswith('ledgers/')]
    if len(ledgers) != 1: raise RuntimeError('台帳の本数が一でない')
    with opening(ledgers[0]) as stream:
        if sum(1 for _ in stream)-1 != trials: raise RuntimeError('台帳の試行数不足')
    required = [name for name in lf if name.startswith(('ledgers/','side/'))]
    if len(required) < 7 or not any(n.endswith('sme.states.jsonl.gz') for n in required):
        raise RuntimeError('所定の台帳・全side・順つき保存状態が無い')
    return dict(passed=True, trials=trials, records=records,
                strictpc_counter=manifest_counters(left,right),
                observation_cache_comparison='原全バイト・順つき' if observer else '元走行に追加控えの観測無し',
                model_time_values_only_normalized=True,
                provenance_files=['output/flag.json','output/manifest.jsonl（strictpcは別に比較）','*.done'],
                reference_not_rerun=True, adoption_decided=False)
