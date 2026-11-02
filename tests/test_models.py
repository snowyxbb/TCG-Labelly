from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Product


def test_product_roundtrip():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Product(
                product_uid="P-001",
                full_sku="2XM-123-EN",
                sku="2XM-123",
                name="Lightning Bolt",
                set_name="Double Masters",
                price=3.5,
                original_price=5.0,
                on_sale=True,
                quantity=4,
            )
        )
        session.commit()

        products = session.exec(select(Product)).all()
        assert len(products) == 1
        p = products[0]
        assert p.id == 1  # auto-increment assigned
        assert p.language == "EN"  # default applied
        assert p.is_active is True  # default applied
        assert p.currency == "SGD"  # default applied


def test_product_indexes():
    expected = {"ix_product_set_language"}
    actual = {ix.name for ix in Product.__table__.indexes}
    assert expected <= actual  # composite index registered on the table
