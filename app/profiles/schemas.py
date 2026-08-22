from typing import Optional
from pydantic import BaseModel, ConfigDict

class FarmProfileBase(BaseModel):
    farm_name: Optional[str] = None
    district: Optional[str] = None
    crops: Optional[str] = None
    farm_size: Optional[float] = None

class FarmProfileCreate(FarmProfileBase):
    pass

class FarmProfileUpdate(FarmProfileBase):
    pass

class FarmProfile(FarmProfileBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)

class UserProfileBase(BaseModel):
    display_name: Optional[str] = None
    district: Optional[str] = None
    preferred_language: Optional[str] = None

class UserProfileCreate(UserProfileBase):
    pass

class UserProfileUpdate(UserProfileBase):
    pass

class UserProfile(UserProfileBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)
