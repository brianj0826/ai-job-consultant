"""Validation models shared by career HTTP routes and suggestion workflows."""
from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class ResumeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    target_role: str = Field(default="", max_length=255)
    content: str = Field(min_length=1, max_length=200_000)
    source_name: Optional[str] = Field(default=None, max_length=512)
    is_primary: bool = False


class ResumeUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    target_role: Optional[str] = Field(default=None, max_length=255)
    content: Optional[str] = Field(default=None, min_length=1, max_length=200_000)
    source_name: Optional[str] = Field(default=None, max_length=512)
    is_primary: Optional[bool] = None


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    company: str = Field(default="", max_length=255)
    description: str = Field(min_length=1, max_length=200_000)
    source_url: Optional[str] = Field(default=None, max_length=2048)
    status: str = Field(default="saved", max_length=32)


class JobUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    company: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, min_length=1, max_length=200_000)
    source_url: Optional[str] = Field(default=None, max_length=2048)
    status: Optional[str] = Field(default=None, max_length=32)


class ApplicationCreate(BaseModel):
    job_id: int = Field(gt=0)
    stage: str = Field(default="saved", max_length=32)
    next_action: str = Field(default="", max_length=500)
    deadline: Optional[date] = None
    notes: str = Field(default="", max_length=20_000)


class ApplicationSuggestionCreate(BaseModel):
    """Pending application draft; the user may still need to choose a job."""

    job_id: Optional[int] = Field(default=None, gt=0)
    stage: str = Field(default="saved", max_length=32)
    next_action: str = Field(default="", max_length=500)
    deadline: Optional[date] = None
    notes: str = Field(default="", max_length=20_000)


class ApplicationUpdate(BaseModel):
    job_id: Optional[int] = Field(default=None, gt=0)
    stage: Optional[str] = Field(default=None, max_length=32)
    next_action: Optional[str] = Field(default=None, max_length=500)
    deadline: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=20_000)


class InterviewCreate(BaseModel):
    job_id: Optional[int] = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=255)
    status: str = Field(default="planned", max_length=32)
    overall_score: Optional[float] = Field(default=None, ge=0, le=100)


class InterviewUpdate(BaseModel):
    job_id: Optional[int] = Field(default=None, gt=0)
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    status: Optional[str] = Field(default=None, max_length=32)
    overall_score: Optional[float] = Field(default=None, ge=0, le=100)


class QuestionCreate(BaseModel):
    position: Optional[int] = Field(default=None, ge=1, le=500)
    question: str = Field(min_length=1, max_length=10_000)
    answer: str = Field(default="", max_length=50_000)
    score: Optional[float] = Field(default=None, ge=0, le=100)
    feedback: str = Field(default="", max_length=20_000)
    reference_answer: str = Field(default="", max_length=50_000)
    coaching_notes: str = Field(default="", max_length=20_000)


class QuestionUpdate(BaseModel):
    position: Optional[int] = Field(default=None, ge=1, le=500)
    question: Optional[str] = Field(default=None, min_length=1, max_length=10_000)
    answer: Optional[str] = Field(default=None, max_length=50_000)
    score: Optional[float] = Field(default=None, ge=0, le=100)
    feedback: Optional[str] = Field(default=None, max_length=20_000)
    reference_answer: Optional[str] = Field(default=None, max_length=50_000)
    coaching_notes: Optional[str] = Field(default=None, max_length=20_000)


class ReportCreate(BaseModel):
    kind: str = Field(max_length=32)
    title: str = Field(min_length=1, max_length=255)
    entity_type: Optional[str] = Field(default=None, max_length=32)
    entity_id: Optional[int] = Field(default=None, gt=0)
    summary: str = Field(min_length=1, max_length=200_000)
    payload: dict[str, Any] = Field(default_factory=dict)


class ReportUpdate(BaseModel):
    kind: Optional[str] = Field(default=None, max_length=32)
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    entity_type: Optional[str] = Field(default=None, max_length=32)
    entity_id: Optional[int] = Field(default=None, gt=0)
    summary: Optional[str] = Field(default=None, min_length=1, max_length=200_000)
    payload: Optional[dict[str, Any]] = None


class SkillCreate(BaseModel):
    skill: str = Field(min_length=1, max_length=255)
    target_level: str = Field(default="", max_length=255)
    status: str = Field(default="planned", max_length=32)
    progress: int = Field(default=0, ge=0, le=100)
    due_date: Optional[date] = None
    notes: str = Field(default="", max_length=20_000)


class SkillUpdate(BaseModel):
    skill: Optional[str] = Field(default=None, min_length=1, max_length=255)
    target_level: Optional[str] = Field(default=None, max_length=255)
    status: Optional[str] = Field(default=None, max_length=32)
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    due_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=20_000)


class SuggestedInterviewQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)
    reference_answer: str = Field(default="", max_length=50_000)
    coaching_notes: str = Field(default="", max_length=20_000)


class InterviewQuestionsSuggestionCreate(BaseModel):
    interview_id: Optional[int] = Field(default=None, gt=0)
    questions: list[SuggestedInterviewQuestion] = Field(min_length=1, max_length=10)


SuggestionResourceType = Literal[
    "resumes",
    "jobs",
    "applications",
    "interviews",
    "reports",
    "skills",
    "interview_questions",
]


class CareerSuggestionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_type: SuggestionResourceType
    title: str = Field(min_length=1, max_length=255)
    reason: str = Field(default="", max_length=1000)
    payload: dict[str, Any]
    relation_hints: dict[str, Any] = Field(default_factory=dict)


class CareerSuggestionRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=1)
    payload: dict[str, Any]


class CareerSuggestionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=1)


CreatePayload = Union[
    ResumeCreate,
    JobCreate,
    ApplicationCreate,
    InterviewCreate,
    ReportCreate,
    SkillCreate,
    InterviewQuestionsSuggestionCreate,
]
