"""Persisted job state and an expiring lease for the single-host executor."""
import time
import uuid
from sqlalchemy import Column, String, Float, Boolean, Text, JSON, ForeignKey
from app.database import Base


class Job(Base):
    __tablename__ = 'jobs'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default='QUEUED', index=True)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    owner = Column(String(36), nullable=True)
    created_at = Column(Float, default=time.time, nullable=False)
    heartbeat_at = Column(Float, nullable=True)
    finished_at = Column(Float, nullable=True)
    error = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)


class WorkerLease(Base):
    __tablename__ = 'worker_leases'
    name = Column(String(30), primary_key=True)
    owner = Column(String(36), nullable=False)
    expires_at = Column(Float, nullable=False)
