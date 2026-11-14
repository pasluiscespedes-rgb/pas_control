"""Restore the newest FORTEX Backblaze backup in a private, temporary PostgreSQL 18.6.
NEVER connect to operational PostgreSQL. Never print credentials or row contents.
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

EXPECTED_BUCKET = "fortex-pascontrol-backups-2026"
BACKUP_PATTERN = re.compile(r"^fortex_production_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}Z)_[a-f0-9]{32}\.dump$")

def emit(event, **fields):
    print(json.dumps({"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), **fields}), flush=True)

def run(argv, env, timeout, code):
    try:
        process = subprocess.run(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError(code) from None
    if process.returncode:
        raise RuntimeError(code)
    return process.stdout.decode("utf-8", errors="replace").strip()

def digest_size(path):
    digest = hashlib.sha1()
    size = 0
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size

def main():
    logging.disable(logging.CRITICAL)
    stage = "configuration"
    try:
        # No credentials or network connection to the operational PostgreSQL instance.
        if any(os.getenv(k) for k in ("PGHOST", "PGPASSWORD", "DATABASE_URL", "DB_HOST", "DB_PASSWORD")):
            raise RuntimeError("production_db_environment_not_allowed")
        required = ("B2_APPLICATION_KEY_ID", "B2_APPLICATION_KEY", "B2_BUCKET_NAME")
        if any(not os.environ.get(k) for k in required):
            raise RuntimeError("b2_credentials_missing")
        if os.environ["B2_BUCKET_NAME"] != EXPECTED_BUCKET:
            raise RuntimeError("unexpected_bucket")
        prefix = os.environ.get("B2_PREFIX", "backups/")
        if not re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*/", prefix):
            raise RuntimeError("invalid_prefix")
        from b2sdk.v3 import B2Api, InMemoryAccountInfo
        api = B2Api(InMemoryAccountInfo(), max_upload_workers=1, max_download_workers=1,
                    max_download_streams_per_file=1)
        stage = "b2_authorization"
        api.authorize_account(os.environ["B2_APPLICATION_KEY_ID"], os.environ["B2_APPLICATION_KEY"])
        bucket = api.get_bucket_by_name(EXPECTED_BUCKET)
        stage = "backup_selection"
        candidates = []
        for version, _folder in bucket.ls(path=prefix, recursive=True):
            name = version.file_name
            if not name.startswith(prefix):
                continue
            m = BACKUP_PATTERN.fullmatch(name[len(prefix):])
            if m:
                stamp = datetime.strptime(m.group(1), "%Y-%m-%d_%H-%M-%SZ").replace(tzinfo=timezone.utc)
                candidates.append((stamp, version))
        if not candidates:
            raise RuntimeError("no_valid_backup_found")
        stamp, version = max(candidates, key=lambda x: x[0])
        age = (datetime.now(timezone.utc) - stamp).total_seconds() / 3600
        if not 0 <= age <= 48:
            raise RuntimeError("latest_backup_not_recent")
        emit("BACKUP_FOUND", age_hours=round(age, 2), bytes=version.size)
        with tempfile.TemporaryDirectory(prefix="fortex-restore-") as temp:
            root = Path(temp)
            dump = root / "backup.dump"
            stage = "download_and_integrity"
            result = api.download_file_by_id(version.id_)
            try:
                with dump.open("xb") as dst:
                    result.save(dst, allow_seeking=False)
            finally:
                result.response.close()
            digest, size = digest_size(dump)
            if size <= 0 or size != version.size:
                raise RuntimeError("dump_size_mismatch")
            recorded = (version.file_info or {}).get("fortex_sha1")
            for expected in (version.content_sha1, recorded):
                if expected and expected != "none" and expected != digest:
                    raise RuntimeError("dump_sha1_mismatch")
            if not recorded and version.content_sha1 in (None, "none"):
                raise RuntimeError("reference_digest_missing")
            stage = "dump_structure"
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                   "HOME": str(root), "LC_ALL": "C"}
            catalog = run(["pg_restore", "--list", str(dump)], env, 90, "dump_listing_failed")
            if sum(bool(x.strip()) and not x.startswith(";") for x in catalog.splitlines()) < 10:
                raise RuntimeError("dump_catalog_too_small")
            stage = "isolated_pg_init"
            data = root / "pgdata"
            sock = root / "socket"
            sock.mkdir(mode=0o700)
            run(["initdb", "-D", str(data), "--auth-local=trust", "--auth-host=reject",
                 "--no-instructions"], env, 120, "initdb_failed")
            local = dict(env, PGHOST=str(sock), PGPORT="5432", PGUSER="postgres",
                         PGDATABASE="postgres")
            started = False
            try:
                run(["pg_ctl", "-D", str(data), "-w", "-o",
                     f"-c listen_addresses='' -c unix_socket_directories={sock}",
                     "-l", str(root / "postgres.log"), "start"], env, 120, "local_postgres_start_failed")
                started = True
                run(["createdb", "-h", str(sock), "-U", "postgres", "fortex_recovery_test"],
                    local, 30, "create_test_db_failed")
                stage = "full_restore"
                run(["pg_restore", "-h", str(sock), "-U", "postgres",
                     "--no-owner", "--no-acl", "--exit-on-error",
                     "--dbname=fortex_recovery_test", str(dump)], local, 1200, "pg_restore_failed")
                stage = "schema_validation"
                query_env = dict(local, PGDATABASE="fortex_recovery_test")
                def q(sql):
                    return run(["psql", "-v", "ON_ERROR_STOP=1", "-Atqc", sql],
                               query_env, 30, "schema_query_failed")
                tables = int(q("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"))
                migrations = int(q("SELECT count(*) FROM django_migrations"))
                if tables < 10 or migrations < 1:
                    raise RuntimeError("restored_schema_incomplete")
                for table in ("clientes_cliente", "polizas_poliza", "cobros_cobro",
                              "vehiculos_marcavehiculo"):
                    q(f"SELECT count(*) FROM {table}")
                emit("RESTORE_VERIFIED", backup_utc=stamp.isoformat(), pg_version="18.6",
                     tables=tables, migration_records=migrations, backup_bytes=size)
            finally:
                if started:
                    try:
                        run(["pg_ctl", "-D", str(data), "-m", "immediate", "-w", "stop"],
                            env, 45, "local_postgres_stop_failed")
                    except RuntimeError:
                        emit("WARNING", code="local_postgres_stop_failed")
        return 0
    except BaseException as error:
        emit("RESTORE_FAILED", stage=stage,
             code=str(error) if isinstance(error, RuntimeError) else "unexpected_error")
        return 1

if __name__ == "__main__":
    sys.exit(main())
