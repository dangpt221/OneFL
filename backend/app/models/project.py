import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Video & Media URLs/Paths
    original_video_url = Column(Text, nullable=True)
    local_video_path = Column(Text, nullable=True)
    extracted_audio_path = Column(Text, nullable=True)
    burned_video_url = Column(Text, nullable=True)
    burned_video_path = Column(Text, nullable=True)
    dubbed_video_url = Column(Text, nullable=True)
    dubbed_video_path = Column(Text, nullable=True)
    dubbed_audio_url = Column(Text, nullable=True)
    dubbed_audio_path = Column(Text, nullable=True)
    default_voice = Column(String(50), default="vi-VN-HoaiMyNeural")
    subtitles_ass_path = Column(Text, nullable=True)
    subtitles_srt_path = Column(Text, nullable=True)

    # Metadata
    video_duration_seconds = Column(Float, default=0.0)
    source_language = Column(String(10), default="auto")  # en, zh, ja, ko, auto
    target_language = Column(String(10), default="vi")
    
    # Status: CREATED, INGESTING, ASR_PROCESSING, SPEAKER_PROFILING, TRANSLATING, WAITING_REVIEW, BURNING, COMPLETED, FAILED
    status = Column(String(50), default="CREATED", index=True)
    current_stage = Column(String(50), default="INITIALIZING")
    progress_percentage = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    # Configs
    settings_override = Column(JSON, nullable=True)  # custom llm, style, guardrail params

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    cues = relationship("SubtitleCue", back_populates="project", cascade="all, delete-orphan", order_by="SubtitleCue.cue_index")
    chunks = relationship("VideoChunk", back_populates="project", cascade="all, delete-orphan", order_by="VideoChunk.chunk_index")
    speakers = relationship("SpeakerProfile", back_populates="project", cascade="all, delete-orphan")
    relationships = relationship("RelationshipMatrix", back_populates="project", cascade="all, delete-orphan")
    glossaries = relationship("GlossaryTerm", back_populates="project", cascade="all, delete-orphan")


class VideoChunk(Base):
    __tablename__ = "video_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)

    audio_chunk_path = Column(Text, nullable=True)
    video_chunk_path = Column(Text, nullable=True)
    ass_chunk_path = Column(Text, nullable=True)
    burned_chunk_path = Column(Text, nullable=True)

    status = Column(String(50), default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    project = relationship("Project", back_populates="chunks")
