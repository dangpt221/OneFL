"""Bounded data contracts shared by Agent adapters and the decision loop."""
from typing import Any, Literal
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator
from app.schemas.tts import ProjectDubRequest


class ToolInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


def seconds(value: Any) -> float:
    if isinstance(value, str) and ':' in value:
        parts = value.replace(',', '.').split(':')
        if len(parts) != 3:
            raise ValueError('Expected HH:MM:SS.mmm timestamp')
        hours, minutes, secs = map(float, parts)
        if hours < 0 or not 0 <= minutes < 60 or not 0 <= secs < 60:
            raise ValueError('Timestamp out of range')
        return hours * 3600 + minutes * 60 + secs
    return float(value)


class AgentCue(BaseModel):
    model_config = ConfigDict(extra='allow', allow_inf_nan=False)
    cue_index: int = Field(ge=1, validation_alias=AliasChoices('cue_index', 'id'))
    original_text: str = Field('', max_length=10000, validation_alias=AliasChoices('original_text', 'text'))
    translated_text: str | None = Field(None, max_length=10000)
    speaker_tag: str = Field('SPEAKER_00', min_length=1, max_length=100, validation_alias=AliasChoices('speaker_tag', 'speaker'))
    start_time: float = Field(0, ge=0)
    end_time: float = Field(gt=0)

    @model_validator(mode='before')
    @classmethod
    def normalize_timing(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        row = dict(value)
        row['start_time'] = seconds(row.get('start', row.get('start_time', 0)))
        row['end_time'] = seconds(row.get('end', row.get('end_time', row['start_time'] + float(row.get('duration', 3)))))
        return row

    @model_validator(mode='after')
    def ordered_timing(self):
        if self.end_time <= self.start_time:
            raise ValueError('Cue end must be after start')
        return self


def normalize_cues(cues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [AgentCue.model_validate({'cue_index': c.get('cue_index', c.get('id', i + 1)), **c}).model_dump()
            for i, c in enumerate(cues)]
    if len({c['cue_index'] for c in rows}) != len(rows):
        raise ValueError('Cue indices must be unique')
    return rows


class ToolOutcome(BaseModel):
    model_config = ConfigDict(extra='allow')
    success: bool = True
    status: str = 'OK'


class QueuedOutcome(ToolOutcome):
    status: Literal['QUEUED']
    job_id: str
    project_id: str


class JobOutcome(ToolOutcome):
    status: Literal['QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED']
    job_id: str
    project_id: str
    error: str | None = None
    result: dict[str, Any] | None = None
    artifact_current: bool


class AgentDecision(ToolInput):
    thought: str = Field('', max_length=2000)
    action: str | None = Field(None, min_length=1, max_length=100)
    action_input: dict[str, Any] = Field(default_factory=dict)
    final_answer: str | None = Field(None, min_length=1, max_length=8000)

    @model_validator(mode='after')
    def choose_one(self):
        if bool(self.action) == bool(self.final_answer):
            raise ValueError('Provide exactly one action or final_answer')
        return self


class ProjectInput(ToolInput):
    project_id: str = Field(min_length=1, max_length=36)


class ProjectDubInput(ProjectDubRequest, ProjectInput):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class ProjectContextInput(ProjectInput):
    offset: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=100)


class ProjectPipelineInput(ProjectInput):
    stage: Literal['INGESTING', 'ASR_PROCESSING', 'SPEAKER_PROFILING', 'TRANSLATING'] | None = None
    force_reprocess: bool = False


class JobInput(ProjectInput):
    job_id: str = Field(min_length=1, max_length=36)


class WaitJobInput(JobInput):
    timeout_seconds: float = Field(5, ge=0, le=30)


def bounded_observation(value: Any, depth: int = 0) -> Any:
    """Keep IDs/status/artifact metadata while preventing transcripts filling history."""
    if isinstance(value, str):
        return value[:1500] + ('… [truncated]' if len(value) > 1500 else '')
    if depth > 5:
        return '[nested data omitted]'
    if isinstance(value, list):
        result = [bounded_observation(x, depth + 1) for x in value[:10]]
        return result + ([{'omitted_items': len(value) - 10}] if len(value) > 10 else [])
    if isinstance(value, dict):
        return {k: bounded_observation(v, depth + 1) for k, v in list(value.items())[:40]}
    return value
