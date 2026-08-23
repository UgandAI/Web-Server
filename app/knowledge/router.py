from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models import Document, User

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    source_identifier: str
    source_url: str | None
    source_type: str
    published_at: datetime | None
    created_at: datetime


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(
    _user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return db.query(Document).order_by(Document.created_at.desc(), Document.id.desc()).limit(100).all()
