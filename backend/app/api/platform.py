"""Authenticated deployment status for Phase 8 foundations; no unfinished feature CRUD is exposed."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import current_user
from app.core.migrate import CURRENT_SCHEMA_VERSION
from app.models import User
from app.services.platform.features import KNOWN_FEATURES, enabled_features

router = APIRouter(prefix="/platform", tags=["platform"])


class PlatformStatus(BaseModel):
    schema_version: int
    features: dict[str, bool]
    foundations_ready: bool = True


@router.get("/status", response_model=PlatformStatus)
def platform_status(_user: User = Depends(current_user)) -> PlatformStatus:
    active = enabled_features()
    return PlatformStatus(
        schema_version=CURRENT_SCHEMA_VERSION,
        features={name: name in active for name in sorted(KNOWN_FEATURES)},
    )
