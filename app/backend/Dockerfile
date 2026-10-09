# syntax=docker/dockerfile:1
# Benki Yetu backend. Build context is BankingAgents/ (see app/docker-compose.yml) so that
# intent-router/ can be copied in. Excludes: app/backend/Dockerfile.dockerignore.
FROM python:3.12-slim

# true: install CPU torch + sentence-transformers for ROUTER_MODE=gemma (~1 GB larger image).
ARG INSTALL_GEMMA=true
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv/backend

COPY app/backend/requirements.txt app/backend/requirements-gemma.txt ./
RUN pip install -r requirements.txt
# CPU torch first, from the PyTorch index, so sentence-transformers doesn't pull the CUDA build.
RUN if [ "$INSTALL_GEMMA" = "true" ]; then \
        pip install --index-url "$TORCH_INDEX_URL" torch torchvision && \
        pip install -r requirements-gemma.txt; \
    fi

# The router needs its code, config, data (train.json is hash-checked) and the built index.
# The model weights are NOT copied: they come from the read-only HF cache mount (HF_HOME).
COPY intent-router/src /srv/intent-router/src
COPY intent-router/config /srv/intent-router/config
COPY intent-router/data /srv/intent-router/data
COPY intent-router/cache/gemma_768.npz /srv/intent-router/cache/gemma_768.npz

COPY app/backend/bankchat ./bankchat

ENV INTENT_ROUTER_DIR=/srv/intent-router \
    PYTHONPATH=/srv/backend \
    HF_HOME=/hf-cache \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1

RUN useradd --create-home --uid 10001 bankapp
USER bankapp

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=180s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# Seed is idempotent: it only creates the demo data when the database is empty.
CMD ["sh", "-c", "python -m bankchat.db.seed && exec uvicorn bankchat.main:app --host 0.0.0.0 --port 8000"]
