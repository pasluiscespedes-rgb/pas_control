"""One-shot backup of FORTEX PostgreSQL over Railway's private network.

No Django imports, Railway CLI, dotenv, migrations, restores or retention jobs.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

EXPECTED_PGHOST = "postgres.railway.internal"
PG_VERSION = "18.6"
PG_KEYS = ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE")
MAX_ATTEMPTS = 3


class BackupError(Exception):
    """Arguments must be controlled error codes, never external error messages."""


def event(name: str, run_id: str, **values: object) -> None:
    print(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(),
                      "event": name, "run_id": run_id, **values}), flush=True)


@dataclass(frozen=True)
class Config:
    pg: dict[str, str] = field(repr=False)
    key_id: str = field(repr=False)
    key: str = field(repr=False)
    bucket: str
    prefix: str

    @classmethod
    def from_env(cls, env: dict[str, str]) -> Config:
        required = (*PG_KEYS, "B2_APPLICATION_KEY_ID", "B2_APPLICATION_KEY", "B2_BUCKET_NAME")
        if any(not env.get(k) or "\x00" in env[k] for k in required):
            raise BackupError("missing_or_invalid_configuration")
        # Exact allowlist: other private services are not the production database.
        if env["PGHOST"].lower() != EXPECTED_PGHOST:
            raise BackupError("unexpected_database_host")
        if not re.fullmatch(r"[0-9]+", env["PGPORT"]) or not 1 <= int(env["PGPORT"]) <= 65535:
            raise BackupError("invalid_database_port")
        if not re.fullmatch(r"[A-Za-z0-9-]{6,50}", env["B2_BUCKET_NAME"]):
            raise BackupError("invalid_bucket_name")
        prefix = env.get("B2_PREFIX", "backups/")
        if not re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*/", prefix):
            raise BackupError("invalid_object_prefix")
        return cls({k: env[k] for k in PG_KEYS}, env["B2_APPLICATION_KEY_ID"],
                   env["B2_APPLICATION_KEY"], env["B2_BUCKET_NAME"], prefix)

    def child_env(self) -> dict[str, str]:
        # No inherited PGSERVICE, public URL, B2 keys, proxies or libpq overrides.
        result = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT") if k in os.environ}
        result.update(self.pg)
        result.update(PGCONNECT_TIMEOUT="20", PGOPTIONS="-c default_transaction_read_only=on",
                      PGCLIENTENCODING="UTF8", LC_ALL="C", HOME="/nonexistent")
        return result


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait()
    except ProcessLookupError:
        process.wait()


def command(argv: list[str], env: dict[str, str], timeout: int, code: str) -> str:
    process = None
    try:
        process = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=os.name == "posix")
        stdout, _stderr = process.communicate(timeout=timeout)
        if process.returncode != 0:
            raise BackupError(code)
        return stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        raise BackupError(code + "_timeout") from None
    except OSError:
        raise BackupError(code + "_unavailable") from None
    finally:
        if process is not None:
            stop_process(process)
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()


def check_tools(env: dict[str, str]) -> None:
    for tool in ("pg_dump", "pg_restore"):
        output = command([tool, "--version"], env, 10, "client_version_check")
        if not re.match(r"^" + tool + r" \(PostgreSQL\) 18\.6(?:\s|$)", output):
            raise BackupError("postgresql_18_6_required")


def file_digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha1()
    size = 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def create_dump(config: Config, folder: Path, run_id: str) -> tuple[Path, int, str, int]:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%SZ")
    final = folder / f"fortex_production_{stamp}_{run_id}.dump"
    partial = final.with_suffix(".dump.partial")
    # Each run has a private scratch directory and UUID; do not overwrite files.
    with partial.open("xb"):
        pass
    env = config.child_env()
    command(["pg_dump", "--format=custom", "--no-owner", "--no-password",
             "--file", str(partial)], env, 900, "pg_dump_failed")
    if not partial.is_file() or partial.stat().st_size == 0:
        raise BackupError("empty_dump")
    listing = command(["pg_restore", "--list", str(partial)], env, 120, "dump_validation_failed")
    entries = sum(bool(line.strip()) and not line.lstrip().startswith(";")
                  for line in listing.splitlines())
    if entries == 0:
        raise BackupError("empty_dump_catalog")
    size, sha1 = file_digest(partial)
    if final.exists():
        raise BackupError("destination_exists")
    partial.rename(final)
    return final, size, sha1, entries


class HashSink(io.RawIOBase):
    """Non-seekable destination for sequential, constant-memory verification."""

    def __init__(self) -> None:
        super().__init__()
        self.size = 0
        self.digest = hashlib.sha1()

    def writable(self) -> bool:
        return True

    def write(self, data: bytes) -> int:
        self.digest.update(data)
        self.size += len(data)
        return len(data)


class Backblaze:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.api = None
        self.bucket = None
        self.sessions = []

    def __enter__(self) -> Backblaze:
        import requests
        from b2sdk.v3 import B2Api, B2HttpApiConfig, InMemoryAccountInfo

        class BoundedSession(requests.Session):
            def send(self, request, **kwargs):
                kwargs["timeout"] = (10, 60)
                return super().send(request, **kwargs)

        def session_factory():
            session = BoundedSession()
            session.trust_env = False
            self.sessions.append(session)
            return session

        try:
            self.api = B2Api(InMemoryAccountInfo(), max_upload_workers=1, max_copy_workers=1,
                             max_download_workers=1, max_download_streams_per_file=1,
                             api_config=B2HttpApiConfig(http_session_factory=session_factory))
            self.api.authorize_account(self.config.key_id, self.config.key)
            self.bucket = self.api.get_bucket_by_name(self.config.bucket)
            if self.bucket.name != self.config.bucket:
                raise BackupError("unexpected_bucket")
            return self
        except BaseException:
            self.close()
            raise

    def verify(self, file_id: str, name: str, size: int, sha1: str) -> None:
        version = self.api.get_file_info(file_id)
        if (version.id_ != file_id or version.file_name != name
                or version.size != size or version.bucket_id != self.bucket.id_):
            raise BackupError("remote_metadata_mismatch")
        # Multipart objects may not provide a full content_sha1.
        if version.content_sha1 not in (None, "none", sha1):
            raise BackupError("remote_sha1_mismatch")
        downloaded = self.api.download_file_by_id(file_id)
        try:
            with HashSink() as sink:
                downloaded.save(sink, allow_seeking=False)
                if sink.size != size or sink.digest.hexdigest() != sha1:
                    raise BackupError("remote_content_mismatch")
        finally:
            downloaded.response.close()

    def upload_verified(self, path: Path, size: int, sha1: str, run_id: str) -> str:
        name = self.config.prefix + path.name
        file_id = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                if file_digest(path) != (size, sha1):
                    raise BackupError("local_file_changed")
                if file_id is None:
                    # Reconcile an upload whose successful response might have been lost.
                    existing = [v for v, _ in self.bucket.ls(path=name, recursive=True)
                                if v.file_name == name]
                    if len(existing) > 1:
                        raise BackupError("ambiguous_remote_object")
                    if existing:
                        file_id = existing[0].id_
                    else:
                        version = self.bucket.upload_local_file(
                            local_file=str(path), file_name=name,
                            content_type="application/octet-stream", sha1_sum=sha1,
                            file_info={"fortex_run_id": run_id, "fortex_sha1": sha1})
                        file_id = version.id_
                self.verify(file_id, name, size, sha1)
                if file_digest(path) != (size, sha1):
                    raise BackupError("local_file_changed")
                return file_id
            except BackupError:
                raise
            except Exception:
                if attempt == MAX_ATTEMPTS:
                    raise BackupError("backblaze_operation_failed") from None
                event("RETRY", run_id, stage="backblaze", attempt=attempt)
                time.sleep(2 ** attempt)
        raise BackupError("backblaze_operation_failed")

    def close(self) -> None:
        # b2sdk 2.12.0 has no public close(). Its pinned LazyThreadPool layout is
        # isolated here: revalidate this adapter when upgrading the dependency.
        pools = []
        if self.api is not None:
            services = self.api.services
            managers = [services.upload_manager, services.copy_manager, services.download_manager]
            managers.extend(services.download_manager.strategies)
            for manager in managers:
                lazy = getattr(manager, "_thread_pool", None)
                pool = getattr(lazy, "_thread_pool", None)
                if pool is not None and pool not in pools:
                    pools.append(pool)
        try:
            for pool in pools:
                pool.shutdown(wait=True, cancel_futures=True)
        finally:
            for session in self.sessions:
                session.close()
            self.sessions.clear()

    def __exit__(self, *_exc) -> None:
        self.close()


def interrupted(_signum, _frame) -> None:
    raise BackupError("interrupted")


def main() -> int:
    # SDK debug logs, external exception strings and libpq stderr can hold secrets.
    logging.disable(logging.CRITICAL)
    run_id = uuid4().hex
    started = time.monotonic()
    stage = "configuration"
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, interrupted)
    try:
        config = Config.from_env(dict(os.environ))
        event("START", run_id, source="Railway/production")
        stage = "tools"
        check_tools(config.child_env())
        stage = "backblaze_authentication"
        with Backblaze(config) as remote:
            # Only this run's scratch files are removed, never existing backups.
            with tempfile.TemporaryDirectory(prefix="fortex-backup-") as directory:
                stage = "dump_and_validation"
                path, size, sha1, entries = create_dump(config, Path(directory), run_id)
                event("LOCAL_VALIDATED", run_id, file=path.name, bytes=size,
                      sha1=sha1, entries=entries, postgres_version=PG_VERSION)
                stage = "upload_and_verification"
                file_id = remote.upload_verified(path, size, sha1, run_id)
                result = {"file": path.name, "bytes": size, "sha1": sha1, "entries": entries,
                          "remote": f"b2://{config.bucket}/{config.prefix}{path.name}",
                          "file_id": file_id}
                stage = "cleanup"
        # No SUCCESS until both verification and resource cleanup have completed.
        event("SUCCESS", run_id, **result, duration_seconds=round(time.monotonic() - started, 2))
        return 0
    except BaseException as error:
        code = str(error) if isinstance(error, BackupError) else "operation_failed"
        event("ERROR", run_id, stage=stage, code=code,
              duration_seconds=round(time.monotonic() - started, 2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
