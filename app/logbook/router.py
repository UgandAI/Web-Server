from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user
from app.db.session import get_db
from app.logbook.schemas import LogbookEntryCreate, LogbookEntryResponse, LogbookEntryUpdate
from app.models.logbook import LogbookEntry
from app.models.user import User

router = APIRouter(prefix="/logbook", tags=["logbook"])


@router.post("/", response_model=LogbookEntryResponse)
async def create_logbook_entry(
    entry_in: LogbookEntryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = LogbookEntry(
        user_id=current_user.id,
        activity_type=entry_in.activity_type,
        date=entry_in.date,
        crop=entry_in.crop,
        field=entry_in.field,
        note=entry_in.note,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.get("/", response_model=List[LogbookEntryResponse])
async def get_logbook_entries(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(LogbookEntry).where(LogbookEntry.user_id == current_user.id))
    return result.scalars().all()


@router.put("/{entry_id}", response_model=LogbookEntryResponse)
async def update_logbook_entry(
    entry_id: int,
    entry_in: LogbookEntryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LogbookEntry).where(
            LogbookEntry.id == entry_id, LogbookEntry.user_id == current_user.id
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Logbook entry not found")

    update_data = entry_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(entry, field, value)

    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/{entry_id}")
async def delete_logbook_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LogbookEntry).where(
            LogbookEntry.id == entry_id, LogbookEntry.user_id == current_user.id
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Logbook entry not found")

    await db.delete(entry)
    await db.commit()
    return {"message": "Logbook entry deleted successfully"}
