from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_token_hash: Mapped[str] = mapped_column(String(255), nullable=True)
    verification_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    credit_adjustments_made = relationship(
        "CreditAdjustment",
        foreign_keys="CreditAdjustment.admin_user_id",
        back_populates="admin_user",
    )
    credit_adjustments_received = relationship(
        "CreditAdjustment",
        foreign_keys="CreditAdjustment.target_user_id",
        back_populates="target_user",
    )
