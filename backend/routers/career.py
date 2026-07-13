"""Authenticated CRUD endpoints for the structured career workspace."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.schemas.career import (
    ApplicationCreate,
    ApplicationUpdate,
    CareerSuggestionDecision,
    CareerSuggestionRevision,
    InterviewCreate,
    InterviewUpdate,
    JobCreate,
    JobUpdate,
    QuestionCreate,
    QuestionUpdate,
    ReportCreate,
    ReportUpdate,
    ResumeCreate,
    ResumeUpdate,
    SkillCreate,
    SkillUpdate,
)
from backend.services import career as career_service
from backend.services import career_suggestions as suggestion_service
from backend.services.access import current_user_id
from backend.services.auth import require_business_csrf, require_current_user


router = APIRouter()


def _changes(payload: BaseModel) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(exclude_unset=True)
    return payload.dict(exclude_unset=True)


def _values(payload: BaseModel) -> dict[str, Any]:
    """Serialize create models with their validated API defaults included."""
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return payload.dict()


def _call(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except career_service.CareerNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except career_service.CareerConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except career_service.CareerDataError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


class DeleteCareerDataRequest(BaseModel):
    confirmation: str


def _uid(current_user: dict) -> int:
    return current_user_id(current_user)


def require_career_data_guard(current_user: dict = Depends(require_current_user)):
    try:
        with career_service.career_data_guard(_uid(current_user)):
            yield
    except career_service.CareerConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


CAREER_WRITE_DEPENDENCIES = [
    Depends(require_business_csrf),
    Depends(require_career_data_guard),
]


# Resumes
@router.get("/resumes")
def resumes(limit: int = Query(100, ge=1, le=500), current_user: dict = Depends(require_current_user)):
    return _call(career_service.list_resumes, _uid(current_user), limit)


@router.post("/resumes", dependencies=CAREER_WRITE_DEPENDENCIES, status_code=201)
def create_resume(payload: ResumeCreate, current_user: dict = Depends(require_current_user)):
    return _call(career_service.create_resume, _uid(current_user), _values(payload))


@router.get("/resumes/{resume_id}")
def resume(resume_id: int, current_user: dict = Depends(require_current_user)):
    return _call(career_service.get_resume, _uid(current_user), resume_id)


@router.patch("/resumes/{resume_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def update_resume(resume_id: int, payload: ResumeUpdate, current_user: dict = Depends(require_current_user)):
    return _call(career_service.update_resume, _uid(current_user), resume_id, _changes(payload))


@router.delete("/resumes/{resume_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def delete_resume(resume_id: int, current_user: dict = Depends(require_current_user)):
    _call(career_service.delete_resume, _uid(current_user), resume_id)
    return {"ok": True}


# Jobs
@router.get("/jobs")
def jobs(limit: int = Query(100, ge=1, le=500), current_user: dict = Depends(require_current_user)):
    return _call(career_service.list_jobs, _uid(current_user), limit)


@router.post("/jobs", dependencies=CAREER_WRITE_DEPENDENCIES, status_code=201)
def create_job(payload: JobCreate, current_user: dict = Depends(require_current_user)):
    return _call(career_service.create_job, _uid(current_user), _values(payload))


@router.get("/jobs/{job_id}")
def job(job_id: int, current_user: dict = Depends(require_current_user)):
    return _call(career_service.get_job, _uid(current_user), job_id)


@router.patch("/jobs/{job_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def update_job(job_id: int, payload: JobUpdate, current_user: dict = Depends(require_current_user)):
    return _call(career_service.update_job, _uid(current_user), job_id, _changes(payload))


@router.delete("/jobs/{job_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def delete_job(job_id: int, current_user: dict = Depends(require_current_user)):
    _call(career_service.delete_job, _uid(current_user), job_id)
    return {"ok": True}


# Applications
@router.get("/applications")
def applications(limit: int = Query(100, ge=1, le=500), current_user: dict = Depends(require_current_user)):
    return _call(career_service.list_applications, _uid(current_user), limit)


@router.post("/applications", dependencies=CAREER_WRITE_DEPENDENCIES, status_code=201)
def create_application(payload: ApplicationCreate, current_user: dict = Depends(require_current_user)):
    return _call(career_service.create_application, _uid(current_user), _values(payload))


@router.get("/applications/{application_id}")
def application(application_id: int, current_user: dict = Depends(require_current_user)):
    return _call(career_service.get_application, _uid(current_user), application_id)


@router.patch("/applications/{application_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def update_application(application_id: int, payload: ApplicationUpdate, current_user: dict = Depends(require_current_user)):
    return _call(career_service.update_application, _uid(current_user), application_id, _changes(payload))


@router.delete("/applications/{application_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def delete_application(application_id: int, current_user: dict = Depends(require_current_user)):
    _call(career_service.delete_application, _uid(current_user), application_id)
    return {"ok": True}


# Interviews and questions
@router.get("/interviews")
def interviews(limit: int = Query(100, ge=1, le=500), current_user: dict = Depends(require_current_user)):
    return _call(career_service.list_interviews, _uid(current_user), limit)


@router.post("/interviews", dependencies=CAREER_WRITE_DEPENDENCIES, status_code=201)
def create_interview(payload: InterviewCreate, current_user: dict = Depends(require_current_user)):
    return _call(career_service.create_interview, _uid(current_user), _values(payload))


@router.get("/interviews/{interview_id}")
def interview(interview_id: int, current_user: dict = Depends(require_current_user)):
    return _call(career_service.get_interview, _uid(current_user), interview_id)


@router.patch("/interviews/{interview_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def update_interview(interview_id: int, payload: InterviewUpdate, current_user: dict = Depends(require_current_user)):
    return _call(career_service.update_interview, _uid(current_user), interview_id, _changes(payload))


@router.delete("/interviews/{interview_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def delete_interview(interview_id: int, current_user: dict = Depends(require_current_user)):
    _call(career_service.delete_interview, _uid(current_user), interview_id)
    return {"ok": True}


@router.post("/interviews/{interview_id}/questions", dependencies=CAREER_WRITE_DEPENDENCIES, status_code=201)
def add_question(interview_id: int, payload: QuestionCreate, current_user: dict = Depends(require_current_user)):
    return _call(career_service.add_interview_question, _uid(current_user), interview_id, _values(payload))


@router.patch("/interviews/{interview_id}/questions/{question_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def update_question(
    interview_id: int,
    question_id: int,
    payload: QuestionUpdate,
    current_user: dict = Depends(require_current_user),
):
    return _call(
        career_service.update_interview_question,
        _uid(current_user),
        interview_id,
        question_id,
        _changes(payload),
    )


@router.delete("/interviews/{interview_id}/questions/{question_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def delete_question(interview_id: int, question_id: int, current_user: dict = Depends(require_current_user)):
    _call(career_service.delete_interview_question, _uid(current_user), interview_id, question_id)
    return {"ok": True}


# Reports
@router.get("/reports")
def reports(
    limit: int = Query(100, ge=1, le=500),
    kind: Optional[str] = Query(None, max_length=32),
    current_user: dict = Depends(require_current_user),
):
    return _call(career_service.list_reports, _uid(current_user), limit, kind)


@router.post("/reports", dependencies=CAREER_WRITE_DEPENDENCIES, status_code=201)
def create_report(payload: ReportCreate, current_user: dict = Depends(require_current_user)):
    return _call(career_service.create_report, _uid(current_user), _values(payload))


@router.get("/reports/{report_id}")
def report(report_id: int, current_user: dict = Depends(require_current_user)):
    return _call(career_service.get_report, _uid(current_user), report_id)


@router.patch("/reports/{report_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def update_report(report_id: int, payload: ReportUpdate, current_user: dict = Depends(require_current_user)):
    return _call(career_service.update_report, _uid(current_user), report_id, _changes(payload))


@router.delete("/reports/{report_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def delete_report(report_id: int, current_user: dict = Depends(require_current_user)):
    _call(career_service.delete_report, _uid(current_user), report_id)
    return {"ok": True}


# Skills
@router.get("/skills")
def skills(limit: int = Query(100, ge=1, le=500), current_user: dict = Depends(require_current_user)):
    return _call(career_service.list_skills, _uid(current_user), limit)


@router.post("/skills", dependencies=CAREER_WRITE_DEPENDENCIES, status_code=201)
def create_skill(payload: SkillCreate, current_user: dict = Depends(require_current_user)):
    return _call(career_service.create_skill, _uid(current_user), _values(payload))


@router.get("/skills/{skill_id}")
def skill(skill_id: int, current_user: dict = Depends(require_current_user)):
    return _call(career_service.get_skill, _uid(current_user), skill_id)


@router.patch("/skills/{skill_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def update_skill(skill_id: int, payload: SkillUpdate, current_user: dict = Depends(require_current_user)):
    return _call(career_service.update_skill, _uid(current_user), skill_id, _changes(payload))


@router.delete("/skills/{skill_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def delete_skill(skill_id: int, current_user: dict = Depends(require_current_user)):
    _call(career_service.delete_skill, _uid(current_user), skill_id)
    return {"ok": True}


# AI suggestions
@router.patch("/suggestions/{suggestion_id}", dependencies=CAREER_WRITE_DEPENDENCIES)
def revise_suggestion(
    suggestion_id: int,
    payload: CareerSuggestionRevision,
    current_user: dict = Depends(require_current_user),
):
    return _call(
        suggestion_service.revise_suggestion,
        _uid(current_user),
        suggestion_id,
        payload.revision,
        payload.payload,
    )


@router.post("/suggestions/{suggestion_id}/accept", dependencies=CAREER_WRITE_DEPENDENCIES)
def accept_suggestion(
    suggestion_id: int,
    payload: CareerSuggestionDecision,
    current_user: dict = Depends(require_current_user),
):
    return _call(
        suggestion_service.accept_suggestion,
        _uid(current_user),
        suggestion_id,
        payload.revision,
    )


@router.post("/suggestions/{suggestion_id}/dismiss", dependencies=CAREER_WRITE_DEPENDENCIES)
def dismiss_suggestion(
    suggestion_id: int,
    payload: CareerSuggestionDecision,
    current_user: dict = Depends(require_current_user),
):
    return _call(
        suggestion_service.dismiss_suggestion,
        _uid(current_user),
        suggestion_id,
        payload.revision,
    )


@router.post("/suggestions/{suggestion_id}/restore", dependencies=CAREER_WRITE_DEPENDENCIES)
def restore_suggestion(
    suggestion_id: int,
    payload: CareerSuggestionDecision,
    current_user: dict = Depends(require_current_user),
):
    return _call(
        suggestion_service.restore_suggestion,
        _uid(current_user),
        suggestion_id,
        payload.revision,
    )


@router.get("/export", dependencies=[Depends(require_career_data_guard)])
def export_data(current_user: dict = Depends(require_current_user)):
    return _call(career_service.export_career_data, _uid(current_user))


@router.delete("/data", dependencies=CAREER_WRITE_DEPENDENCIES)
def delete_data(payload: DeleteCareerDataRequest, current_user: dict = Depends(require_current_user)):
    if payload.confirmation != "DELETE":
        raise HTTPException(status_code=400, detail="confirmation must equal DELETE")
    user_id = _uid(current_user)
    # Keep the heavy RAG stack out of ordinary career CRUD imports.  It is only
    # needed for this explicit privacy operation.
    from backend.services.rag import delete_user_collection

    vector_collection_deleted = delete_user_collection(user_id)
    deleted = _call(career_service.delete_career_data, user_id)
    return {
        "ok": True,
        "deleted": deleted,
        "vector_collection_deleted": vector_collection_deleted,
    }
