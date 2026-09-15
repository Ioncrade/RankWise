from __future__ import annotations

import time
from pathlib import Path
from threading import Event

from rankwise.catalog import Catalog
from rankwise.errors import ValidationError
from rankwise.jobs import BackgroundJobRunner, InlineJobRunner


def test_background_runner_persists_state_transitions(tmp_path: Path) -> None:
    catalog = Catalog(tmp_path / "catalog.sqlite3")
    runner = BackgroundJobRunner(catalog, workers=1)
    started = Event()
    release = Event()

    def task():
        started.set()
        release.wait(timeout=1)
        return {"value": 42}

    job = runner.submit("tenant", "test", {}, task)
    assert started.wait(timeout=1)
    assert catalog.get_job(job.job_id, "tenant").status == "running"
    release.set()
    deadline = time.monotonic() + 1
    current = catalog.get_job(job.job_id, "tenant")
    while current.status != "succeeded" and time.monotonic() < deadline:
        time.sleep(0.01)
        current = catalog.get_job(job.job_id, "tenant")
    runner.executor.shutdown(wait=True)
    assert current.status == "succeeded"
    assert current.result == {"value": 42}


def test_inline_runner_persists_typed_failure(tmp_path: Path) -> None:
    catalog = Catalog(tmp_path / "catalog.sqlite3")
    runner = InlineJobRunner(catalog)

    def task():
        raise ValidationError("Bad task input", code="bad_task_input")

    job = runner.submit("tenant", "test", {}, task)
    assert job.status == "failed"
    assert job.error == {
        "code": "bad_task_input",
        "message": "Bad task input",
        "details": {},
    }
