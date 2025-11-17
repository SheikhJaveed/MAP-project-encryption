import os
import math
import time
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util import Counter

BLOCK = 16

def pad(data: bytes) -> bytes:
    pad_len = BLOCK - (len(data) % BLOCK)
    return data + bytes([pad_len]) * pad_len

def unpad(data: bytes) -> bytes:
    pad_len = data[-1]
    if pad_len < 1 or pad_len > BLOCK:
        return data
    return data[:-pad_len]

def new_key():
    return get_random_bytes(32)  # AES-256 key

# ---------- Serial encrypt/decrypt ----------
def encrypt_serial(data: bytes, key: bytes, mode: str = "CTR"):
    start = time.perf_counter()
    if mode == "ECB":
        cipher = AES.new(key, AES.MODE_ECB)
        encrypted = cipher.encrypt(pad(data))
    elif mode == "CBC":
        iv = get_random_bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv=iv)
        encrypted = iv + cipher.encrypt(pad(data))
    elif mode == "CTR":
        # single-stream CTR
        nonce = get_random_bytes(8)
        ctr = Counter.new(64, prefix=nonce, initial_value=0)
        cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
        encrypted = nonce + cipher.encrypt(data)  # CTR doesn't require padding
    else:
        raise ValueError("Unsupported mode")
    end = time.perf_counter()
    return encrypted, end - start

def decrypt_serial(encrypted: bytes, key: bytes, mode: str = "CTR"):
    start = time.perf_counter()
    if mode == "ECB":
        cipher = AES.new(key, AES.MODE_ECB)
        decrypted = unpad(cipher.decrypt(encrypted))
    elif mode == "CBC":
        iv = encrypted[:16]
        cipher = AES.new(key, AES.MODE_CBC, iv=iv)
        decrypted = unpad(cipher.decrypt(encrypted[16:]))
    elif mode == "CTR":
        nonce = encrypted[:8]
        ctr = Counter.new(64, prefix=nonce, initial_value=0)
        cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
        decrypted = cipher.decrypt(encrypted[8:])
    else:
        raise ValueError("Unsupported mode")
    end = time.perf_counter()
    return decrypted, end - start

# ---------- Chunk helpers for parallel ----------
def chunkify(data: bytes, num_chunks: int):
    size = len(data)
    base = size // num_chunks
    chunks = []
    start = 0
    for i in range(num_chunks):
        end = start + base + (1 if i < (size % num_chunks) else 0)
        chunks.append(data[start:end])
        start = end
    return chunks

def encrypt_chunk_ecb(chunk: bytes, key: bytes):
    cipher = AES.new(key, AES.MODE_ECB)
    # ECB requires block alignment — pad only the last chunk externally
    return cipher.encrypt(chunk)

def decrypt_chunk_ecb(chunk: bytes, key: bytes):
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.decrypt(chunk)

def encrypt_chunk_ctr_with_counter(chunk: bytes, key: bytes, nonce: bytes, initial_counter: int):
    ctr = Counter.new(64, prefix=nonce, initial_value=initial_counter)
    cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
    return cipher.encrypt(chunk)

def decrypt_chunk_ctr_with_counter(chunk: bytes, key: bytes, nonce: bytes, initial_counter: int):
    ctr = Counter.new(64, prefix=nonce, initial_value=initial_counter)
    cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
    return cipher.decrypt(chunk)
