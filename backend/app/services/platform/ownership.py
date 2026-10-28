"""Uniform object ownership checks that do not disclose cross-account resources."""
from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import Base

Owned = TypeVar("Owned", bound=Base)


def owned_or_404(db: Session, model: type[Owned], row_id: str, user_id: str, label: str = "Item") -> Owned:
    row = db.get(model, row_id)
    if row is None or getattr(row, "user_id", None) != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} not found")
    return row
