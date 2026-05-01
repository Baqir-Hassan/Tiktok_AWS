from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.job import JobAccessResponse, JobCreateRequest, JobDetailResponse, JobListResponse, JobResponse
from app.services.job_service import JobService
from app.services.media_access_service import MediaAccessService


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
    return _serialize_job(job)


@router.get("", response_model=JobListResponse)
def list_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobListResponse:
    jobs = JobService(db).list_jobs(current_user)
    return JobListResponse(jobs=[_serialize_job(job) for job in jobs])


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobDetailResponse:
    job = JobService(db).get_job_for_user(current_user, job_id)
    return _serialize_job_detail(job)


@router.get("/{job_id}/access", response_model=JobAccessResponse)
def get_job_access(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobAccessResponse:
    job = JobService(db).get_job_for_user(current_user, job_id)
    descriptor = MediaAccessService().create_user_access_descriptor(job, current_user)
    if descriptor.kind == "local":
        base_url = str(request.url_for("stream_job_media", job_id=job_id))
        return JobAccessResponse(url=f"{base_url}?token={descriptor.value}", expires_in_seconds=descriptor.expires_in_seconds)
    return JobAccessResponse(url=descriptor.value, expires_in_seconds=descriptor.expires_in_seconds)


@router.get("/{job_id}/media", name="stream_job_media")
def stream_job_media(
    job_id: int,
    token: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> FileResponse:
    job = JobService(db)._get_job(job_id)
    media_path = MediaAccessService().resolve_local_media_path(job, token)
    return FileResponse(
        path=media_path,
        media_type="video/mp4",
        filename=media_path.name,
        headers={"Cache-Control": "private, max-age=60"},
    )


def _serialize_job(job) -> JobResponse:
    return JobResponse.model_validate(job).model_copy(update={"video_url": None, "uploaded_video_url": None})


def _serialize_job_detail(job) -> JobDetailResponse:
    return JobDetailResponse.model_validate(job).model_copy(update={"video_url": None, "uploaded_video_url": None})
