import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class GlossaryTerm(Base):
    __tablename__ = "glossaries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    source_term = Column(String(255), nullable=False)
    target_term = Column(String(255), nullable=False)
    category = Column(String(100), default="general")  # PROPER_NAME, LOCATION, WEAPON_MECHA, RANK_REALM, ORGANIZATION, SLANG_IDIOM, DO_NOT_TRANSLATE
    context_note = Column(Text, nullable=True)
    priority = Column(String(20), default="normal")    # normal, high
    case_sensitive = Column(String(10), default="false") # true, false

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("project_id", "source_term", name="uq_project_source_term"),
    )

    project = relationship("Project", back_populates="glossaries")
