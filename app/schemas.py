"""Request schemas. Table models are never accepted directly from clients —
these validate input first (direct table-model construction skips Pydantic
validation, so the schema is the trust boundary)."""

from sqlmodel import Field, SQLModel


class ProductCreate(SQLModel):
    product_uid: str = Field(min_length=1)
    full_sku: str = Field(min_length=1)
    sku: str = Field(min_length=1)
    variant: str = ""
    name: str = Field(min_length=1)
    language: str = "EN"
    rarity: str = ""
    set_name: str = Field(min_length=1)
    currency: str = "SGD"
    price: float = Field(ge=0)
    original_price: float | None = Field(default=None, ge=0)
    on_sale: bool = False
    discount: float = Field(default=0, ge=0, le=100)
    is_active: bool = True
    remarks: str = ""
    quantity: int = Field(default=1, ge=0)


class ProductUpdate(SQLModel):
    """All fields optional; only provided fields are applied (PATCH)."""

    product_uid: str | None = Field(default=None, min_length=1)
    full_sku: str | None = Field(default=None, min_length=1)
    sku: str | None = Field(default=None, min_length=1)
    variant: str | None = None
    name: str | None = Field(default=None, min_length=1)
    language: str | None = None
    rarity: str | None = None
    set_name: str | None = Field(default=None, min_length=1)
    currency: str | None = None
    price: float | None = Field(default=None, ge=0)
    original_price: float | None = Field(default=None, ge=0)
    on_sale: bool | None = None
    discount: float | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None
    remarks: str | None = None


class SaleUpdate(SQLModel):
    """Sale-state update; only provided fields apply."""

    on_sale: bool | None = None
    discount: float | None = Field(default=None, ge=0, le=100)
    quantity: int | None = Field(default=None, ge=0)


class LabelTemplateCreate(SQLModel):
    name: str = Field(min_length=1)
    template: str = Field(min_length=1)
    description: str = ""


class LabelTemplateUpdate(SQLModel):
    """All fields optional; only provided fields are applied (PATCH)."""

    name: str | None = Field(default=None, min_length=1)
    template: str | None = Field(default=None, min_length=1)
    description: str | None = None
