import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class SubtitleCue(Base):
    __tablename__ = "subtitle_cues"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    cue_index = Column(Integer, nullable=False, index=True)
    start_time = Column(Float, nullable=False)  # in seconds (e.g. 12.345)
    end_time = Column(Float, nullable=False)    # in seconds (e.g. 15.678)
    
    original_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=True)
    
    speaker_tag = Column(String(50), default="SPEAKER_00", index=True)
    target_speaker_tag = Column(String(50), nullable=True)  # Who this speaker is talking to
    
    # Quality metrics
    cps = Column(Float, default=0.0)             # Characters per second
    line_count = Column(Integer, default=1)
    max_line_length = Column(Integer, default=0)
    has_guardrail_violation = Column(Boolean, default=False)
    violation_notes = Column(Text, nullable=True)
    
    is_edited = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="cues")
