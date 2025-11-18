# backend/threadpool.py
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import shared_memory
from typing import Tuple, List

from Crypto.Cipher import AES
from Crypto.Util import Counter

from .aes_core import pad, BLOCK

# -----------------------------
# Artificial workload (now parameterized)
# -----------------------------
def heavy_computation(iters: int):
    dummy = 0
    for _ in range(iters):
        dummy = (dummy * 1234567 + 89123) % 999999937
    return dummy

# -----------------------------
# Worker functions (top-level)
# Each worker now accepts 'heavy_iters' to perform only its share
# -----------------------------
def _worker_encrypt_ecb(shm_in_name: str, shm_out_name: str, offset: int, length: int, key: bytes, heavy_iters: int):
    shm_in = shared_memory.SharedMemory(name=shm_in_name)
    shm_out = shared_memory.SharedMemory(name=shm_out_name)
    try:
        data = bytes(shm_in.buf[offset: offset + length])

        # artificial workload (per-worker)
        heavy_computation(heavy_iters)

        cipher = AES.new(key, AES.MODE_ECB)
        if len(data) % BLOCK != 0:
            data = pad(data)
        encrypted = cipher.encrypt(data)

        shm_out.buf[offset: offset + len(encrypted)] = encrypted
        return len(encrypted)
    finally:
        shm_in.close()
        shm_out.close()


def _worker_encrypt_ctr(shm_in_name: str, shm_out_name: str, offset: int, length: int,
                        key: bytes, nonce_prefix: bytes, initial_counter: int, heavy_iters: int):
    shm_in = shared_memory.SharedMemory(name=shm_in_name)
    shm_out = shared_memory.SharedMemory(name=shm_out_name)
    try:
        data = bytes(shm_in.buf[offset: offset + length])

        # artificial workload (per-worker)
        heavy_computation(heavy_iters)

        ctr = Counter.new(64, prefix=nonce_prefix, initial_value=initial_counter)
        cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
        encrypted = cipher.encrypt(data)

        shm_out.buf[offset: offset + len(encrypted)] = encrypted
        return len(encrypted)
    finally:
        shm_in.close()
        shm_out.close()


def _worker_decrypt_ecb(shm_in_name: str, shm_out_name: str, offset: int, length: int, key: bytes, heavy_iters: int):
    shm_in = shared_memory.SharedMemory(name=shm_in_name)
    shm_out = shared_memory.SharedMemory(name=shm_out_name)
    try:
        data = bytes(shm_in.buf[offset: offset + length])

        heavy_computation(heavy_iters)

        cipher = AES.new(key, AES.MODE_ECB)
        decrypted = cipher.decrypt(data)

        shm_out.buf[offset: offset + len(decrypted)] = decrypted
        return len(decrypted)
    finally:
        shm_in.close()
        shm_out.close()


def _worker_decrypt_ctr(shm_in_name: str, shm_out_name: str, offset: int, length: int,
                        key: bytes, nonce_prefix: bytes, initial_counter: int, heavy_iters: int):
    shm_in = shared_memory.SharedMemory(name=shm_in_name)
    shm_out = shared_memory.SharedMemory(name=shm_out_name)
    try:
        data = bytes(shm_in.buf[offset: offset + length])

        heavy_computation(heavy_iters)

        ctr = Counter.new(64, prefix=nonce_prefix, initial_value=initial_counter)
        cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
        decrypted = cipher.decrypt(data)

        shm_out.buf[offset: offset + len(decrypted)] = decrypted
        return len(decrypted)
    finally:
        shm_in.close()
        shm_out.close()

