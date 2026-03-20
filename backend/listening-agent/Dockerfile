FROM python:3.12-slim
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies first (cached layer, no source needed)
COPY listening-agent/pyproject.toml listening-agent/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and shared data files, then install the project itself
COPY listening-agent/ .
COPY call_flows.json /call_flows.json
RUN uv sync --frozen --no-dev

CMD ["uv", "run", "listening-agent", "start"]
