FROM python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b
RUN apt-get update \
    && apt-get install -y tmux \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY overlay.py sample.json sample_history.json /app/
RUN chmod 644 /app/overlay.py /app/sample.json /app/sample_history.json
