"""Logging setup: our messages at the configured level, third-party chatter hidden."""

import logging

_NOISY_LOGGERS = ("httpx", "httpcore", "huggingface_hub", "sentence_transformers", "transformers", "google_genai")
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format=_FORMAT)
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
