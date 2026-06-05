# PTP fulfillment model — FastAPI scoring service (backend/ml-ptp)
# Build context: ./backend/ml-ptp
FROM python:3.12-slim
WORKDIR /app

# libgomp1 is the OpenMP runtime LightGBM needs at import time (the payment
# models are unpickled at startup). Without it the service crash-loops.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv (matches the listening-agent image)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies first (cached layer, no source needed)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source + pre-trained model artifacts, then install the project itself.
# The trained model (models/ptp_model.joblib + model_metadata.json) and the
# LightGBM payment models (models/payment/*.pkl) are committed and baked in;
# the service loads them at startup and serves /predict.
COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uv", "run", "ptp-serve"]
