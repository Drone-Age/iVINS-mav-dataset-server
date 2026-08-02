FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REGISTRY_ROOT=/registry \
    RAW_ROOT=/data \
    PORT=8080

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt \
    && addgroup -S -g 10001 catalog \
    && adduser -S -D -H -u 10001 -G catalog catalog

COPY --chown=catalog:catalog server.py api_keys.py versions.json ./
COPY --chown=catalog:catalog templates ./templates
COPY --chown=catalog:catalog static ./static
COPY --chown=catalog:catalog seed ./seed

USER 10001:10001

EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "server:app"]
