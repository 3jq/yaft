from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.api.auth import require_owner
from finance_app.api.routes.transactions import _session
from finance_app.api.schemas import CategoryIn, CategoryOut
from finance_app.db.models import Category

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
async def list_categories(
    include_archived: bool = False,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    q = select(Category)
    if not include_archived:
        q = q.where(Category.archived == 0)
    rows = (await session.execute(q.order_by(Category.id))).scalars().all()
    return [CategoryOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("", response_model=CategoryOut, status_code=201)
async def create_category(
    body: CategoryIn,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    c = Category(name=body.name, parent_id=body.parent_id, kind=body.kind, emoji=body.emoji)
    session.add(c)
    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(400, "duplicate (name, parent)") from e
    await session.refresh(c)
    return CategoryOut.model_validate(c, from_attributes=True)


@router.patch("/{cid}", response_model=CategoryOut)
async def patch_category(
    cid: int,
    body: CategoryIn,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    c = await session.get(Category, cid)
    if not c:
        raise HTTPException(404, "not found")
    c.name = body.name
    c.parent_id = body.parent_id
    c.kind = body.kind
    c.emoji = body.emoji
    await session.commit()
    await session.refresh(c)
    return CategoryOut.model_validate(c, from_attributes=True)


@router.post("/{cid}/archive", status_code=204)
async def archive_category(
    cid: int,
    session: AsyncSession = Depends(_session),  # noqa: B008
    _u=Depends(require_owner),  # noqa: B008
):
    c = await session.get(Category, cid)
    if not c:
        raise HTTPException(404, "not found")
    c.archived = 1
    await session.commit()
    return Response(status_code=204)
