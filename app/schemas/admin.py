from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class AdminUserResponse(BaseModel):
    id: int
    email: EmailStr
    credits: int
    is_admin: bool
    email_verified: bool

    model_config = {"from_attributes": True}


class AdminUserDetailResponse(AdminUserResponse):
    created_at: datetime


class AdminCreditSetRequest(BaseModel):
    credits: int = Field(..., ge=0)
    reason: str | None = Field(default=None, max_length=500)


class AdminCreditAdjustRequest(BaseModel):
    delta: int
    reason: str | None = Field(default=None, max_length=500)


class AdminCreditAdjustmentResponse(BaseModel):
    id: int
    target_user_id: int
    target_email: EmailStr
    admin_user_id: int
    admin_email: EmailStr
    old_credits: int
    new_credits: int
    delta: int
    reason: str | None
    created_at: datetime


class AdminCreditAdjustmentListResponse(BaseModel):
    adjustments: list[AdminCreditAdjustmentResponse]
