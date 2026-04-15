from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User


settings = get_settings()


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register(self, email: str, password: str) -> User:
        existing_user = self.db.scalar(select(User).where(User.email == email))
        if existing_user:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        user = User(
            email=email,
            password_hash=hash_password(password),
            credits=settings.initial_user_credits,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def login(self, email: str, password: str) -> str:
        user = self.db.scalar(select(User).where(User.email == email))
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        return create_access_token(str(user.id))
