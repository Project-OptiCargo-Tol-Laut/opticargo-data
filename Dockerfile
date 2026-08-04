FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY opticargo-shared /opt/opticargo-shared
RUN python -m pip install --no-cache-dir /opt/opticargo-shared

COPY opticargo-data/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY opticargo-data /app

CMD ["python", "-m", "seed.seed_all"]
