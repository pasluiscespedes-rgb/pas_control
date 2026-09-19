FROM postgres:18.6-bookworm@sha256:1c59e2c3c818eaa0f0628f695b36e7c9e362d6b219b36a54a32df645cbd7e1af

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates tini \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt \
    && /opt/venv/bin/pip check \
    && pg_dump --version | grep -Eq '^pg_dump \(PostgreSQL\) 18\.6([[:space:]]|$)' \
    && pg_restore --version | grep -Eq '^pg_restore \(PostgreSQL\) 18\.6([[:space:]]|$)'
COPY backup.py /app/backup.py

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=UTC
USER postgres
# Replace the database-server entrypoint inherited from the base image.
ENTRYPOINT ["/usr/bin/tini", "-g", "--"]
CMD ["/usr/bin/timeout", "--signal=TERM", "--kill-after=30s", "1800", "/opt/venv/bin/python", "-u", "/app/backup.py"]
