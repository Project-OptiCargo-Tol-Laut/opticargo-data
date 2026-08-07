FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OPTICARGO_DATASET_DIR=/app/dataset

WORKDIR /app

RUN groupadd --system opticargo && useradd --system --gid opticargo --home-dir /nonexistent --shell /usr/sbin/nologin opticargo

COPY requirements.txt /app/requirements.txt
COPY vendor /app/vendor
RUN python -m pip install --upgrade pip && python -m pip install -r /app/requirements.txt

COPY pyproject.toml README.md /app/
COPY opticargo_data /app/opticargo_data
COPY dataset /app/dataset
COPY scripts /app/scripts

RUN chown -R opticargo:opticargo /app
USER opticargo

CMD ["python", "-m", "opticargo_data.seed", "--help"]
