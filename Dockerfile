## Parent image
FROM python:3.12-slim

## Essential environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

## Work directory inside the docker container
WORKDIR /app

## Installing system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

## Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

## Copy dependency metadata first for better layer caching
COPY pyproject.toml uv.lock ./

## Install Python dependencies from uv lockfile
RUN uv sync --frozen --no-dev

## Copy application code
COPY . .

## Sync again after copying source in case editable/local package metadata changed
RUN uv sync --frozen --no-dev

## Expose only flask port
EXPOSE 5000

## Run the Flask app
CMD ["uv", "run", "app/application.py"]

