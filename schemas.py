import pydantic as _pydantic


class _UserBase(_pydantic.BaseModel):
    username: str


class UserCreate(_UserBase):
    password: str


class User(_UserBase):
    id: int

    model_config = _pydantic.ConfigDict(from_attributes=True)
