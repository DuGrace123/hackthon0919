FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LINGJIAN_ENV=production \
    LINGJIAN_WEB_WORKSPACE=/var/data/lingjian \
    LINGJIAN_MAX_UPLOAD_MB=512 \
    PORT=10000

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-web.txt requirements-deploy.txt ./
RUN python -m pip install -r requirements-deploy.txt

# Copy only runtime sources and licensed assets, never local media or accounts.
COPY *.py ./
COPY web/ ./web/
COPY assets/ ./assets/
COPY docs/third_party_notices.md ./docs/third_party_notices.md

EXPOSE 10000
CMD ["gunicorn", "--config", "gunicorn.conf.py", "web_app:app"]
