"""Score a gemma-ft run on the calibration split only. It never opens an exam.

    python -m scripts.calibration_report
"""

import json
import sys

from src.config import load_router_config, load_settings
from src.data import load_intent_categories
from src.evaluate import calibration_cases, choose, load_calibration, sweep
from src.index import EmbeddingIndex
from src.rules import load_bank_config


BACKEND = sys.argv[1] if len(sys.argv) > 1 else "gemma-ft"
SCORING = "logreg"



settings = load_settings()
paths  = settings.paths
train = EmbeddingIndex.load(paths.index_file(BACKEND, settings.embedding.dim))
calibration = load_calibration(settings.finetune, train)
categories = load_intent_categories(paths.intents)
bank = load_bank_config(paths.bank_config)
config = load_router_config(paths.router_config, BACKEND, SCORING)



cases = calibration_cases(SCORING, train,calibration,config.k,bank)
best,found_zero = choose(sweep(cases,categories,config,"probability"))



meta = json.loads(settings.finetune.metadata_file.read_text(encoding="utf-8"))
params = meta["hyperparameters"]
metrics = best.metrics
print(
    f"mode={params['mode']} epochs={params['epochs']} rounds={params['pair_rounds']} | "
    f"threshold={best.threshold:.2f} margin={best.margin:.2f} zero_critical={found_zero} | "
    f"coverage={metrics.coverage:.1%} top1={metrics.top1_accuracy:.1%} "
    f"critical={metrics.critical} minor={metrics.minor}"
)