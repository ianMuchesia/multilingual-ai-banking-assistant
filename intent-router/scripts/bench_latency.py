"""Time the real router path, stage by stage.

    python -m scripts.bench_latency gemma 4
"""

import json
import statistics
import sys
import time
import random
from datetime import date

import numpy as np
import torch

from src.config import ROOT, load_router_config, load_settings, with_overrides
from src.data import load_examples
from src.question_guard import question_markers
from src.router import Router, decide
from src.rules import apply_rules

WARMUP = 20
RUNS = 500

BATCH_SIZES = (1, 8, 32)
BATCH_ROUNDS = 20
BATCH_MESSAGES = 320  # every batch size embeds this many, so the test is fair



def summarize(ms: list[float]) -> dict[str, float]:
    return {
        "p50": float(np.percentile(ms, 50)),
        "p95": float(np.percentile(ms, 95)),
        "p99": float(np.percentile(ms, 99)),
        "max":max(ms),
        "mean": statistics.mean(ms),
    }


backend = sys.argv[1] if len(sys.argv) > 1 else "gemma"
threads = int(sys.argv[2]) if len(sys.argv) > 2 else 4
torch.set_num_threads(threads)#before the model loads


settings = with_overrides(load_settings(), gemma_local_only=True)
config = load_router_config(settings.paths.router_config, backend)


start = time.perf_counter()
router = Router(backend, settings,config)
startup_s = time.perf_counter() - start


texts = [ex.text for ex in load_examples(settings.paths.test_synthetic)]


for text in texts[:WARMUP]: #warmup: timings thrown away
    router.route(text)

stages = {"embed": [], "score": [], "rules_decide": [],  "total": []}


for i in range(RUNS):
    text = texts[i%len(texts)]
    
    
    t0 = time.perf_counter()
    vector = router._embedder.embed([text])[0]
    t1 = time.perf_counter()
    
    ranked = router._scorer.rank(vector)
    t2 = time.perf_counter()
    
    if router._bank:
        ranked, rule_reasons = apply_rules(ranked, text, router._bank)
    
    decide(ranked, router._categories, router.config, question_markers(text))
    t3 = time.perf_counter()
    
    stages["embed"].append((t1-t0)*1000)
    stages["score"].append((t2-t1)*1000)
    stages["rules_decide"].append((t3-t2)*1000)
    stages["total"].append((t3-t0)*1000)
    
    
print(f"backend={backend}, threads={threads}, startup={startup_s:.1f}s runs={RUNS}")


for name, ms in stages.items():
    s = summarize(ms)
    print(f"{name:<13} p50={s['p50']:8.2f}  p95={s['p95']:8.2f}  p99={s['p99']:8.2f}  mean={s['mean']:8.2f} ms max={s['max']:8.2f} ms")
    
    
    
    
def cpu_name() -> str:
    for line in open("/proc/cpuinfo", encoding="utf-8"):
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return "unknown"



shuffled = texts[:]
random.Random(42).shuffle(shuffled)  # fixed seed: same order every run

batching = {}

for size in BATCH_SIZES:
    rounds = BATCH_MESSAGES // size
    times = []
    
    for i in range(rounds):
        batch = [shuffled[(i * size + j) % len(shuffled)] for j in range(size)]
        t0 = time.perf_counter()
        router._embedder.embed(batch)
        times.append((time.perf_counter() - t0) * 1000)
        
    batch_ms = statistics.mean(times)
    batching[size] = {
        "batch_ms": batch_ms,
        "ms_per_message": batch_ms / size,
        "messages_per_s": size / (batch_ms / 1000),
        "rounds": rounds,
    }
    
    print(
        f"batch {size:>2}: {batch_ms:8.1f} ms per batch  "
        f"{batch_ms / size:6.1f} ms per message  "
        f"{size / (batch_ms / 1000):6.1f} messages/s"
    )
    
    
    
report = {
    "backend": backend,
    "date": str(date.today()),
    "cpu": cpu_name(),
    "threads": threads,
    "startup_s": startup_s,
    "warmup": WARMUP,
    "runs": RUNS,
    "batch_messages": BATCH_MESSAGES,
    "stages_ms": {name: summarize(ms) for name, ms in stages.items()},
    "batching": batching,
}

out_dir = ROOT / "eval" / "latency"
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / f"{backend}_{date.today()}.json"
out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(f"saved {out_path}")

