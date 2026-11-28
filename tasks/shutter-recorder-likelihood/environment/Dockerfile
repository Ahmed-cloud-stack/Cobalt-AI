FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y tmux=3.3a-3 \
 && command -v tmux \
 && tmux -V \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --no-deps numpy==2.3.5
WORKDIR /app
COPY shutter.py sample.json /app/
RUN chmod 644 /app/shutter.py /app/sample.json \
 && mkdir -p /app/output
