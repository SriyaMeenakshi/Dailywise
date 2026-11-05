import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Category, User
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])

_DUPLICATE = HTTPException(status.HTTP_409_CONFLICT, "You already have a category with that name")


def _get_owned(db: Session, user: User, category_id: uuid.UUID) -> Category:
    category = db.scalar(
        select(Category).where(Category.id == category_id, Category.user_id == user.id)
    )
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return category


@router.get("", response_model=list[CategoryRead])
def list_categories(
    user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]
):
    return list(
        db.scalars(
            select(Category)
            .where(Category.user_id == user.id)
            .order_by(Category.sort_order, Category.name)
        )
    )


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    next_order = (
        db.scalar(select(func.max(Category.sort_order)).where(Category.user_id == user.id)) or 0
    ) + 1
    category = Category(
        user_id=user.id, name=body.name.strip(), color=body.color, sort_order=next_order
    )
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _DUPLICATE from None
    return category


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    category = _get_owned(db, user, category_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(422, f"{field} cannot be null")
        setattr(category, field, value.strip() if field == "name" else value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _DUPLICATE from None
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Tasks in the category are kept and become uncategorised (FK is ON DELETE SET NULL)."""
    db.delete(_get_owned(db, user, category_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

