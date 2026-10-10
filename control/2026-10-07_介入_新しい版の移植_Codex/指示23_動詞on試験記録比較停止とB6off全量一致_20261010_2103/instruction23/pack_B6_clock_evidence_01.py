"""全欄の原値を残し、完了済み比較の時計根拠を可逆圧縮する。"""
from pathlib import Path
import datetime
import gzip
import hashlib
import json
import resource
import time

here = Path(__file__).resolve().parent
source = here/'B6_after_end_01/comparison_excluded_fields_01.json'
destination = here/'B6_after_end_01/comparison_excluded_fields_01.json.gz'
result_path = here/'B6_after_end_01/clock_evidence_compression_01.json'
assert not destination.exists() and not result_path.exists()
started = time.perf_counter()

def digest(stream):
    value = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        value.update(chunk)
    return value.hexdigest()

with source.open('rb') as stream:
    before = digest(stream)
with source.open('rb') as stream, destination.open('xb') as output:
    with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as compressed:
        while chunk := stream.read(1024 * 1024):
            compressed.write(chunk)
with gzip.open(destination, 'rb') as stream:
    unpacked = digest(stream)
with source.open('rb') as stream:
    after = digest(stream)
assert before == unpacked == after
with destination.open('rb') as stream:
    compressed_digest = digest(stream)
result = dict(at_jst=datetime.datetime.now().astimezone().isoformat(),
    passed=True, source=str(source), source_bytes=source.stat().st_size,
    source_sha256=before, decompressed_sha256=unpacked, source_after_sha256=after,
    compressed=str(destination), compressed_bytes=destination.stat().st_size,
    compressed_sha256=compressed_digest, all_fields_and_original_values_preserved=True,
    comparison_rerun=False, model_rerun=False, seconds=time.perf_counter()-started,
    max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
with result_path.open('x') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
print(json.dumps(result, ensure_ascii=False))
