import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv

from sqlmodel import Session, select

load_dotenv()

from .database import engine, init_db
from .models import PriceItem, PriceSupplierGroup, SellerToken, Supplier
from .utils import normalize_inn


def seed_suppliers(session: Session) -> None:
    defaults = [
        {"supplier": "Росско", "inn": "7701234567", "city": "Москва", "country": "RU"},
        {"supplier": "Берг", "inn": "7807654321", "city": "Санкт-Петербург", "country": "RU"},
    ]
    for data in defaults:
        existing = session.exec(select(Supplier).where(Supplier.inn == data["inn"])).first()
        if not existing:
            session.add(Supplier(**data))


def seed_price_items(session: Session) -> list[SellerToken]:
    """Seed multiple owners/packets for richer demo."""
    batches = [
        {
            "ownerId": "demo-owner",
            "packetId": "demo-packet",
            "items": [
                *[
                    {
                        "inn": "7701234567",
                        "std_supplier": "Росско филиал Москва",
                        "itemId": f"demo-r-{i}",
                    }
                    for i in range(100)
                ],
                *[
                    {
                        "inn": "7807654321",
                        "std_supplier": "Берг Поставка",
                        "itemId": f"demo-b-{i}",
                    }
                    for i in range(50)
                ],
            ],
        },
        {
            "ownerId": "owner-2",
            "packetId": "packet-2",
            "items": [
                *[
                    {
                        "inn": "7701234567",
                        "std_supplier": "Росско Региональный",
                        "itemId": f"o2-r-{i}",
                    }
                    for i in range(60)
                ],
                *[
                    {
                        "inn": "7807654321",
                        "std_supplier": "Берг Север",
                        "itemId": f"o2-b-{i}",
                    }
                    for i in range(40)
                ],
            ],
        },
        {
            "ownerId": "owner-3",
            "packetId": "packet-3",
            "items": [
                *[
                    {
                        "inn": "7701234567",
                        "std_supplier": "Росско Центр",
                        "itemId": f"o3-r-{i}",
                    }
                    for i in range(30)
                ],
                *[
                    {
                        "inn": "7807654321",
                        "std_supplier": "Берг Юг",
                        "itemId": f"o3-b-{i}",
                    }
                    for i in range(20)
                ],
            ],
        },
    ]

    tokens: list[SellerToken] = []
    now = datetime.utcnow()

    for batch in batches:
        owner_id = batch["ownerId"]
        packet_id = batch["packetId"]
        for item in batch["items"]:
            inn_norm, inn_invalid = normalize_inn(item["inn"])
            pi = PriceItem(
                owner_id=owner_id,
                packet_id=packet_id,
                inn=item["inn"],
                inn_norm=inn_norm,
                inn_invalid=inn_invalid,
                std_supplier=item["std_supplier"],
                item_id=item["itemId"],
                created_at=now,
            )
            session.add(pi)
            group = session.exec(
                select(PriceSupplierGroup).where(
                    PriceSupplierGroup.owner_id == owner_id,
                    PriceSupplierGroup.packet_id == packet_id,
                    PriceSupplierGroup.inn_norm == inn_norm,
                    PriceSupplierGroup.std_supplier_raw == item["std_supplier"],
                )
            ).first()
            if not group:
                group = PriceSupplierGroup(
                    owner_id=owner_id,
                    packet_id=packet_id,
                    inn_norm=inn_norm,
                    std_supplier_raw=item["std_supplier"],
                    items_count=0,
                    inn_invalid=inn_invalid,
                    created_at=now,
                    updated_at=now,
                )
                session.add(group)
            group.items_count += 1
            group.updated_at = now

        token_value = str(uuid.uuid4())
        token = SellerToken(
            token=token_value,
            owner_id=owner_id,
            packet_id=packet_id,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        session.add(token)
        tokens.append(token)

    return tokens


def run_seed() -> None:
    init_db()
    with Session(engine) as session:
        seed_suppliers(session)
        tokens = seed_price_items(session)
        session.commit()
        print("Seed complete.")
        for token in tokens:
            print(f"Seller token link ({token.owner_id}/{token.packet_id}): /s/{token.token}")


if __name__ == "__main__":
    run_seed()
