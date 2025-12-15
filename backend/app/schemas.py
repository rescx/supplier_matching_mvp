from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, validator

from .models import SupplierMappingStatus, ModerationDecision


class PriceItemImport(BaseModel):
    ownerId: str
    packetId: str
    inn: Optional[str] = None
    std_supplier: str
    itemId: Optional[str] = None


class PriceSupplierGroupOut(BaseModel):
    id: int
    owner_id: str
    packet_id: str
    inn_norm: Optional[str]
    inn_invalid: bool
    std_supplier_raw: str
    items_count: int
    status: str
    canonical_supplier: Optional[str] = None
    canonical_supplier_id: Optional[int] = None
    latest_status: Optional[str] = None
    latest_decision_at: Optional[datetime] = None
    reject_reason_label: Optional[str] = None

    class Config:
        orm_mode = True


class SupplierBase(BaseModel):
    supplier: str
    inn: str
    kpp: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    url: Optional[str] = None
    branch: Optional[str] = None

    @validator("inn")
    def validate_inn(cls, v: str) -> str:
        digits = "".join(filter(str.isdigit, v or ""))
        if len(digits) not in (10, 12):
            raise ValueError("INN must be 10 or 12 digits")
        return digits


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(SupplierBase):
    supplier: Optional[str] = None
    inn: Optional[str] = None


class SupplierOut(SupplierBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class MappingRequest(BaseModel):
    token: str
    group_id: int
    canonical_supplier_id: int


class IssueCreate(BaseModel):
    token: str
    group_id: int
    comment: str


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class MappingModerationResponse(BaseModel):
    id: int
    owner_id: str
    packet_id: str
    inn_norm: Optional[str]
    std_supplier_raw: str
    status: SupplierMappingStatus
    canonical_supplier_id: int
    canonical_supplier: str
    created_at: datetime

    class Config:
        orm_mode = True


class RejectRequest(BaseModel):
    reason_code: str
    comment_internal: Optional[str] = None


class ModerationEventOut(BaseModel):
    id: int
    owner_id: str
    packet_id: str
    supplier_group_id: int
    decision: ModerationDecision
    decided_at: datetime
    decided_by: str
    reject_reason_label: Optional[str] = None
    reject_comment_internal: Optional[str] = None
    std_supplier_raw: Optional[str] = None
    inn_norm: Optional[str] = None
    packet: Optional[str] = None
    canonical_supplier: Optional[str] = None
    canonical_inn: Optional[str] = None
    canonical_city: Optional[str] = None
    status: Optional[SupplierMappingStatus] = None

    class Config:
        orm_mode = True


class IssueOut(BaseModel):
    id: int
    owner_id: str
    packet_id: str
    group_id: Optional[int]
    inn: Optional[str]
    inn_norm: Optional[str]
    std_supplier: Optional[str]
    comment: str
    created_at: datetime

    class Config:
        orm_mode = True


class AnalyticsMappingOut(BaseModel):
    ownerId: str
    packetId: str
    inn: Optional[str]
    std_supplier_raw: str
    canonical_supplier_id: int
    canonical_supplier: str
    approved_at: datetime