# -----------------------------
# Compute chunking + worker count
# -----------------------------
def _compute_chunks(total_len: int, requested_workers: int, min_chunk_bytes: int = 32 * 1024 * 1024):
    """
    Determine actual number of chunks (num_workers), offsets and lengths.
    Ensures each chunk is at least min_chunk_bytes to reduce overhead.
    """
    # cap to CPU count to avoid oversubscription
    cpu = os.cpu_count() or 1
    requested_workers = min(requested_workers, cpu)

    if total_len < min_chunk_bytes:
        num_workers = 1
    else:
        # compute an upper bound on chunks by dividing by min_chunk_bytes
        max_chunks = max(1, total_len // min_chunk_bytes)
        num_workers = min(requested_workers, max_chunks)
        if num_workers < 1:
            num_workers = 1

    base = total_len // num_workers
    extra = total_len % num_workers
    offsets = []
    lengths = []
    cur = 0
    for i in range(num_workers):
        ln = base + (1 if i < extra else 0)
        offsets.append(cur)
        lengths.append(ln)
        cur += ln

    return num_workers, offsets, lengths

# -----------------------------
# encrypt_parallel
# -----------------------------
def encrypt_parallel(data: bytes, key: bytes, mode: str, workers: int) -> Tuple[bytes, float]:
    """
    Parallel encryption using shared memory + process pool.
    Supports ECB and CTR.
    The total artificial workload is constant (total_heavy_iters) and split between workers.
    """
    start_total = time.perf_counter()

    if mode == "ECB":
        in_bytes = pad(data)
        out_len = len(in_bytes)
    elif mode == "CTR":
        in_bytes = data
        out_len = len(in_bytes)
    else:
        raise ValueError("Parallel encryption only supports ECB and CTR in this framework.")

    shm_in = shared_memory.SharedMemory(create=True, size=len(in_bytes))
    shm_out = shared_memory.SharedMemory(create=True, size=out_len)

    try:
        shm_in.buf[:len(in_bytes)] = in_bytes

        # compute chunking (this will cap to cpu_count and ensure min chunk size)
        num_workers, offsets, lengths = _compute_chunks(len(in_bytes), workers)

        # compute per-worker heavy iterations so TOTAL is constant
        total_heavy_iters = 50000  # tune this for your research; total synthetic work
        per_worker_iters = max(100, total_heavy_iters // num_workers)

        with ProcessPoolExecutor(max_workers=num_workers) as ex:
            futures = []
            if mode == "ECB":
                for off, ln in zip(offsets, lengths):
                    futures.append(ex.submit(_worker_encrypt_ecb, shm_in.name, shm_out.name, off, ln, key, per_worker_iters))
                nonce_prefix = None
            else:
                nonce_prefix = os.urandom(8)
                for off, ln in zip(offsets, lengths):
                    initial_counter = off // BLOCK
                    futures.append(ex.submit(_worker_encrypt_ctr, shm_in.name, shm_out.name, off, ln, key, nonce_prefix, initial_counter, per_worker_iters))

            for fut in as_completed(futures):
                # will raise exception here if any worker failed
                _ = fut.result()

        if mode == "ECB":
            encrypted = bytes(shm_out.buf[:out_len])
            # prefix 16 zero bytes for compatibility with decrypt_serial expectations
            encrypted = b'\x00' * 16 + encrypted
        else:
            encrypted = nonce_prefix + bytes(shm_out.buf[:out_len])

        end_total = time.perf_counter()
        elapsed = end_total - start_total
        return encrypted, elapsed
    finally:
        try:
            shm_in.close()
            shm_in.unlink()
        except Exception:
            pass
        try:
            shm_out.close()
            shm_out.unlink()
        except Exception:
            pass

# -----------------------------
# decrypt_parallel
# -----------------------------
def decrypt_parallel(encrypted: bytes, key: bytes, mode: str, workers: int) -> Tuple[bytes, float]:
    """
    Parallel decryption using shared memory + process pool.
    Supports ECB and CTR.
    """
    start_total = time.perf_counter()

    if mode == "ECB":
        # encrypted may have 16-byte prefix (for compatibility)
        body = encrypted[16:]
        in_bytes = body
    else:
        nonce_prefix = encrypted[:8]
        in_bytes = encrypted[8:]

    total_len = len(in_bytes)
    shm_in = shared_memory.SharedMemory(create=True, size=total_len)
    shm_out = shared_memory.SharedMemory(create=True, size=total_len)

    try:
        shm_in.buf[:total_len] = in_bytes

        num_workers, offsets, lengths = _compute_chunks(total_len, workers)

        # keep total heavy iterations constant and split between workers
        total_heavy_iters = 50000
        per_worker_iters = max(100, total_heavy_iters // num_workers)

        with ProcessPoolExecutor(max_workers=num_workers) as ex:
            futures = []
            if mode == "ECB":
                for off, ln in zip(offsets, lengths):
                    futures.append(ex.submit(_worker_decrypt_ecb, shm_in.name, shm_out.name, off, ln, key, per_worker_iters))
            else:
                for off, ln in zip(offsets, lengths):
                    initial_counter = off // BLOCK
                    futures.append(ex.submit(_worker_decrypt_ctr, shm_in.name, shm_out.name, off, ln, key, nonce_prefix, initial_counter, per_worker_iters))

            for fut in as_completed(futures):
                _ = fut.result()

        decrypted = bytes(shm_out.buf[:total_len])

        end_total = time.perf_counter()
        elapsed = end_total - start_total
        return decrypted, elapsed
    finally:
        try:
            shm_in.close()
            shm_in.unlink()
        except Exception:
            pass
        try:
            shm_out.close()
            shm_out.unlink()
        except Exception:
            pass
