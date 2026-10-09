"""Logging for the command-line scripts: our messages at INFO, third-party chatter hidden."""

import logging

# Libraries that log every HTTP request at INFO level.
_NOISY_LOGGERS = ("httpx", "httpcore", "huggingface_hub", "sentence_transformers", "transformers", "google_genai")


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(message)s")
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
