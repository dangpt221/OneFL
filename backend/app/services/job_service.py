"""One durable queue per database with atomic project admission and safe cancel."""
import asyncio
import logging
import time
import uuid
import os
from contextlib import suppress
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, update, func, or_
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import get_async_session
from app.models.job import Job, WorkerLease
from app.models.project import Project

logger = logging.getLogger(__name__)


class JobService:
    def __init__(self):
        self.owner = str(uuid.uuid4())
        self.runner = None
        self.active: dict[str, asyncio.Task] = {}
        self.leader = False
        self.last_cleanup = time.monotonic()
        self.process_lock = None
        self._wake_event = None

    async def enqueue(self, db, project_id: str, kind: str, payload: dict[str, Any], *, project_updates: dict | None = None) -> Job:
        if kind not in {'PIPELINE', 'BURN', 'DUBBING', 'DOWNLOAD', 'RETRANSLATE', 'AGENT_TOOL'}:
            raise ValueError('Unsupported job kind')
        count = await db.scalar(select(func.count(Job.id)).where(Job.status == 'QUEUED'))
        if count >= settings.MAX_QUEUED_JOBS:
            raise HTTPException(429, 'Job queue is full')
        job = Job(id=str(uuid.uuid4()), project_id=project_id, kind=kind, payload=payload)
        values = dict(project_updates or {})
        values.update(burned_video_path=None, burned_video_url=None)
        display_kind = ('BURN' if payload.get('operation') == 'BURN_FILE' else 'TRANSCRIBE') if kind == 'AGENT_TOOL' else kind
        if display_kind != 'BURN':
            values.update(dubbed_audio_path=None, dubbed_audio_url=None, dubbed_video_path=None, dubbed_video_url=None)
        values.update(active_job_id=job.id, last_job_kind=display_kind, status='QUEUED', current_stage='QUEUED', progress_percentage=0, error_message=None)
        claimed = await db.execute(update(Project).where(
            Project.id == project_id, Project.active_job_id.is_(None)
        ).values(**values))
        if claimed.rowcount != 1:
            await db.rollback()
            raise HTTPException(409, 'Project already has an active job')
        db.add(job)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        if self.runner and self._wake_event and not self.runner.done():
            loop = self.runner.get_loop()
            if not loop.is_closed():
                loop.call_soon_threadsafe(self._wake_event.set)
        return job

    async def cancel(self, db, project_id: str) -> None:
        project = await db.get(Project, project_id, populate_existing=True)
        if not project or not project.active_job_id:
            return
        job = await db.get(Job, project.active_job_id, populate_existing=True)
        if not job:
            raise HTTPException(409, 'Job ownership is inconsistent; restart recovery is required')
        job.cancel_requested = True
        job_id = job.id
        queued = job.status == 'QUEUED'
        if queued:
            job.status, job.finished_at = 'CANCELLED', time.time()
            project.active_job_id = None
        await db.commit()
        task = self.active.get(job_id)
        if task:
            if not task.cancelling():
                task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=30)
            except asyncio.CancelledError:
                pass  # The job task acknowledged cancellation.
            except asyncio.TimeoutError:
                raise HTTPException(409, 'Cancellation is pending until the current inference exits safely')
        elif not queued and job.status not in {'FAILED', 'CANCELLED', 'SUCCEEDED'}:
            raise HTTPException(409, 'Cancellation requested; wait for the worker acknowledgement')
        await db.refresh(project)

    async def start(self):
        if not self.runner:
            self._wake_event = asyncio.Event()
            self.runner = asyncio.create_task(self._run(), name='onefl-durable-queue')

    async def stop(self):
        if self.runner:
            self.runner.cancel()
            with suppress(asyncio.CancelledError):
                await self.runner
            self.runner = None
            self._wake_event = None
        # Shutdown must wait until cancelled media/inference has stopped before
        # relinquishing the lease to another process.
        await self._drain_active()
        self.active.clear()
        async with get_async_session() as db:
            await db.execute(update(WorkerLease).where(WorkerLease.owner == self.owner).values(expires_at=0))
            await db.commit()
        self.leader = False
        self._release_process_lock()

    async def _drain_active(self):
        tasks = set(self.active.values())
        for task in tasks:
            if not task.done() and not task.cancelling():
                task.cancel()
        while tasks:
            _, tasks = await asyncio.wait(tasks, timeout=min(5, settings.JOB_LEASE_SECONDS / 3))
            if tasks:
                try:
                    if not await self._lease():
                        logger.error('Lease lost while waiting for native inference to stop')
                except Exception:
                    logger.exception('Unable to renew draining worker lease; local process lock remains held')
        await asyncio.gather(*self.active.values(), return_exceptions=True)

    def _acquire_process_lock(self):
        # The queue uses local media. An OS lock also fences API processes while
        # the DB is unavailable or native inference is acknowledging cancellation.
        if self.process_lock:
            return True
        handle = open(settings.TEMP_SCRATCH_DIR / '.worker.lock', 'a+b')
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self.process_lock = handle
        return True

    def _release_process_lock(self):
        if self.process_lock:
            self.process_lock.close()
            self.process_lock = None

    async def _lease(self) -> bool:
        async with get_async_session() as db:
            now = time.time()
            result = await db.execute(update(WorkerLease).where(
                WorkerLease.name == 'media',
                or_(WorkerLease.expires_at < now, WorkerLease.owner == self.owner),
            ).values(owner=self.owner, expires_at=now + settings.JOB_LEASE_SECONDS))
            if not result.rowcount:
                db.add(WorkerLease(name='media', owner=self.owner, expires_at=now + settings.JOB_LEASE_SECONDS))
                try:
                    await db.commit()
                    return True
                except IntegrityError:
                    await db.rollback()
                    return False
            await db.commit()
            return True

    async def _recover(self):
        async with get_async_session() as db:
            jobs = (await db.execute(select(Job).where(Job.status == 'RUNNING'))).scalars().all()
            for job in jobs:
                job.status = 'CANCELLED' if job.cancel_requested else 'QUEUED'
                job.owner = None
                if job.cancel_requested:
                    job.finished_at = time.time()
                    await db.execute(update(Project).where(Project.active_job_id == job.id).values(active_job_id=None, status='CANCELLED', current_stage='CANCELLED'))
            # Legacy orphan states have no resumable job metadata. Mark them
            # interrupted so the UI offers an explicit retry, not a false spinner.
            await db.execute(update(Project).where(
                Project.active_job_id.is_(None),
                Project.status.in_(['PROCESSING', 'INGESTING', 'DUBBING', 'BURNING']),
            ).values(status='FAILED', error_message='Previous process was interrupted; retry from the saved checkpoint'))
            await db.commit()

    async def _wait_for_work(self):
        if not self._wake_event:
            await asyncio.sleep(settings.JOB_POLL_SECONDS)
            return
        try:
            await asyncio.wait_for(self._wake_event.wait(), settings.JOB_POLL_SECONDS)
        except asyncio.TimeoutError:
            pass  # Cross-process producers are discovered by the polling timeout.

    async def _run(self):
        while True:
            try:
                if self._wake_event:
                    self._wake_event.clear()
                if not self._acquire_process_lock():
                    await self._wait_for_work()
                    continue
                acquired = await self._lease()
                if acquired and not self.leader:
                    await self._recover()
                self.leader = acquired
                if acquired:
                    if time.monotonic() - self.last_cleanup >= 3600:
                        from app.services.artifact_service import cleanup_expired_scratch
                        async with get_async_session() as cleanup_db:
                            await cleanup_expired_scratch(cleanup_db)
                        self.last_cleanup = time.monotonic()
                    async with get_async_session() as db:
                        job = (await db.execute(select(Job).where(Job.status == 'QUEUED').order_by(Job.created_at).limit(1))).scalar_one_or_none()
                        if job:
                            job_id = job.id
                            job.status, job.owner, job.heartbeat_at = 'RUNNING', self.owner, time.time()
                            await db.commit()
                    if job:
                        task = asyncio.create_task(self._execute(job_id))
                        self.active[job_id] = task
                        while not task.done():
                            done, _ = await asyncio.wait({task}, timeout=min(5, settings.JOB_LEASE_SECONDS / 3))
                            if done:
                                break
                            if not await self._lease():
                                if not task.cancelling():
                                    task.cancel()
                                await asyncio.gather(task, return_exceptions=True)
                                raise RuntimeError('Worker lease lost')
                            async with get_async_session() as db:
                                heartbeat = await db.execute(update(Job).where(
                                    Job.id == job_id, Job.status == 'RUNNING'
                                ).values(heartbeat_at=time.time()))
                                if heartbeat.rowcount != 1:
                                    logger.warning('Monitored job %s was removed or stopped; cancelling its task', job_id)
                                    if not task.cancelling():
                                        task.cancel()
                                    break
                                current = await db.get(Job, job_id)
                                if current and current.cancel_requested:
                                    if not task.cancelling():
                                        task.cancel()
                                await db.commit()
                        await asyncio.gather(task, return_exceptions=True)
                        self.active.pop(job_id, None)
                        continue  # Drain queued work immediately after completion.
                await self._wait_for_work()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception('Durable queue poll failed')
                await self._drain_active()
                self.active.clear()
                self.leader = False
                await asyncio.sleep(3)

    async def _execute(self, job_id):
        from app.security import current_user
        async with get_async_session() as db:
            job = await db.get(Job, job_id)
            project = await db.get(Project, job.project_id) if job else None
            if not project:
                return
            actor = project.user_id
        token = current_user.set(actor)
        try:
            await self._execute_owned(job_id)
        finally:
            current_user.reset(token)

    async def _execute_owned(self, job_id):
        status, error = 'SUCCEEDED', None
        result = None
        try:
            async with get_async_session() as db:
                job = await db.get(Job, job_id)
                if job.cancel_requested:
                    raise asyncio.CancelledError()
                pid, kind, payload = job.project_id, job.kind, dict(job.payload)
            from app.services.workflow_engine import workflow_engine
            if kind == 'DUBBING':
                from app.api.v1.tts import _run_dubbing_task
                await _run_dubbing_task(pid, **payload)
            else:
                async with get_async_session() as db:
                    if kind == 'AGENT_TOOL':
                        from app.services.agent_project_service import execute_media_job
                        result = await execute_media_job(db, pid, payload['operation'], payload['arguments'])
                    elif kind == 'PIPELINE':
                        await workflow_engine.run_pipeline(db, pid, **payload)
                    elif kind == 'BURN':
                        await workflow_engine.burn_project_video(db, pid)
                    elif kind == 'DOWNLOAD':
                        from app.services.ingestion_service import download_project
                        await download_project(db, pid, **payload)
                    elif kind == 'RETRANSLATE':
                        from app.api.v1.subtitles import _retranslate_cues
                        from app.schemas.translation import RetranslateRequest
                        await _retranslate_cues(pid, RetranslateRequest(**payload), db)
        except asyncio.CancelledError:
            status, error = 'CANCELLED', 'Job cancelled safely'
        except Exception as exc:
            status, error = 'FAILED', str(exc) or type(exc).__name__
            logger.exception('Job %s failed', job_id)
        async with get_async_session() as db:
            job = await db.get(Job, job_id)
            if job:
                job.status, job.error, job.finished_at = status, error, time.time()
                if status == 'SUCCEEDED':
                    project = await db.get(Project, job.project_id)
                    result = result or {key: getattr(project, key) for key in (
                        'content_revision', 'burned_video_url', 'dubbed_video_url', 'subtitles_ass_path')}
                    job.result = result
                values = {'active_job_id': None}
                if status != 'SUCCEEDED':
                    values.update(status=status, current_stage=status, error_message=error)
                await db.execute(update(Project).where(Project.active_job_id == job_id).values(**values))
                await db.commit()
                from app.services.ws_manager import ws_manager
                await ws_manager.broadcast_to_project(job.project_id, 'STATUS_UPDATE', {'status': status if status != 'SUCCEEDED' else None, 'message': error})


job_service = JobService()
