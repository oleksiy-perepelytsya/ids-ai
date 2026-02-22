FROM python:3.11-slim

WORKDIR /app

# CLAUDE_CODE=true  — include Node.js + Claude Code CLI (~450 MB, needed for /code command)
# CLAUDE_CODE=false — skip it, saves ~450 MB (parliament deliberation still works fully)
ARG CLAUDE_CODE=true

# System deps: git is always needed; Node.js only when Claude Code is enabled.
# curl is used only during setup and purged afterwards.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl \
    && if [ "$CLAUDE_CODE" = "true" ]; then \
         curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
         && apt-get install -y --no-install-recommends nodejs \
         && npm install -g @anthropic-ai/claude-code --no-optional \
         && npm cache clean --force; \
       fi \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency spec
COPY pyproject.toml ./

# Install Python packages via Poetry, then remove Poetry in the same layer
# so it does not persist and inflate the final image.
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi --no-root \
    && pip uninstall -y poetry \
    && rm -rf /root/.cache/pip /root/.cache/pypoetry

# Copy application code
COPY ids/ ./ids/

# Project workspace directory
RUN mkdir -p /projects

# Minimal git config (Claude Code needs git identity for commits)
RUN git config --global user.name "IDS Bot" \
    && git config --global user.email "ids-bot@noreply.local"

CMD ["python", "-m", "ids"]
