import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.services.email_service import EmailDeliveryError, EmailService


settings = get_settings()


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()

    def register(self, email: str, password: str) -> User:
        existing_user = self.db.scalar(select(User).where(User.email == email))
        if existing_user:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        token, token_hash, token_expiry = self._build_token()
        now = self._utcnow_naive()
        user = User(
            email=email,
            password_hash=hash_password(password),
            credits=settings.initial_user_credits,
            email_verified=False,
            verification_token_hash=token_hash,
            verification_token_expires_at=token_expiry,
            verification_sent_at=now,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        self._send_verification_email(user.email, token)
        return user

    def login(self, email: str, password: str) -> str:
        user = self.db.scalar(select(User).where(User.email == email))
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        if not user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please verify your email before signing in.",
            )
        return create_access_token(str(user.id))

    def verify_email(self, token: str) -> None:
        user = self._get_user_by_token(token)
        if user.email_verified:
            return

        user.email_verified = True
        user.verification_token_hash = None
        user.verification_token_expires_at = None
        user.verification_sent_at = None
        self.db.add(user)
        self.db.commit()

    def resend_verification(self, email: str) -> None:
        user = self.db.scalar(select(User).where(User.email == email))
        if not user or user.email_verified:
            return

        now = self._utcnow_naive()
        self._enforce_resend_cooldown(user, now)
        token, token_hash, token_expiry = self._build_token()
        user.verification_token_hash = token_hash
        user.verification_token_expires_at = token_expiry
        user.verification_sent_at = now
        self.db.add(user)
        self.db.commit()
        self._send_verification_email(user.email, token)

    def forgot_password(self, email: str) -> None:
        user = self.db.scalar(select(User).where(User.email == email))
        if not user or not user.email_verified:
            return

        now = self._utcnow_naive()
        self._enforce_resend_cooldown(user, now)
        token, token_hash, token_expiry = self._build_token()
        user.verification_token_hash = token_hash
        user.verification_token_expires_at = token_expiry
        user.verification_sent_at = now
        self.db.add(user)
        self.db.commit()
        self._send_password_reset_email(user.email, token)

    def reset_password(self, token: str, new_password: str) -> None:
        user = self._get_user_by_token(token)
        user.password_hash = hash_password(new_password)
        user.verification_token_hash = None
        user.verification_token_expires_at = None
        user.verification_sent_at = None
        self.db.add(user)
        self.db.commit()

    def _get_user_by_token(self, token: str) -> User:
        token_hash = self._hash_token(token)
        user = self.db.scalar(select(User).where(User.verification_token_hash == token_hash))
        now = self._utcnow_naive()
        if not user or not user.verification_token_expires_at or user.verification_token_expires_at < now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
        return user

    def _enforce_resend_cooldown(self, user: User, now: datetime) -> None:
        if not user.verification_sent_at:
            return
        next_allowed = user.verification_sent_at + timedelta(seconds=settings.verification_resend_cooldown_seconds)
        if next_allowed > now:
            retry_seconds = int((next_allowed - now).total_seconds())
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {retry_seconds}s before requesting another email.",
            )

    def _build_token(self) -> tuple[str, str, datetime]:
        token = secrets.token_urlsafe(32)
        return token, self._hash_token(token), self._utcnow_naive() + timedelta(minutes=settings.verification_token_expire_minutes)

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _send_verification_email(self, email: str, token: str) -> None:
        verification_url = f"{settings.verify_email_page_url}?token={quote_plus(token)}"
        try:
            self.email_service.send_verification_email(email, verification_url)
        except EmailDeliveryError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to send verification email at the moment.",
            ) from exc

    def _send_password_reset_email(self, email: str, token: str) -> None:
        reset_url = f"{settings.reset_password_page_url}?token={quote_plus(token)}"
        try:
            self.email_service.send_password_reset_email(email, reset_url)
        except EmailDeliveryError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to send password reset email at the moment.",
            ) from exc

    def _utcnow_naive(self) -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)
