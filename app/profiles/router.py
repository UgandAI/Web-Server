from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.farm_profile import FarmProfile as DBFarmProfile
from app.models.user_profile import UserProfile as DBUserProfile
from app.profiles import schemas

router = APIRouter(prefix="/profiles", tags=["Profiles"])

@router.get("/farm", response_model=List[schemas.FarmProfile])
def get_farm_profiles(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(DBFarmProfile).filter(DBFarmProfile.user_id == user.id).all()

@router.post("/farm", response_model=schemas.FarmProfile, status_code=status.HTTP_201_CREATED)
def create_farm_profile(
    profile_in: schemas.FarmProfileCreate, 
    user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    db_profile = DBFarmProfile(**profile_in.model_dump(), user_id=user.id)
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile

@router.put("/farm/{profile_id}", response_model=schemas.FarmProfile)
def update_farm_profile(
    profile_id: int,
    profile_in: schemas.FarmProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_profile = db.query(DBFarmProfile).filter(
        DBFarmProfile.id == profile_id, DBFarmProfile.user_id == user.id
    ).first()
    if not db_profile:
        raise HTTPException(status_code=404, detail="Farm profile not found")
    
    update_data = profile_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_profile, key, value)
        
    db.commit()
    db.refresh(db_profile)
    return db_profile

@router.get("/user", response_model=schemas.UserProfile)
def get_user_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == user.id).first()
    if not db_profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    return db_profile

@router.post("/user", response_model=schemas.UserProfile, status_code=status.HTTP_201_CREATED)
def create_user_profile(
    profile_in: schemas.UserProfileCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if db.query(DBUserProfile).filter(DBUserProfile.user_id == user.id).first():
        raise HTTPException(status_code=400, detail="User profile already exists")
        
    db_profile = DBUserProfile(**profile_in.model_dump(), user_id=user.id)
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile

@router.put("/user", response_model=schemas.UserProfile)
def update_user_profile(
    profile_in: schemas.UserProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == user.id).first()
    if not db_profile:
        raise HTTPException(status_code=404, detail="User profile not found")
        
    update_data = profile_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_profile, key, value)
        
    db.commit()
    db.refresh(db_profile)
    return db_profile
