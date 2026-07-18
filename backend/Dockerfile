# EverMind API image (OPS-2). Compose bind-mounts ../backend:/app for hot
# reload, so dependencies are installed into the SYSTEM python (a /app/.venv
# would be shadowed by the host mount); the mounted source is imported via
# PYTHONPATH=/app.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project --output-file /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "evermind.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
