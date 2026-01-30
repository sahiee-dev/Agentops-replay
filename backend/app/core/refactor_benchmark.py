import json
import os
from typing import Any

from .metrics import combined_score
from .refactor_engine import HybridRefactor

# Path to your sample agents
SAMPLES_DIR = "backend/demo_agents/test-samples/"
RESULTS_FILE = "backend/data/results/benchmark.json"


def load_samples(path: str) -> tuple[list[str], list[str]]:
    samples: list[str] = []
    files = [f for f in os.listdir(path) if f.endswith(".py")]
    for f in files:
        with open(os.path.join(path, f)) as file:
            samples.append(file.read())
    return samples, files


def benchmark(samples: list[str], filenames: list[str]) -> list[dict[str, Any]]:
    ref = HybridRefactor()
    results: list[dict[str, Any]] = []
    for i, s in enumerate(samples):
        refined, _ = ref.hybrid_refactor(s)
        score = combined_score(s, refined)
        results.append(
            {"file": filenames[i], "score": score, "original": s, "refined": refined}
        )
    return results


if __name__ == "__main__":
    samples, filenames = load_samples(SAMPLES_DIR)
    results = benchmark(samples, filenames)

    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=4)

    print(
        f"Benchmark completed for {len(samples)} samples. Results saved in {RESULTS_FILE}"
    )
