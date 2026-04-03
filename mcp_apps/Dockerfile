# Self-contained Helix image for the MCP Apps demo.
# Combines the core chat service (chat/) and workflow examples (chat_examples/)
# so the demo can be started with a single `docker compose up --build`.

# ── Stage 1: install base chat service deps ──────────────────────────────
FROM istresearch/golden-image:python-3.12 AS build-base

RUN pip install --upgrade pip

WORKDIR /usr/src/app

COPY pyproject.toml .
COPY uv.lock .
COPY chat/pyproject.toml          ./chat/pyproject.toml
COPY chat_examples/pyproject.toml ./chat_examples/pyproject.toml

WORKDIR /usr/src/app/chat
RUN python -m venv --copies /app/venv \
 && . /app/venv/bin/activate \
 && pip install --upgrade pip uv \
 && uv sync --active

# ── Stage 2: add chat_examples (langgraph) deps to the venv ──────────────
FROM build-base AS build-examples

WORKDIR /usr/src/app/chat_examples
RUN . /app/venv/bin/activate \
 && uv sync --active --extra langgraph

# ── Stage 3: slim runtime image ───────────────────────────────────────────
FROM istresearch/golden-image:python-3.12-slim AS service

RUN addgroup helix \
 && adduser --gecos "" --disabled-password --shell /bin/false \
            --uid 1717 --ingroup helix helix

RUN mkdir /usr/src/app && chown -R helix:helix /usr/src/app

USER helix:helix

COPY --from=build-examples /app/venv /app/venv/

ENV PATH="/app/venv/bin:$PATH"

WORKDIR /usr/src/app/chat

# Core chat service
COPY --chown=helix:helix ./chat/chat_service ./chat_service
COPY --chown=helix:helix ./chat/config       ./config

# Example workflows (McpAgent, LangGraph utils, etc.)
COPY --chown=helix:helix ./chat_examples/workflow ../chat_examples/workflow

ARG VERSION_TAG
ENV VERSION_TAG=${VERSION_TAG:-main}

CMD ["python", "-m", "chat_service.main"]
