# Image dùng chung cho API, worker và beat (cùng mã nguồn backend, có FFmpeg + font tiếng Việt)
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY services/api/requirements.txt /srv/requirements.txt
RUN pip install -r /srv/requirements.txt
COPY services/api /srv/services/api
COPY services/worker /srv/services/worker
COPY migrations /srv/migrations
COPY scripts/docker-entrypoint.sh /srv/entrypoint.sh
RUN useradd -m -u 10001 anngan && mkdir -p /srv/var/storage /srv/var/backups /srv/var/tmp && chown -R anngan /srv/var && chmod +x /srv/entrypoint.sh
USER anngan
ENV PYTHONPATH=/srv/services/api:/srv/services/worker STORAGE_LOCAL_ROOT=/srv/var/storage BACKUP_DIR=/srv/var/backups
WORKDIR /srv/services/api
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD curl -fs http://localhost:8000/health || exit 1
ENTRYPOINT ["/srv/entrypoint.sh"]
CMD ["api"]
