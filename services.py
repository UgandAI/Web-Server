import sqlalchemy.orm as _orm

import schemas as _schemas
from app.db.session import get_db
from app.models import User
from passlib.hash import bcrypt


def get_user(db: _orm.Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


def verify_password(db: _orm.Session, username: str, password: str):
    user_obj = db.query(User).filter(User.username == username).first()
    return bcrypt.verify(password, user_obj.hashed_password)


def get_user_by_username(db: _orm.Session, username: str):
    return db.query(User).filter(User.username == username).first()


def get_users(db: _orm.Session, skip: int = 0, limit: int = 100):
    return db.query(User).offset(skip).limit(limit).all()


def create_user(db: _orm.Session, user: _schemas.UserCreate):
    db_user = User(
        username=user.username,
        hashed_password=bcrypt.hash(user.password),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
