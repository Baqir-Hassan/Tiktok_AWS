from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models.credit_adjustment import CreditAdjustment
from app.models.user import User
from app.schemas.admin import (
    AdminCreditAdjustmentListResponse,
    AdminCreditAdjustmentResponse,
    AdminCreditAdjustRequest,
    AdminCreditSetRequest,
    AdminUserDetailResponse,
    AdminUserResponse,
)
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users/search", response_model=List[AdminUserResponse])
def search_users_by_email_prefix(
    email_prefix: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> List[AdminUserResponse]:
    """Search users by email prefix"""
    normalized_prefix = email_prefix.strip().lower()
    if len(normalized_prefix) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email_prefix must be at least 2 characters.",
        )

    users = db.scalars(
        select(User)
        .where(User.email.ilike(f"{normalized_prefix}%"))
        .order_by(User.email.asc())
        .limit(10)
    ).all()
    return [
        AdminUserResponse(
            id=user.id,
            email=user.email,
            credits=user.credits,
            is_admin=user.is_admin,
            email_verified=user.email_verified,
        )
        for user in users
    ]


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
def get_user_details(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> AdminUserDetailResponse:
    user = AdminService(db).get_user_or_404(user_id)
    return AdminUserDetailResponse.model_validate(user)


@router.put("/users/{user_id}/credits", response_model=AdminCreditAdjustmentResponse)
def set_user_credits(
    user_id: int,
    payload: AdminCreditSetRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> AdminCreditAdjustmentResponse:
    adjustment = AdminService(db).set_user_credits(current_admin, user_id, payload.credits, payload.reason)
    return _serialize_credit_adjustment(adjustment, current_admin, AdminService(db).get_user_or_404(user_id))


@router.post("/users/{user_id}/credits/adjust", response_model=AdminCreditAdjustmentResponse)
def adjust_user_credits(
    user_id: int,
    payload: AdminCreditAdjustRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> AdminCreditAdjustmentResponse:
    service = AdminService(db)
    adjustment = service.adjust_user_credits(current_admin, user_id, payload.delta, payload.reason)
    return _serialize_credit_adjustment(adjustment, current_admin, service.get_user_or_404(user_id))


@router.get("/users/{user_id}/credits/history", response_model=AdminCreditAdjustmentListResponse)
def get_user_credit_history(
    user_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> AdminCreditAdjustmentListResponse:
    service = AdminService(db)
    target_user = service.get_user_or_404(user_id)
    adjustments = service.list_recent_credit_adjustments(user_id, limit)
    admin_users = {
        admin_user.id: admin_user
        for admin_user in db.scalars(
            select(User).where(User.id.in_({adjustment.admin_user_id for adjustment in adjustments}))
        ).all()
    } if adjustments else {}
    return AdminCreditAdjustmentListResponse(
        adjustments=[
            _serialize_credit_adjustment(
                adjustment,
                admin_users.get(adjustment.admin_user_id, target_user),
                target_user,
            )
            for adjustment in adjustments
        ]
    )


def _serialize_credit_adjustment(
    adjustment: CreditAdjustment,
    admin_user: User,
    target_user: User,
) -> AdminCreditAdjustmentResponse:
    return AdminCreditAdjustmentResponse(
        id=adjustment.id,
        target_user_id=target_user.id,
        target_email=target_user.email,
        admin_user_id=admin_user.id,
        admin_email=admin_user.email,
        old_credits=adjustment.old_credits,
        new_credits=adjustment.new_credits,
        delta=adjustment.delta,
        reason=adjustment.reason,
        created_at=adjustment.created_at,
    )
