from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.credit_adjustment import CreditAdjustment
from app.models.user import User


class AdminService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_or_404(self, user_id: int) -> User:
        user = self.db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return user

    def set_user_credits(self, admin_user: User, target_user_id: int, credits: int, reason: str | None = None) -> CreditAdjustment:
        target_user = self.get_user_or_404(target_user_id)
        old_credits = target_user.credits
        new_credits = credits
        delta = new_credits - old_credits
        return self._apply_credit_change(admin_user, target_user, old_credits, new_credits, delta, reason)

    def adjust_user_credits(self, admin_user: User, target_user_id: int, delta: int, reason: str | None = None) -> CreditAdjustment:
        target_user = self.get_user_or_404(target_user_id)
        old_credits = target_user.credits
        new_credits = old_credits + delta
        if new_credits < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credit adjustment would result in a negative balance.",
            )
        return self._apply_credit_change(admin_user, target_user, old_credits, new_credits, delta, reason)

    def list_recent_credit_adjustments(self, target_user_id: int, limit: int = 20) -> list[CreditAdjustment]:
        self.get_user_or_404(target_user_id)
        return list(
            self.db.scalars(
                select(CreditAdjustment)
                .where(CreditAdjustment.target_user_id == target_user_id)
                .order_by(CreditAdjustment.created_at.desc(), CreditAdjustment.id.desc())
                .limit(limit)
            )
        )

    def _apply_credit_change(
        self,
        admin_user: User,
        target_user: User,
        old_credits: int,
        new_credits: int,
        delta: int,
        reason: str | None,
    ) -> CreditAdjustment:
        if new_credits < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credits cannot be negative.")

        normalized_reason = reason.strip() if reason and reason.strip() else None
        target_user.credits = new_credits
        adjustment = CreditAdjustment(
            admin_user_id=admin_user.id,
            target_user_id=target_user.id,
            old_credits=old_credits,
            new_credits=new_credits,
            delta=delta,
            reason=normalized_reason,
        )
        self.db.add(target_user)
        self.db.add(adjustment)
        self.db.commit()
        self.db.refresh(adjustment)
        return adjustment
