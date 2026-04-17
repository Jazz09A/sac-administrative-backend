"""
API Contributors: POST/GET con get_or_create.
Última mod: 2026-04-17 09:03 | Changes: Basic CRUD.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.crud.contributors import (
    get_contributors, get_contributor, create_contributor, update_contributor
)
from src.models.contributor import (
    ContributorPublic, ContributorCreate, ContributorUpdate
)

router = APIRouter()

@router.post("/", response_model=ContributorPublic, status_code=status.HTTP_201_CREATED)
async def create_new_contributor(
    contributor_in: ContributorCreate,
    db: AsyncSession = Depends(get_db)
) -> ContributorPublic:
    """Crea o retorna existente por RIF."""
    contributor = await create_contributor(db, contributor_in)
    return contributor

@router.get("/", response_model=List[ContributorPublic])
async def read_contributors(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
) -> List[ContributorPublic]:
    contributors = await get_contributors(db, skip=skip, limit=limit)
    return contributors

@router.get("/{contributor_id}", response_model=ContributorPublic)
async def read_contributor(
    contributor_id: int, db: AsyncSession = Depends(get_db)
) -> ContributorPublic:
    contributor = await get_contributor(db, contributor_id)
    if not contributor:
        raise HTTPException(status_code=404, detail="Contribuyente no encontrado")
    return contributor

@router.put("/{contributor_id}", response_model=ContributorPublic)
async def update_existing_contributor(
    contributor_id: int,
    contributor_in: ContributorUpdate,
    db: AsyncSession = Depends(get_db)
) -> ContributorPublic:
    contributor = await update_contributor(db, contributor_id, contributor_in)
    if not contributor:
        raise HTTPException(status_code=404, detail="Contribuyente no encontrado")
    return contributor