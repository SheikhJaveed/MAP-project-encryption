import subprocess, shlex, time, os, tempfile

def openssl_encrypt_file(filepath, mode="aes-256-ctr", key=None):
    """
    Encrypt using OpenSSL CLI. Returns elapsed time.
    Note: To avoid passphrase prompts we use -K (key in hex) and -iv (0) for stream modes or generate IV.
    """
    if not shutil.which("openssl"):
        raise RuntimeError("OpenSSL not found on PATH")
    start = time.perf_counter()
    # create a temporary output
    out = filepath + f".{mode}.enc"
    # For CTR/CBC: set an IV; OpenSSL expects hex strings
    iv_hex = "00000000000000000000000000000000"
    key_hex = key.hex()
    cmd = f"openssl enc -{mode} -in {shlex.quote(filepath)} -out {shlex.quote(out)} -K {key_hex} -iv {iv_hex}"
    subprocess.run(cmd, shell=True, check=True)
    end = time.perf_counter()
    return (out, end - start)
