from flask import Flask, jsonify, request, send_from_directory
import os, json
from pathlib import Path
from .generate_data import generate_file
from .benchmark import run_single_experiment
from .aes_core import new_key
from .aes_core import encrypt_serial
from .threadpool import encrypt_parallel

app = Flask(__name__, static_folder="../frontend", static_url_path="/")


@app.route("/")
def index():
    return send_from_directory("../frontend", "index.html")


@app.route("/generate/<int:size_mb>")
def generate(size_mb):
    """Generate binary file of given size in MB."""
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(exist_ok=True)
    path = data_dir / f"sample_{size_mb}MB.bin"
    generate_file(path, size_mb)
    return jsonify({"status": "ok", "path": str(path)})


@app.route("/run_one", methods=["POST"])
def run_one():
    """
    Example JSON payload:
    {
      "size_mb": 50,
      "mode": "CTR",
      "threads": 4
    }
    """
    payload = request.json
    size = payload.get("size_mb", 50)
    mode = payload.get("mode", "CTR")
    threads = payload.get("threads", 4)

    base_dir = Path(__file__).resolve().parent.parent
    data_path = base_dir / "data" / f"sample_{size}MB.bin"

    if not data_path.exists():
        return jsonify({"error": f"Data file {data_path} not found"}), 400

    key = new_key()
    result = run_single_experiment(data_path, key, mode, threads)
    return jsonify(result)


@app.route("/benchmarks")
def benchmarks():
    """Return all saved benchmark results."""
    base_dir = Path(__file__).resolve().parent.parent
    json_path = base_dir / "results" / "benchmarks" / "benchmarks.json"
    if json_path.exists():
        with open(json_path) as f:
            return jsonify(json.load(f))
    return jsonify([])

@app.route("/run_thread_sweep", methods=["POST"])
def run_thread_sweep():
    payload = request.json
    size = payload.get("size_mb", 50)
    mode = payload.get("mode", "CTR")

    from pathlib import Path
    base_dir = Path(__file__).resolve().parent.parent
    data_path = base_dir / "data" / f"sample_{size}MB.bin"

    if not data_path.exists():
        return jsonify({"error": "data not found"}), 400

    # THESE TWO LINES ARE REQUIRED
    from .aes_core import encrypt_serial
    from .threadpool import encrypt_parallel

    thread_list = [1, 2, 4, 8, 16]
    key = new_key()

    results = []

    with open(data_path, "rb") as f:
        data = f.read()

    for threads in thread_list:
        # Serial encryption
        encrypted_serial, t1 = encrypt_serial(data, key, mode)

        # Parallel encryption
        encrypted_parallel, t2 = encrypt_parallel(data, key, mode, threads)

        results.append({
            "threads": threads,
            "serial": t1,
            "parallel": t2
        })

    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)
