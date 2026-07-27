FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REGISTRY_ROOT=/registry \
    RAW_ROOT=/data \
    PORT=8080

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt \
    && groupadd --system --gid 10001 catalog \
    && useradd --system --uid 10001 --gid catalog --home-dir /nonexistent catalog

COPY --chown=catalog:catalog server.py .

USER 10001:10001

EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "server:app"]
