from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlmodel import or_, select

from app.database import SessionDep
from app.models import Product
from app.schemas import ProductCreate, ProductUpdate, SaleUpdate

router = APIRouter(prefix="/products", tags=["products"])


def _round_prices(price: float, original_price: float | None) -> tuple[float, float | None]:
    # 2dp invariant agreed for this app: round on every write, format on every read
    return round(price, 2), round(original_price, 2) if original_price is not None else None


@router.post("", status_code=201)
def create_product(data: ProductCreate, session: SessionDep) -> Product:
    data.price, data.original_price = _round_prices(data.price, data.original_price)
    product = Product(**data.model_dump())
    session.add(product)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="product_uid or full_sku already exists")
    session.refresh(product)
    return product


@router.get("")
def list_products(
    session: SessionDep,
    set_name: Annotated[str | None, Query()] = None,
    language: Annotated[str | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> list[Product]:
    query = select(Product)
    if set_name is not None:
        query = query.where(Product.set_name == set_name)
    if language is not None:
        query = query.where(Product.language == language)
    if is_active is not None:
        query = query.where(Product.is_active == is_active)
    return list(session.exec(query).all())


@router.get("/search")
def search_products(
    session: SessionDep,
    q: Annotated[str, Query(min_length=1)],
) -> list[Product]:
    # one box, four targets: partial name (case-insensitive), or exact identifiers.
    # declared before /{product_id} so "search" isn't swallowed by the path param.
    query = select(Product).where(
        or_(
            Product.name.contains(q, autoescape=True),
            Product.sku == q,
            Product.product_uid == q,
            Product.full_sku == q,
        )
    )
    return list(session.exec(query).all())


@router.get("/{product_id}")
def get_product(product_id: int, session: SessionDep) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}")
def update_product(product_id: int, data: ProductUpdate, session: SessionDep) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    updates = data.model_dump(exclude_unset=True)
    if "price" in updates or "original_price" in updates:
        price, original_price = _round_prices(
            updates.get("price", product.price),
            updates.get("original_price", product.original_price),
        )
        updates["price"], updates["original_price"] = price, original_price
    for key, value in updates.items():
        setattr(product, key, value)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="product_uid or full_sku already exists")
    session.refresh(product)
    return product


@router.patch("/{product_id}/sale")
def set_sale(product_id: int, data: SaleUpdate, session: SessionDep) -> Product:
    """Toggle on_sale and/or set the discount percentage in one call."""
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Provide on_sale and/or discount")
    for key, value in updates.items():
        setattr(product, key, value)
    session.commit()
    session.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, session: SessionDep) -> None:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    session.delete(product)
    session.commit()
