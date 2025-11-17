from flask import Flask, jsonify, request, send_from_directory
import os, json
from pathlib import Path
from .generate_data import generate_file
from .benchmark import run_single_experiment
from .aes_core import new_key

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


if __name__ == "__main__":
    app.run(debug=True)
