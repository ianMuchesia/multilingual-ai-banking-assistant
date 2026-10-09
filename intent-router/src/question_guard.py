"""Cheap rule-based check: does a message read like a question?

Used by the router's action guard. Embeddings score "how do I send money to KCB"
and "send 5000 to KCB" at 0.87 (both gemma and gemini), so when the top intent
moves money but the message looks like a question, the router defers to the LLM.

This is a keyword list, so it has blind spots by design: "explain sending to KCB"
or "process ya kutuma pesa KCB" are questions it will not recognise.
"""

import re

QUESTION_WORDS = frozenset({"how", "what", "jinsi", "aje", "gani", "ngapi"})
QUESTION_PHRASES = (("can", "i"), ("is", "there"))
# Swahili/Sheng question verbs end in -je: nitumaje, nitalipaje, inafanyaje.
JE_SUFFIX = "je"
JE_MIN_LENGTH = 5


def _words(text: str) -> list[str]:
    # Split on anything that isn't a letter or digit, so "what's" -> ["what", "s"].
    return re.findall(r"[a-z0-9]+", text.lower())


def question_markers(text: str) -> list[str]:
    """The question markers found in `text`, in order, without duplicates. Empty = not a question."""
    words = _words(text)
    found = ["?"] if "?" in text else []
    found += [w for w in words if w in QUESTION_WORDS]
    found += [f"{a} {b}" for a, b in QUESTION_PHRASES if any(pair == (a, b) for pair in zip(words, words[1:]))]
    found += [w for w in words if len(w) >= JE_MIN_LENGTH and w.endswith(JE_SUFFIX)]
    return list(dict.fromkeys(found))
