import os

def generate_file(path, size_mb):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(os.urandom(size_mb * 1024 * 1024))
    print(f"Generated {size_mb}MB -> {path}")

if __name__ == "__main__":
    generate_file("../data/sample_10MB.bin", 10)
    generate_file("../data/sample_50MB.bin", 50)
    generate_file("../data/sample_100MB.bin", 100)
