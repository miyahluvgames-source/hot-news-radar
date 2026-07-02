FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY SKILL.md README.md ./
COPY agents ./agents
COPY references ./references
COPY scripts ./scripts

FROM base AS final
ENTRYPOINT ["python", "scripts/hot_news_radar.py"]

FROM base AS browser
COPY requirements-browser.txt ./
RUN python -m pip install --no-cache-dir -r requirements-browser.txt \
    && python -m playwright install --with-deps chromium
ENTRYPOINT ["python", "scripts/hot_news_radar.py"]

