import asyncio
import importlib
import time
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.models.project import Project
from app.models.job import Job
from tests.test_reliability import isolated_db


def worker_for(db, monkeypatch):
    module = importlib.import_module('app.services.job_service')
    factory = async_sessionmaker(db.bind, expire_on_commit=False)
    @asynccontextmanager
    async def sessions():
        async with factory() as session:
            yield session
    monkeypatch.setattr(module, 'get_async_session', sessions)
    return module.JobService()


@pytest.mark.asyncio
async def test_worker_lease_prevents_two_executors(isolated_db, monkeypatch):
    first = worker_for(isolated_db, monkeypatch)
    second = worker_for(isolated_db, monkeypatch)
    assert await first._lease()
    assert not await second._lease()


@pytest.mark.asyncio
async def test_restart_recovers_job_with_original_config(isolated_db, monkeypatch):
    worker = worker_for(isolated_db, monkeypatch)
    project = Project(title='restart')
    isolated_db.add(project)
    await isolated_db.commit()
    job = await worker.enqueue(isolated_db, project.id, 'DUBBING', {'voice': 'nova', 'speed': 1.3})
    job.status, job.owner, job.heartbeat_at = 'RUNNING', 'old-process', time.time() - 100
    await isolated_db.commit()
    await worker._recover()
    await isolated_db.refresh(job)
    assert job.status == 'QUEUED' and job.payload['speed'] == 1.3
    assert job.owner is None


@pytest.mark.asyncio
async def test_running_job_cancel_acknowledges_before_unlock(isolated_db, monkeypatch):
    from app.services.workflow_engine import workflow_engine
    worker = worker_for(isolated_db, monkeypatch)
    project = Project(title='cancel running')
    isolated_db.add(project)
    await isolated_db.commit()
    pid = project.id
    job = await worker.enqueue(isolated_db, pid, 'PIPELINE', {})
    job.status = 'RUNNING'
    await isolated_db.commit()
    entered, exited = asyncio.Event(), asyncio.Event()
    async def blocking_pipeline(db, project_id, **kwargs):
        entered.set()
        try:
            await asyncio.sleep(60)
        finally:
            exited.set()
    monkeypatch.setattr(workflow_engine, 'run_pipeline', blocking_pipeline)
    task = asyncio.create_task(worker._execute(job.id))
    worker.active[job.id] = task
    await entered.wait()
    await worker.cancel(isolated_db, pid)
    assert exited.is_set()
    await isolated_db.refresh(job)
    await isolated_db.refresh(project)
    assert job.status == 'CANCELLED' and project.active_job_id is None


@pytest.mark.asyncio
async def test_deleted_finished_job_does_not_break_worker_heartbeat(isolated_db, monkeypatch, caplog):
    from unittest.mock import AsyncMock
    from app.config import settings
    worker = worker_for(isolated_db, monkeypatch)
    project = Project(title='delete between completion and heartbeat')
    isolated_db.add(project)
    await isolated_db.commit()
    job = await worker.enqueue(isolated_db, project.id, 'PIPELINE', {})
    completed = asyncio.Event()
    real_sleep = asyncio.sleep

    async def finish_and_delete(job_id):
        # Project deletion can remove a finished job while the queue monitor sleeps.
        await isolated_db.delete(job)
        await isolated_db.commit()
        completed.set()

    async def fast_sleep(seconds):
        if seconds == min(5, settings.JOB_LEASE_SECONDS / 3):
            await completed.wait()
        await real_sleep(0.001)

    monkeypatch.setattr(worker, '_execute', finish_and_delete)
    monkeypatch.setattr(worker, '_lease', AsyncMock(return_value=True))
    monkeypatch.setattr(worker, '_recover', AsyncMock())
    monkeypatch.setattr(worker, '_acquire_process_lock', lambda: True)
    monkeypatch.setattr(asyncio, 'sleep', fast_sleep)
    runner = asyncio.create_task(worker._run())
    try:
        await asyncio.wait_for(completed.wait(), timeout=2)
        for _ in range(200):
            if not worker.active:
                break
            await real_sleep(0.005)
        assert not worker.active
        assert 'Durable queue poll failed' not in caplog.text
        assert not runner.done()
    finally:
        runner.cancel()
        await asyncio.gather(runner, return_exceptions=True)
