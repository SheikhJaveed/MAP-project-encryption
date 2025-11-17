import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from .aes_core import (
    chunkify,
    encrypt_chunk_ecb,
    encrypt_chunk_ctr_with_counter,
    decrypt_chunk_ecb,
    decrypt_chunk_ctr_with_counter,
)

def encrypt_parallel(data: bytes, key: bytes, mode: str, workers: int):
    """
    Returns (encrypted_bytes, elapsed_time)
    For ECB: we need to pad data to multiple of block size BEFORE chunking.
    For CTR: we compute per-chunk counters and do parallel CTR encryption.
    """
    start_total = time.perf_counter()
    if mode == "ECB":
        # pad so that every chunk is block-aligned
        from .aes_core import pad
        data_padded = pad(data)
        chunks = chunkify(data_padded, workers)
        results = [None] * len(chunks)
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(encrypt_chunk_ecb, chunks[i], key): i for i in range(len(chunks))}
            for fut in as_completed(futures):
                i = futures[fut]
                results[i] = fut.result()
        encrypted = b"".join(results)
    elif mode == "CTR":
        # CTR: choose a single nonce, compute starting counter for each chunk
        from .aes_core import chunkify
        nonce = os.urandom(8)
        chunks = chunkify(data, workers)
        # compute initial counter for each chunk (in blocks)
        offsets = []
        cur = 0
        for c in chunks:
            offsets.append(cur // 16)
            cur += len(c)
        results = [None] * len(chunks)
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(encrypt_chunk_ctr_with_counter, chunks[i], key, nonce, offsets[i]): i
                for i in range(len(chunks))
            }
            for fut in as_completed(futures):
                i = futures[fut]
                results[i] = fut.result()
        # prefix nonce so decryptor can use same nonce
        encrypted = nonce + b"".join(results)
    else:
        raise ValueError("Parallel encryption only supports ECB and CTR in this framework.")
    end_total = time.perf_counter()
    return encrypted, end_total - start_total

def decrypt_parallel(encrypted: bytes, key: bytes, mode: str, workers: int):
    start_total = time.perf_counter()
    if mode == "ECB":
        chunks = chunkify(encrypted, workers)
        results = [None] * len(chunks)
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(decrypt_chunk_ecb, chunks[i], key): i for i in range(len(chunks))}
            for fut in as_completed(futures):
                i = futures[fut]
                results[i] = fut.result()
        decrypted = b"".join(results)
    elif mode == "CTR":
        nonce = encrypted[:8]
        body = encrypted[8:]
        chunks = chunkify(body, workers)
        offsets = []
        cur = 0
        for c in chunks:
            offsets.append(cur // 16)
            cur += len(c)
        results = [None] * len(chunks)
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(decrypt_chunk_ctr_with_counter, chunks[i], key, nonce, offsets[i]): i
                for i in range(len(chunks))
            }
            for fut in as_completed(futures):
                i = futures[fut]
                results[i] = fut.result()
        decrypted = b"".join(results)
    else:
        raise ValueError("Parallel decryption only supports ECB and CTR in this framework.")
    end_total = time.perf_counter()
    return decrypted, end_total - start_total
