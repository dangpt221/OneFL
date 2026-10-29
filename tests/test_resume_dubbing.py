"""Resume is idempotent for the current dub, preserving unrelated job locks."""
import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import func, select
from app.api.v1.projects import resume_project_dubbing
from app.models.project import Project
from app.models.job import Job
from app.services.job_service import job_service
from tests.test_reliability import isolated_db


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['QUEUED', 'RUNNING'])
async def test_active_dubbing_resume_returns_same_job(isolated_db, status):
    project = Project(title='active dub', last_dub_config={'voice': 'nova'})
    isolated_db.add(project)
    await isolated_db.commit()
    job = await job_service.enqueue(isolated_db, project.id, 'DUBBING', {'voice': 'nova'})
    job.status = status
    # The persisted job is sufficient even if legacy project config is absent.
    project.last_dub_config = None
    await isolated_db.commit()
    for _ in range(2):
        result = await resume_project_dubbing(project.id, BackgroundTasks(), isolated_db)
        assert result['job_id'] == job.id and result['already_active'] is True
        assert result['status'] == status
    assert await isolated_db.scalar(select(func.count(Job.id))) == 1


@pytest.mark.asyncio
async def test_interrupted_saved_dubbing_queues_once(isolated_db):
    project = Project(title='interrupted dub', status='FAILED', last_dub_config={'voice': 'nova', 'speed': 1.2})
    isolated_db.add(project)
    await isolated_db.commit()
    first = await resume_project_dubbing(project.id, BackgroundTasks(), isolated_db)
    second = await resume_project_dubbing(project.id, BackgroundTasks(), isolated_db)
    assert second['job_id'] == first['job_id']
    assert second['already_active']
    job = await isolated_db.get(Job, first['job_id'])
    assert job.payload['voice'] == 'nova' and job.payload['speed'] == 1.2
    assert await isolated_db.scalar(select(func.count(Job.id))) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('kind,cancelling', [('BURN', False), ('DUBBING', True)])
async def test_resume_never_replaces_other_or_cancelling_job(isolated_db, kind, cancelling):
    project = Project(title='preserve owner', last_dub_config={'voice': 'nova'})
    isolated_db.add(project)
    await isolated_db.commit()
    job = await job_service.enqueue(isolated_db, project.id, kind, {})
    job.cancel_requested = cancelling
    await isolated_db.commit()
    job_id = job.id
    with pytest.raises(HTTPException) as error:
        await resume_project_dubbing(project.id, BackgroundTasks(), isolated_db)
    assert error.value.status_code == 409
    await isolated_db.refresh(project)
    assert project.active_job_id == job_id
    assert await isolated_db.scalar(select(func.count(Job.id))) == 1


@pytest.mark.asyncio
async def test_resume_without_saved_config_does_not_invent_configuration(isolated_db):
    project = Project(title='no saved config', status='FAILED')
    isolated_db.add(project)
    await isolated_db.commit()
    with pytest.raises(HTTPException) as error:
        await resume_project_dubbing(project.id, BackgroundTasks(), isolated_db)
    assert error.value.status_code == 409
    assert 'configuration' in error.value.detail
    assert await isolated_db.scalar(select(func.count(Job.id))) == 0


@pytest.mark.asyncio
async def test_resume_racing_with_winner_returns_winners_job(isolated_db, monkeypatch):
    from app.api.v1 import tts
    project = Project(title='race', status='FAILED', last_dub_config={'voice': 'nova'})
    isolated_db.add(project)
    await isolated_db.commit()
    async def racing_start(project_id, background_tasks, config, db):
        await job_service.enqueue(db, project_id, 'DUBBING', config.model_dump())
        raise HTTPException(409, 'Project already has an active job')
    monkeypatch.setattr(tts, 'start_project_dubbing', racing_start)
    result = await resume_project_dubbing(project.id, BackgroundTasks(), isolated_db)
    assert result['already_active']
    assert result['job_id'] == project.active_job_id
    assert await isolated_db.scalar(select(func.count(Job.id))) == 1


@pytest.mark.asyncio
async def test_resume_does_not_clear_an_inconsistent_job_reference(isolated_db):
    project = Project(title='orphan ownership', active_job_id='missing-job', last_dub_config={'voice': 'nova'})
    isolated_db.add(project)
    await isolated_db.commit()
    with pytest.raises(HTTPException) as error:
        await resume_project_dubbing(project.id, BackgroundTasks(), isolated_db)
    assert error.value.status_code == 409
    await isolated_db.refresh(project)
    assert project.active_job_id == 'missing-job'
    assert await isolated_db.scalar(select(func.count(Job.id))) == 0
