import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint, Float, Integer
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class SpeakerProfile(Base):
    __tablename__ = "speaker_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    speaker_tag = Column(String(50), nullable=False)  # SPEAKER_00, SPEAKER_01
    display_name = Column(String(100), nullable=True)  # Alex, Linh, John
    original_name = Column(String(100), nullable=True) # Tên gốc nguyên tác (Hán tự / English)
    aliases = Column(String(200), nullable=True)       # Biệt danh, danh xưng phụ
    avatar_color = Column(String(20), default="#6366f1") # Màu sắc đại diện
    gender = Column(String(20), default="unknown")     # male, female, neutral, unknown
    age_group = Column(String(50), default="adult")   # child, teen, young_adult, adult, senior
    role = Column(String(100), nullable=True)         # Director, Junior Dev, Friend, Host
    tone = Column(String(150), nullable=True)         # Polite, formal, casual, energetic
    tts_voice = Column(String(50), default="nova")    # nova, shimmer, alloy, onyx, echo, vi-VN-HoaiMyNeural
    tts_speed = Column(Float, default=1.0)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("project_id", "speaker_tag", name="uq_project_speaker"),
    )

    project = relationship("Project", back_populates="speakers")


class RelationshipMatrix(Base):
    __tablename__ = "relationship_matrices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    source_speaker = Column(String(50), nullable=False)  # SPEAKER_00
    target_speaker = Column(String(50), nullable=False)  # SPEAKER_01
    
    self_pronoun = Column(String(50), nullable=False)    # "Anh", "Tôi", "Em", "Bố", "Sếp"
    target_pronoun = Column(String(50), nullable=False)  # "Em", "Bạn", "Con", "Linh"
    relationship_type = Column(String(100), nullable=True) # "Sếp - Nhân viên", "Bạn thân", "Vợ - Chồng"
    honorific_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("project_id", "source_speaker", "target_speaker", name="uq_project_speaker_pair"),
    )

    project = relationship("Project", back_populates="relationships")
