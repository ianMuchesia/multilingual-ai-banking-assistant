"""gemini-embedding-2 via the Gemini API."""

import logging
import time

import numpy as np
from google import genai
from google.genai import errors, types

from src.config import EmbeddingConfig, GeminiConfig
from src.embeddings.base import Embedder, QuotaExceededError

log = logging.getLogger(__name__)


def _is_server_error(error: errors.APIError) -> bool:
    return error.code is not None and 500 <= error.code < 600


class GeminiEmbedder(Embedder):
    def __init__(self, config: GeminiConfig, embedding: EmbeddingConfig) -> None:
        super().__init__(config.model_id, embedding)
        if not config.api_key:
            raise ValueError("GEMINI_API_KEY is not set in .env")
        self._config = config
        self._client = genai.Client(api_key=config.api_key)
        self._request_config = types.EmbedContentConfig(output_dimensionality=self.dim)
        if not self.prefix:
            log.warning("task prefix is OFF")
        if not config.wrap_contents:
            log.warning("wrap_contents is OFF: expect one aggregated vector per batch")

    def _encode(self, texts: list[str]) -> np.ndarray:
        size = self._config.batch_size
        batches = [texts[i : i + size] for i in range(0, len(texts), size)]

        results = []
        for n, batch in enumerate(batches, start=1):
            if n > 1:
                log.info("pausing %.0fs for rate limit", self._config.batch_pause_s)
                time.sleep(self._config.batch_pause_s)
            log.info("batch %d/%d (%d texts)", n, len(batches), len(batch))
            results.append(self._embed_with_retry(batch))
        return np.vstack(results)

    def _embed_with_retry(self, texts: list[str]) -> np.ndarray:
        """Retry 5xx with exponential backoff. The final attempt's error propagates as-is."""
        for attempt in range(1, self._config.max_tries):
            try:
                return self._embed_once(texts)
            except errors.APIError as e:
                if not _is_server_error(e):
                    raise
                delay = 2**attempt
                log.warning("server error %s, retry %d in %ds", e.code, attempt, delay)
                time.sleep(delay)
        return self._embed_once(texts)

    def _build_contents(self, texts: list[str]) -> list[types.Content] | list[str]:
        prefixed = [self.prefix + t for t in texts]
        if not self._config.wrap_contents:
            return prefixed  # a plain list of strings is embedded as ONE aggregated vector
        return [types.Content(parts=[types.Part.from_text(text=t)]) for t in prefixed]

    def _embed_once(self, texts: list[str]) -> np.ndarray:
        try:
            response = self._client.models.embed_content(
                model=self.model_id, contents=self._build_contents(texts), config=self._request_config
            )
        except errors.APIError as e:
            if e.code == 429:
                raise QuotaExceededError(f"Gemini returned 429: {e.message}") from e
            raise
        return np.array([e.values for e in response.embeddings], dtype=np.float32)
