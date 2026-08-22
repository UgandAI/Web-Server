from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.farm_profile import FarmProfile
from app.models.user import User
from pydantic import BaseModel
from openai import OpenAI
from app.core.config import settings

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

client = OpenAI(api_key=settings.OPENAI_API_KEY)

class RecommendationResponse(BaseModel):
    recommendation: str

@router.get("/initial", response_model=RecommendationResponse)
def get_initial_recommendation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.execute(
        select(FarmProfile).where(FarmProfile.user_id == current_user.id)
    ).scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=400, detail="Farm profile not found. Please complete your profile first.")

    prompt = f"""
    The user is a farmer in Uganda. 
    Farm Size: {profile.farm_size} acres.
    District: {profile.district}.
    Crops: {profile.primary_crops}.
    
    Please provide one concise, encouraging initial piece of farming advice or recommendation for them (max 3 sentences). 
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert agronomist providing tailored advice to Ugandan farmers."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7,
        )
        recommendation = response.choices[0].message.content.strip()
        return {"recommendation": recommendation}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate recommendation")
