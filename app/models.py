from sqlmodel import Field, Index, SQLModel


class Product(SQLModel, table=True):
    """One purchasable trading-card product (a card variant, sealed box, etc.)."""

    id: int | None = Field(default=None, primary_key=True)  # auto-increment
    product_uid: str = Field(index=True, unique=True, nullable=False)
    full_sku: str = Field(index=True, unique=True)
    sku: str = Field(index=True)
    variant: str = ""
    name: str = Field(index=True)
    language: str = "EN"
    rarity: str = ""
    set_name: str = Field(index=True)
    currency: str = "SGD"
    price: float
    original_price: float | None = None
    on_sale: bool = False
    discount: float = 0  # percentage off price while on_sale (0–100)
    is_active: bool = True
    remarks: str = ""
    quantity: int = 1

    # serves the most common combined filter: set + language
    __table_args__ = (Index("ix_product_set_language", "set_name", "language"),)