from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings


settings = get_settings()
# Use pbkdf2_sha256 to avoid bcrypt backend compatibility issues on deploy
# targets while keeping password hashing strong and deterministic.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expires_at, "typ": "auth"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("typ") != "auth":
            raise ValueError("Invalid access token")
        return payload
    except JWTError as exc:
        raise ValueError("Invalid access token") from exc


def create_media_access_token(*, job_id: int, user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.media_access_token_expire_seconds)
    payload = {"sub": str(user_id), "job_id": job_id, "exp": expires_at, "typ": "media"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_media_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("typ") != "media":
            raise ValueError("Invalid media token")
        return payload
    except JWTError as exc:
        raise ValueError("Invalid media token") from exc
