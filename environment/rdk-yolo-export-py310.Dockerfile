FROM python:3.10-slim-bookworm

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-pt2onnx.txt /tmp/requirements-pt2onnx.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/requirements-pt2onnx.txt

WORKDIR /workspace
