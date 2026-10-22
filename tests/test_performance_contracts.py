"""Latency/resource invariants without relaxing media validation or cancellation."""
import asyncio
from unittest.mock import AsyncMock
import pytest
import pytest_asyncio
from app.config import settings
from app.models.project import Project
from tests.test_reliability import isolated_db
from tests.test_job_worker import worker_for


@pytest_asyncio.fixture
async def worker_db(isolated_db, tmp_path):
    """Worker cancellation may invalidate a connection: keep its DB on disk.

    SQLite :memory: loses all tables when cancellation replaces its sole pooled
    connection. This fixture keeps independent sessions realistic under load.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.database import Base
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "scheduler.db"}')
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            yield db
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_completed_jobs_dispatch_without_waiting_for_heartbeat(worker_db, monkeypatch):
    isolated_db = worker_db
    worker = worker_for(isolated_db, monkeypatch)
    monkeypatch.setattr(worker, '_lease', AsyncMock(return_value=True))
    monkeypatch.setattr(worker, '_recover', AsyncMock())
    monkeypatch.setattr(worker, '_acquire_process_lock', lambda: True)
    monkeypatch.setattr(settings, 'JOB_POLL_SECONDS', .01)
    monkeypatch.setattr(settings, 'JOB_LEASE_SECONDS', 45)
    ids = []
    for i in range(2):
        p = Project(title=f'fast job {i}')
        isolated_db.add(p)
        await isolated_db.commit()
        ids.append((await worker.enqueue(isolated_db, p.id, 'PIPELINE', {})).id)
    done = asyncio.Event()
    async def finish(job_id):
        from app.models.job import Job
        from sqlalchemy import update
        await isolated_db.execute(update(Job).where(Job.id == job_id).values(status='SUCCEEDED'))
        await isolated_db.commit()
        if job_id == ids[-1]:
            done.set()
    monkeypatch.setattr(worker, '_execute', finish)
    runner = asyncio.create_task(worker._run())
    try:
        await asyncio.wait_for(done.wait(), .8)
    finally:
        runner.cancel()
        await asyncio.gather(runner, return_exceptions=True)


@pytest.mark.asyncio
async def test_probe_reuses_metadata_and_invalidates_on_file_change(tmp_path, monkeypatch):
    from app.services import media_process
    path = tmp_path / 'audio.wav'
    path.write_bytes(b'fixture')
    run = AsyncMock(return_value=(b'', b'Duration: 00:00:01.00 Audio: pcm_s16le'))
    monkeypatch.setattr(media_process, 'run_media', run)
    assert await media_process.probe_media(path, require_audio=True) == 1
    assert await media_process.probe_media(path, require_audio=True) == 1
    assert run.await_count == 1
    with pytest.raises(RuntimeError):
        await media_process.probe_media(path, require_video=True)
    path.write_bytes(b'changed-size')
    run.return_value = (b'', b'not valid media')
    with pytest.raises(RuntimeError):
        await media_process.probe_media(path, require_audio=True)
    assert run.await_count == 2


@pytest.mark.asyncio
async def test_concurrent_identical_probes_share_one_validation(tmp_path, monkeypatch):
    from app.services import media_process
    path = tmp_path / 'shared.wav'
    path.write_bytes(b'fixture')
    async def run(*args, **kwargs):
        await asyncio.sleep(.01)
        return b'', b'Duration: 00:00:01.00 Audio: pcm_s16le'
    process = AsyncMock(side_effect=run)
    monkeypatch.setattr(media_process, 'run_media', process)
    assert await asyncio.gather(*(media_process.probe_media(path, require_audio=True) for _ in range(12))) == [1] * 12
    assert process.await_count == 1


@pytest.mark.asyncio
async def test_tts_task_count_is_bounded_by_workers_not_cue_count(tmp_path, monkeypatch):
    from pathlib import Path
    from app.services import media_process
    from app.services.asr_service import ASRService
    from app.services.tts_service import tts_service
    monkeypatch.setattr(settings, 'TEMP_SCRATCH_DIR', tmp_path)
    if hasattr(settings, 'TTS_MAX_CONCURRENCY'):
        monkeypatch.setattr(settings, 'TTS_MAX_CONCURRENCY', 8)
    created = 0
    original = asyncio.create_task
    def counted(coro, *args, **kwargs):
        nonlocal created
        created += 1
        return original(coro, *args, **kwargs)
    async def speech(text, voice, model, speed, output):
        output.write_bytes(b'provider fixture')
    async def run(args, **kwargs):
        Path(args[-1]).write_bytes(b'\0' * 100)
        await asyncio.sleep(0)
        return b'', b''
    async def blocking(fn):
        return fn()
    monkeypatch.setattr(asyncio, 'create_task', counted)
    monkeypatch.setattr(tts_service, 'synthesize_speech', speech)
    monkeypatch.setattr(media_process, 'probe_media', AsyncMock(return_value=.1))
    monkeypatch.setattr(media_process, 'validate_duration', AsyncMock(return_value=2))
    monkeypatch.setattr(media_process, 'run_media', run)
    monkeypatch.setattr(ASRService, '_blocking', blocking)
    cues = [dict(cue_index=i + 1, start_time=0., end_time=1., translated_text=f'Line {i}') for i in range(200)]
    await tts_service.dub_project_timeline(cues, 2, tmp_path / 'dub.mp3')
    assert created <= 8, f'Created {created} tasks for 200 cues instead of a bounded worker pool'


@pytest.mark.asyncio
@pytest.mark.parametrize('local_producer', [True, False])
async def test_idle_worker_wakes_locally_and_polls_other_producers(worker_db, monkeypatch, local_producer):
    isolated_db = worker_db
    from app.services.job_service import JobService
    worker = worker_for(isolated_db, monkeypatch)
    monkeypatch.setattr(worker, '_lease', AsyncMock(return_value=True))
    monkeypatch.setattr(worker, '_recover', AsyncMock())
    monkeypatch.setattr(worker, '_acquire_process_lock', lambda: True)
    monkeypatch.setattr(settings, 'JOB_POLL_SECONDS', 30 if local_producer else .02)
    idle, picked = asyncio.Event(), asyncio.Event()
    wait = worker._wait_for_work
    async def idle_wait():
        idle.set()
        await wait()
    async def execute(job_id):
        picked.set()
    monkeypatch.setattr(worker, '_wait_for_work', idle_wait)
    monkeypatch.setattr(worker, '_execute', execute)
    project = Project(title='wake from idle')
    isolated_db.add(project)
    await isolated_db.commit()
    await worker.start()
    try:
        await asyncio.wait_for(idle.wait(), 1)
        producer = worker if local_producer else JobService()
        await producer.enqueue(isolated_db, project.id, 'PIPELINE', {})
        await asyncio.wait_for(picked.wait(), .8)
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_metadata_cache_evicts_old_files_and_never_caches_errors(tmp_path, monkeypatch):
    from app.services import media_process
    process = AsyncMock(return_value=(b'', b'Duration: 00:00:01.00 Audio: pcm_s16le'))
    monkeypatch.setattr(media_process, 'run_media', process)
    first = tmp_path / '0.wav'
    for i in range(513):
        path = tmp_path / f'{i}.wav'
        path.write_bytes(b'media fixture')
        await media_process.probe_media(path, require_audio=True)
    assert process.await_count == 513
    await media_process.probe_media(first, require_audio=True)
    assert process.await_count == 514
    failed = tmp_path / 'failed.wav'
    failed.write_bytes(b'invalid')
    process.side_effect = RuntimeError('probe failed')
    with pytest.raises(RuntimeError):
        await media_process.probe_media(failed)
    process.side_effect = None
    assert await media_process.probe_media(failed, require_audio=True) == 1
    assert process.await_count == 516
