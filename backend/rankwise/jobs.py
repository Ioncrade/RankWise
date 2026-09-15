"""Bounded background execution with durable job state."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol

from .catalog import Catalog, JobRecord
from .errors import AppError

logger = logging.getLogger(__name__)
JobTask = Callable[[], dict[str, Any]]


class JobRunner(Protocol):
    def submit(
        self, tenant_id: str, kind: str, payload: dict[str, Any], task: JobTask
    ) -> JobRecord: ...


class BackgroundJobRunner:
    def __init__(self, catalog: Catalog, *, workers: int = 2) -> None:
        self.catalog = catalog
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="rankwise-job")

    def submit(
        self, tenant_id: str, kind: str, payload: dict[str, Any], task: JobTask
    ) -> JobRecord:
        record = self.catalog.create_job(tenant_id, kind, payload)
        self.executor.submit(self._execute, record.job_id, task)
        return record

    def _execute(self, job_id: str, task: JobTask) -> None:
        self.catalog.update_job(job_id, "running")
        try:
            result = task()
        except AppError as exc:
            self.catalog.update_job(
                job_id,
                "failed",
                error={"code": exc.code, "message": exc.message, "details": exc.details},
            )
        except Exception:
            logger.exception("Background job failed", extra={"job_id": job_id})
            self.catalog.update_job(
                job_id,
                "failed",
                error={"code": "job_failed", "message": "Background processing failed"},
            )
        else:
            self.catalog.update_job(job_id, "succeeded", result=result)


class InlineJobRunner(BackgroundJobRunner):
    """Runs immediately while retaining the same persisted state machine for tests."""

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    def submit(
        self, tenant_id: str, kind: str, payload: dict[str, Any], task: JobTask
    ) -> JobRecord:
        record = self.catalog.create_job(tenant_id, kind, payload)
        self._execute(record.job_id, task)
        return self.catalog.get_job(record.job_id, tenant_id)
