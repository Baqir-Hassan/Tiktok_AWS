from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.auth_rate_limit_service import AuthRateLimitService
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=MessageResponse)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> MessageResponse:
    AuthRateLimitService().enforce_register(_get_client_ip(request), payload.email)
    AuthService(db).register(payload.email, payload.password)
    return MessageResponse(message="Account created. Please verify your email before signing in.")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    AuthRateLimitService().enforce_login(_get_client_ip(request), payload.email)
    token = AuthService(db).login(payload.email, payload.password)
    return TokenResponse(access_token=token)


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> MessageResponse:
    AuthService(db).verify_email(payload.token)
    return MessageResponse(message="Email verified successfully. You can now sign in.")


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(payload: ResendVerificationRequest, request: Request, db: Session = Depends(get_db)) -> MessageResponse:
    AuthRateLimitService().enforce_email_action("resend-verification", _get_client_ip(request), payload.email)
    AuthService(db).resend_verification(payload.email)
    return MessageResponse(message="If an unverified account exists for this email, we sent a verification link.")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)) -> MessageResponse:
    AuthRateLimitService().enforce_email_action("forgot-password", _get_client_ip(request), payload.email)
    AuthService(db).forgot_password(payload.email)
    return MessageResponse(message="If an account exists for this email, you will receive a password reset link.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    AuthService(db).reset_password(payload.token, payload.new_password)
    return MessageResponse(message="Password reset successfully. You can now sign in.")


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        first_hop = forwarded_for.split(",")[0].strip()
        if first_hop:
            return first_hop
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"
