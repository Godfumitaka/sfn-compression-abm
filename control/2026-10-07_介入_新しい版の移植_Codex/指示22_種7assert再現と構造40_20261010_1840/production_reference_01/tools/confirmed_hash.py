"""確定済み原行を写さずに読む。模型・乱数・原ファイルは変更しない。"""
from pathlib import Path
import hashlib, zlib

CHUNK_BYTES = 1024 * 1024

def hash_confirmed(path):
    path = Path(path)
    digest = hashlib.sha256()
    size = lines = 0
    last = b''
    decoder = zlib.decompressobj(31) if path.suffix == '.gz' else None
    with path.open('rb') as stream:
        while raw := stream.read(CHUNK_BYTES):
            if decoder is None:
                pieces = (raw,)
            else:
                def decompressed(block):
                    nonlocal decoder
                    pending = block
                    while True:
                        if decoder.eof:
                            decoder = zlib.decompressobj(31)
                        data = decoder.decompress(pending, CHUNK_BYTES)
                        pending = decoder.unused_data if decoder.eof else decoder.unconsumed_tail
                        if data:
                            yield data
                        if decoder.eof:
                            if pending:
                                continue
                            break
                        if not pending and len(data) < CHUNK_BYTES:
                            break
                pieces = decompressed(raw)
            for data in pieces:
                digest.update(data)
                size += len(data)
                lines += data.count(b'\n')
                last = data[-1:]
    assert not size or last == b'\n', '確定前の行を補わない'
    return dict(sha256=digest.hexdigest(), bytes=size, lines=lines)
