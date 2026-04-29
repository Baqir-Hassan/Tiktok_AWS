from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.job import JobCreateRequest, JobDetailResponse, JobListResponse, JobResponse
from app.services.job_service import JobService


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(
    payload: JobCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    job = JobService(db).create_job(
        current_user,
        payload.subreddit,
        payload.tts_provider,
        payload.custom_title,
        payload.custom_story,
    )
    return JobResponse.model_validate(job)


@router.get("", response_model=JobListResponse)
def list_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobListResponse:
    jobs = JobService(db).list_jobs(current_user)
    return JobListResponse(jobs=[JobResponse.model_validate(job) for job in jobs])


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobDetailResponse:
    job = JobService(db).get_job_for_user(current_user, job_id)
    return JobDetailResponse.model_validate(job)
