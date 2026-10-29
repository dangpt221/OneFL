"""Isolated scheduler and real FFmpeg metadata benchmarks; never uses the live DSN."""
import argparse
import asyncio
from contextlib import asynccontextmanager
import importlib
import json
import os
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'tmp' / 'performance'
WORK.mkdir(parents=True, exist_ok=True)
os.environ.update({'DATABASE_URL': 'sqlite+aiosqlite:///:memory:', 'STORAGE_DRIVER': 'local',
    'OUTPUT_DIR': str(WORK / 'outputs'), 'UPLOAD_DIR': str(WORK / 'uploads'),
    'TEMP_SCRATCH_DIR': str(WORK / 'scratch'), 'API_ACCESS_TOKEN': '', 'AUTH_USERS': '{}',
    'GEMINI_API_KEY': '', 'OPENAI_API_KEY': '', 'HF_TOKEN': '', 'ENV': 'development',
    'ENABLE_VISUAL_CONTEXT': 'false', 'ENABLE_SPEAKER_PROFILER': 'false'})
sys.path.insert(0, str(ROOT / 'backend'))

from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.database import Base
from app.models.job import Job
from app.models.project import Project
from app.services import media_process


async def scheduler_sample():
    module = importlib.import_module('app.services.job_service')
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    @asynccontextmanager
    async def sessions():
        async with factory() as db:
            yield db
    starts, finishes = [], []
    finished = asyncio.Event()
    worker = module.JobService()
    async def synthetic(job_id):
        starts.append(time.perf_counter())
        await asyncio.sleep(.025)
        async with sessions() as db:
            await db.execute(update(Job).where(Job.id == job_id).values(status='SUCCEEDED'))
            await db.execute(update(Project).where(Project.active_job_id == job_id).values(active_job_id=None))
            await db.commit()
        finishes.append(time.perf_counter())
        if len(finishes) == 3:
            finished.set()
    try:
        with patch.object(module, 'get_async_session', sessions), patch.object(worker, '_execute', synthetic), \
             patch.object(settings, 'JOB_POLL_SECONDS', .02), patch.object(settings, 'JOB_LEASE_SECONDS', 45):
            async with sessions() as db:
                for i in range(3):
                    p = Project(title=f'Synthetic scheduling {i}')
                    db.add(p)
                    await db.commit()
                    await worker.enqueue(db, p.id, 'PIPELINE', {})
            started = time.perf_counter()
            await worker.start()
            try:
                await asyncio.wait_for(finished.wait(), 30)
            finally:
                await worker.stop()
            return {'elapsed_ms': (finishes[-1] - started) * 1000,
                    'dispatch_gap_ms': [(starts[i] - finishes[i - 1]) * 1000 for i in range(1, 3)]}
    finally:
        await engine.dispose()


async def main(label):
    settings.ensure_directories()
    samples = [await scheduler_sample() for _ in range(2)]
    source = WORK / 'probe_fixture.wav'
    await media_process.run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i',
        'sine=frequency=440:sample_rate=24000', '-t', '1', str(source)])
    original = media_process.run_media
    calls = 0
    async def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return await original(*args, **kwargs)
    durations = []
    with patch.object(media_process, 'run_media', counted):
        for _ in range(10):
            start = time.perf_counter()
            await media_process.probe_media(source, require_audio=True)
            durations.append((time.perf_counter() - start) * 1000)
    result = {'label': label, 'workload': {'scheduler_jobs': 3, 'repeats': 2, 'work_ms': 25,
        'job_poll_seconds': .02, 'job_lease_seconds': 45, 'probe_calls': 10, 'media_seconds': 1},
        'scheduler': samples, 'scheduler_gap_median_ms': statistics.median([n for s in samples for n in s['dispatch_gap_ms']]),
        'probe_ms': durations, 'probe_warm_median_ms': statistics.median(durations[1:]), 'probe_subprocesses': calls}
    (WORK / f'{label}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', choices=['before', 'after'], required=True)
    asyncio.run(main(parser.parse_args().label))
