FROM python:3.11-slim

WORKDIR /app

# Install system dependencies + Node.js (for Claude Code CLI)
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_CREATE=false
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY ids/ ./ids/

# Create directories
RUN mkdir -p /projects

# Minimal git config (Claude Code needs git identity for commits)
RUN git config --global user.name "IDS Bot" \
    && git config --global user.email "ids-bot@noreply.local"

# Run the application
CMD ["python", "-m", "ids"]
