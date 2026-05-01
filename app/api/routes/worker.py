from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_worker_key
from app.core.database import get_db
from app.schemas.worker import (
    WorkerClaimRequest,
    WorkerClaimResponse,
    WorkerCompleteRequest,
    WorkerFailRequest,
    WorkerHeartbeatRequest,
    WorkerJobResponse,
    WorkerUpdateRequest,
)
from app.services.worker_service import WorkerService


router = APIRouter(prefix="/jobs", tags=["worker"], dependencies=[Depends(require_worker_key)])


@router.get("/next", response_model=WorkerJobResponse)
def get_next_job(db: Session = Depends(get_db)) -> WorkerJobResponse | Response:
    job = WorkerService(db).get_next_job()
    if not job:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return WorkerJobResponse.model_validate(job)


@router.post("/{job_id}/claim", response_model=WorkerClaimResponse)
def claim_job(
    job_id: int,
    payload: WorkerClaimRequest,
    db: Session = Depends(get_db),
) -> WorkerClaimResponse:
    job = WorkerService(db).claim_job(job_id, payload.worker_id)
    return WorkerClaimResponse(
        id=job.id,
        status=job.status,
        claimed=True,
        progress=job.progress,
        claimed_by=job.claimed_by,
        claimed_at=job.claimed_at,
    )


@router.post("/{job_id}/update", response_model=WorkerJobResponse)
def update_job(
    job_id: int,
    payload: WorkerUpdateRequest,
    db: Session = Depends(get_db),
) -> WorkerJobResponse:
    job = WorkerService(db).update_job(
        job_id=job_id,
        next_stage=payload.status,
        worker_id=payload.worker_id,
        message=payload.message,
        progress=payload.progress,
        source_title=payload.source_title,
        source_post_id=payload.source_post_id,
        source_permalink=payload.source_permalink,
        script=payload.script,
    )
    return WorkerJobResponse.model_validate(job)


@router.post("/{job_id}/complete", response_model=WorkerJobResponse)
def complete_job(
    job_id: int,
    payload: WorkerCompleteRequest,
    db: Session = Depends(get_db),
) -> WorkerJobResponse:
    job = WorkerService(db).complete_job(job_id, payload.worker_id, payload.video_url, payload.message)
    return WorkerJobResponse.model_validate(job)


@router.post("/{job_id}/fail", response_model=WorkerJobResponse)
def fail_job(
    job_id: int,
    payload: WorkerFailRequest,
    db: Session = Depends(get_db),
) -> WorkerJobResponse:
    job = WorkerService(db).fail_job(job_id, payload.worker_id, payload.error_message, payload.message)
    return WorkerJobResponse.model_validate(job)


@router.post("/{job_id}/heartbeat", response_model=WorkerJobResponse)
def heartbeat_job(
    job_id: int,
    payload: WorkerHeartbeatRequest,
    db: Session = Depends(get_db),
) -> WorkerJobResponse:
    job = WorkerService(db).heartbeat_job(job_id, payload.worker_id)
    return WorkerJobResponse.model_validate(job)
