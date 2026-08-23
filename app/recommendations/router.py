import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.farm_profile import FarmProfile
from app.models.user import User
from app.recommendations.service import RecommendationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendationResponse(BaseModel):
    recommendation: str


def get_recommendation_service() -> RecommendationService:
    return RecommendationService()


@router.get("/initial", response_model=RecommendationResponse)
def get_initial_recommendation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: RecommendationService = Depends(get_recommendation_service),
):
    profile = db.execute(
        select(FarmProfile).where(FarmProfile.user_id == current_user.id)
    ).scalars().first()
    if not profile:
        raise HTTPException(400, "Farm profile not found. Please complete your profile first.")
    try:
        return {"recommendation": service.generate(
            farm_size=profile.farm_size, district=profile.district, crops=profile.crops
        )}
    except Exception as exc:
        logger.error("Initial recommendation generation failed: %s", type(exc).__name__)
        raise HTTPException(502, "Recommendation service unavailable")
