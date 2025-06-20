# docker/jupyter/Dockerfile
# docker/jupyter/Dockerfile
FROM quay.io/jupyter/datascience-notebook:latest

USER root

RUN apt-get update \
 && apt-get install -y build-essential \
 && pip install --no-cache-dir poetry \
 && rm -rf /var/lib/apt/lists/*
 
RUN apt-get update && apt-get install -y git nodejs

WORKDIR /home/jovyan/work

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
 && poetry install --no-root --without dev --no-interaction --no-ansi

# 🔥 Добавь это:
RUN mkdir -p /home/jovyan/.local/share/jupyter/runtime \
 && chown -R jovyan:users /home/jovyan/.local

USER jovyan

