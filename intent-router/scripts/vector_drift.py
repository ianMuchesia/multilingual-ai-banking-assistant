"""How much did INT8 change the vectors? Compares two saved indexes row by row.

    python -m scripts.vector_drift gemma-ft gemma-ft-int8
"""

import sys
from collections import defaultdict

import numpy as np

from src.config import load_settings
from src.index import EmbeddingIndex

before_name, after_name = sys.argv[1], sys.argv[2]
settings = load_settings()

for split in ("train", "test_synthetic"):
    before = EmbeddingIndex.load(settings.paths.index_file(before_name, settings.embedding.dim, split))
    after = EmbeddingIndex.load(settings.paths.index_file(after_name, settings.embedding.dim, split))
    if list(before.texts) != list(after.texts):
        sys.exit(f"{split}: the two indexes hold different sentences, so they can't be compared")

    cosines = (before.vectors * after.vectors).sum(axis=1)
    print(f"\n{split}: {len(cosines)} sentences   mean {cosines.mean():.4f}   min {cosines.min():.4f}")

    by_language = defaultdict(list)
    for lang, cosine in zip(before.langs, cosines):
        by_language[lang].append(cosine)
    for lang, values in sorted(by_language.items()):
        print(f"  {lang:<6} mean {np.mean(values):.4f}   min {np.min(values):.4f}")

    print("  5 worst:")
    for i in np.argsort(cosines)[:5]:
        print(f"    {cosines[i]:.4f}  {before.langs[i]:<6} {before.texts[i]}")
