import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple
from Crypto.Random import get_random_bytes

from .aes_core import (
    pad, BLOCK,
    encrypt_chunk_ecb, decrypt_chunk_ecb,
    encrypt_chunk_ctr_with_counter, decrypt_chunk_ctr_with_counter
)

# -----------------------------------------
# Worker functions
# -----------------------------------------
def task_ecb_encrypt(idx, chunk, key):
    return idx, encrypt_chunk_ecb(chunk, key)

def task_ctr_encrypt(idx, chunk, key, nonce, init_ctr):
    return idx, encrypt_chunk_ctr_with_counter(chunk, key, nonce, init_ctr)

def task_ecb_decrypt(idx, chunk, key):
    return idx, decrypt_chunk_ecb(chunk, key)

def task_ctr_decrypt(idx, chunk, key, nonce, init_ctr):
    return idx, decrypt_chunk_ctr_with_counter(chunk, key, nonce, init_ctr)

# -----------------------------------------
# Worker + chunk logic
# -----------------------------------------
def _normalize_workers_and_chunks(total_len, req_workers, min_chunk=8 * 1024 * 1024):
    cpu = os.cpu_count() or 1
    workers = min(req_workers, cpu)

    if total_len < min_chunk:
        workers = 1

    base = total_len // workers
    extra = total_len % workers

    offsets, lengths = [], []
    cur = 0
    for i in range(workers):
        ln = base + (1 if i < extra else 0)
        offsets.append(cur)
        lengths.append(ln)
        cur += ln

    return workers, offsets, lengths

# -----------------------------------------
# Parallel Encrypt (NO LAMBDAS)
# -----------------------------------------
def encrypt_parallel(data, key, mode, workers):
    start = time.perf_counter()

    if mode == "ECB":
        in_bytes = pad(data)
    else:
        in_bytes = data

    total_len = len(in_bytes)
    workers, offsets, lengths = _normalize_workers_and_chunks(total_len, workers)
    results = [None] * workers

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = []

        if mode == "ECB":
            for i, (off, ln) in enumerate(zip(offsets, lengths)):
                futures.append(ex.submit(task_ecb_encrypt, i, in_bytes[off:off+ln], key))

        else:
            nonce = get_random_bytes(8)
            for i, (off, ln) in enumerate(zip(offsets, lengths)):
                init_ctr = off // BLOCK
                futures.append(ex.submit(task_ctr_encrypt, i, in_bytes[off:off+ln], key, nonce, init_ctr))

        for fut in futures:
            idx, part = fut.result()
            results[idx] = part

    if mode == "ECB":
        return b"\x00"*16 + b"".join(results), time.perf_counter() - start
    else:
        return nonce + b"".join(results), time.perf_counter() - start

# -----------------------------------------
# Parallel Decrypt (NO LAMBDAS)
# -----------------------------------------
def decrypt_parallel(enc, key, mode, workers):
    start = time.perf_counter()

    if mode == "ECB":
        in_bytes = enc[16:]
    else:
        nonce = enc[:8]
        in_bytes = enc[8:]

    total_len = len(in_bytes)
    workers, offsets, lengths = _normalize_workers_and_chunks(total_len, workers)
    results = [None] * workers

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = []
        if mode == "ECB":
            for i, (off, ln) in enumerate(zip(offsets, lengths)):
                futures.append(ex.submit(task_ecb_decrypt, i, in_bytes[off:off+ln], key))
        else:
            for i, (off, ln) in enumerate(zip(offsets, lengths)):
                init_ctr = off // BLOCK
                futures.append(ex.submit(task_ctr_decrypt, i, in_bytes[off:off+ln], key, nonce, init_ctr))

        for fut in futures:
            idx, part = fut.result()
            results[idx] = part

    return b"".join(results), time.perf_counter() - start
