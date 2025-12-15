from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint


class SupplierMappingStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PriceItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: str = Field(index=True)
    packet_id: str = Field(index=True)
    inn: str = Field(default="")
    inn_norm: Optional[str] = Field(default=None, index=True)
    inn_invalid: bool = Field(default=False)
    std_supplier: str = Field(index=True)
    item_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PriceSupplierGroup(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("owner_id", "packet_id", "inn_norm", "std_supplier_raw", name="uq_group"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: str = Field(index=True)
    packet_id: str = Field(index=True)
    inn_norm: Optional[str] = Field(default=None, index=True)
    std_supplier_raw: str = Field(index=True)
    items_count: int = Field(default=0)
    inn_invalid: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    mappings: List["SupplierMapping"] = Relationship(back_populates="group")


class Supplier(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    supplier: str = Field(index=True)
    inn: str = Field(index=True)
    kpp: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    url: Optional[str] = None
    branch: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    mappings: List["SupplierMapping"] = Relationship(back_populates="canonical_supplier")


class SupplierMapping(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="pricesuppliergroup.id")
    canonical_supplier_id: int = Field(foreign_key="supplier.id")
    owner_id: str = Field(index=True)
    packet_id: str = Field(index=True)
    status: SupplierMappingStatus = Field(default=SupplierMappingStatus.PENDING, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejected_by: Optional[str] = None
    reject_reason: Optional[str] = None
    std_supplier_raw: str = Field(default="")
    inn_norm: Optional[str] = Field(default=None)

    group: PriceSupplierGroup = Relationship(back_populates="mappings")
    canonical_supplier: Supplier = Relationship(back_populates="mappings")


class ModerationDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ModerationEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: str = Field(index=True)
    packet_id: str = Field(index=True)
    supplier_group_id: int = Field(index=True)
    mapping_id: Optional[int] = Field(default=None, foreign_key="suppliermapping.id")
    decision: ModerationDecision = Field(index=True)
    decided_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    decided_by: str
    reject_reason_code: Optional[str] = None
    reject_reason_label: Optional[str] = None
    reject_comment_internal: Optional[str] = None


class SellerIssue(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: str = Field(index=True)
    packet_id: str = Field(index=True)
    group_id: Optional[int] = Field(default=None, foreign_key="pricesuppliergroup.id")
    inn: Optional[str] = None
    inn_norm: Optional[str] = None
    std_supplier: Optional[str] = None
    comment: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SellerToken(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(index=True, unique=True)
    owner_id: str = Field(index=True)
    packet_id: str = Field(index=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
